#!/usr/bin/python3
import argparse
import csv
import getpass
import json
import logging
import os
import re
import sys
import textwrap
import time
from http import cookiejar
from urllib.parse import quote, unquote

import requests

log = logging.getLogger("linkedin")



def default_cookie_file():
    override = os.environ.get("LINKEDIN_COOKIE_FILE")
    if override:
        return override
    legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin-cookies.cookies")
    if os.path.exists(legacy):
        return legacy
    return os.path.join(os.path.expanduser("~"), ".linkedin-scraper", "linkedin-cookies.cookies")


COOKIE_FILE = default_cookie_file()
ME_URL = "https://www.linkedin.com/voyager/api/voyagerMe"
AUTH_URL = "https://www.linkedin.com/uas/authenticate"
SEARCH_URL = ("https://www.linkedin.com:443/voyager/api/graphql?queryId=voyagerSearchDashClusters.8883e32cfbde6e9879cab4622bf735a6"
              "&queryName=SearchClusterCollection&variables=(query:(queryParameters:(currentCompany:List({company_id}),"
              "resultType:List(PEOPLE)),flagshipSearchIntent:SEARCH_SRP,includeFiltersInResponse:false),count:{count},"
              "origin:COMPANY_PAGE_CANNED_SEARCH,start:{start})")
COMPANY_SEARCH_URL = ("https://www.linkedin.com:443/voyager/api/graphql?queryId=voyagerSearchDashClusters.8883e32cfbde6e9879cab4622bf735a6"
                      "&queryName=SearchClusterCollection&variables=(query:(keywords:{keywords},"
                      "queryParameters:(resultType:List(COMPANIES)),flagshipSearchIntent:SEARCH_SRP,includeFiltersInResponse:false),"
                      "count:{count},origin:GLOBAL_SEARCH_HEADER,start:0)")
COMPANY_RESULTS = 10
# Company URNs look like urn:li:fsd_company:1234 or urn:li:fsd_miniCompany:1234
COMPANY_URN_ID = re.compile(r"company:(\d+)", re.IGNORECASE)
API_HEADERS = {
    "X-Li-User-Agent": "LIAuthLibrary:3.2.4 com.linkedin.LinkedIn:8.8.1 iPhone:8.3",
    "User-Agent": "LinkedIn/8.8.1 CFNetwork/711.3.18 Darwin/14.0.0",
    "X-User-Language": "en",
    "X-User-Locale": "en_US",
    "Accept-Language": "en-us",
    "x-restli-protocol-version": "2.0.0",
    "Accept": "application/json",
}

PAGE_SIZE = 50
REQUEST_TIMEOUT = 30  # seconds
MAX_ATTEMPTS = 3      # per request, for network errors / HTTP 429 / HTTP 5xx
LOGIN_ATTEMPTS = 3


class LinkedInError(Exception):
    """Anything that stops us from getting data out of LinkedIn."""


class AuthError(LinkedInError):
    """The session is missing, expired, or was rejected."""


class LinkedInClient:
    def __init__(self, cookie_file=None):
        self.session = requests.Session()
        self.jar = cookiejar.LWPCookieJar(filename=cookie_file or COOKIE_FILE)
        try:
            self.jar.load(ignore_discard=True)
        except FileNotFoundError:
            log.debug("No stored cookies yet; a login will be required")
        except (OSError, cookiejar.LoadError) as exc:
            log.warning("Ignoring unreadable cookie file %s: %s", self.jar.filename, exc)
        self.session.cookies = self.jar
        self.headers = dict(API_HEADERS)
        self._sync_csrf()

    # ---- session plumbing -------------------------------------------------

    def _sync_csrf(self):
        """LinkedIn requires the JSESSIONID cookie value to be echoed back as Csrf-Token."""
        token = requests.utils.dict_from_cookiejar(self.session.cookies).get("JSESSIONID")
        if token:
            self.headers["Csrf-Token"] = token.strip('"')
        else:
            self.headers.pop("Csrf-Token", None)

    def clear_cookies(self):
        self.jar.clear()
        self._sync_csrf()

    def save_cookies(self):
        try:
            folder = os.path.dirname(self.jar.filename)
            if folder:
                os.makedirs(folder, mode=0o700, exist_ok=True)
            self.jar.save(ignore_discard=True)
            os.chmod(self.jar.filename, 0o600)  # it holds a live session; best effort (no-op on Windows)
        except OSError as exc:
            log.warning("Could not save cookies to %s: %s", self.jar.filename, exc)

    @staticmethod
    def _backoff(attempt, reason, retry_after=None):
        delay = min(60, 2 ** attempt)
        if retry_after and str(retry_after).isdigit():
            delay = min(120, int(retry_after))
        log.warning("%s; retrying in %ds (attempt %d/%d)", reason, delay, attempt, MAX_ATTEMPTS)
        time.sleep(delay)

    def _request(self, method, url, headers=None, **kwargs):
        """Send a request with a timeout, retrying network errors, HTTP 429 and HTTP 5xx."""
        merged = dict(self.headers)
        merged.update(headers or {})
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = self.session.request(method, url, headers=merged, timeout=REQUEST_TIMEOUT, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise LinkedInError(f"network error talking to LinkedIn: {exc}") from exc
                self._backoff(attempt, type(exc).__name__)
                continue
            if resp.status_code == 999:
                raise LinkedInError("LinkedIn rejected the request (HTTP 999, bot detection). Wait a while before retrying.")
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    raise LinkedInError(f"LinkedIn kept returning HTTP {resp.status_code} ({MAX_ATTEMPTS} attempts)")
                self._backoff(attempt, f"HTTP {resp.status_code}", resp.headers.get("Retry-After"))
                continue
            return resp

    @staticmethod
    def _json(resp, what):
        try:
            return resp.json()
        except ValueError:
            snippet = " ".join(resp.text[:120].split())
            raise LinkedInError(f"{what}: expected JSON but got HTTP {resp.status_code}: {snippet!r}") from None

    # ---- authentication ---------------------------------------------------

    def check_logged_in(self):
        resp = self._request("GET", ME_URL)
        if resp.status_code != 200:
            return False
        try:
            mini = self._json(resp, "session check")["miniProfile"]
            log.info("Reusing session, logged in as %s %s", mini["firstName"], mini["lastName"])
        except (LinkedInError, KeyError, TypeError):
            return False
        self.save_cookies()
        return True

    def login(self, username, password):
        log.info("Logging in")
        self._request("GET", AUTH_URL)  # LinkedIn issues the JSESSIONID cookie here
        jsessionid = requests.utils.dict_from_cookiejar(self.session.cookies).get("JSESSIONID")
        if not jsessionid:
            raise LinkedInError("LinkedIn did not issue a session cookie, so login can't proceed (blocked, or the endpoint changed)")
        resp = self._request("POST", AUTH_URL, data={
            "session_key": username,
            "session_password": password,
            "JSESSIONID": jsessionid,
        })
        payload = self._json(resp, "login")
        result = payload.get("login_result") if isinstance(payload, dict) else None
        self._sync_csrf()
        if result == "PASS":
            log.info("Login succeeded")
            self.save_cookies()
            return True
        log.error("Login failed (%s)", result or "no result returned")
        return False

    # ---- scraping ---------------------------------------------------------

    def _get_search(self, url, what, hint=""):
        resp = self._request("GET", url, headers={"X-Li-Graphql-Pegasus-Client": "true"})
        if resp.status_code in (401, 403):
            raise AuthError(f"LinkedIn rejected the session (HTTP {resp.status_code}); rerun with --clear to log in again")
        if resp.status_code != 200:
            raise LinkedInError(f"{what} failed: HTTP {resp.status_code}{' ' + hint if hint else ''}")
        return self._json(resp, what)

    def _search_page(self, company_id, start):
        url = SEARCH_URL.format(company_id=company_id, count=PAGE_SIZE, start=start)
        return self._get_search(url, f"search at offset {start}",
                                hint="(LinkedIn caps how many results one search can return)")

    def search_companies(self, keywords, count=COMPANY_RESULTS, dump_raw=None):
        """Search LinkedIn for companies by name. Returns a list of {id, name, detail, extra, url} dicts."""
        url = COMPANY_SEARCH_URL.format(keywords=quote(keywords, safe=""), count=count)
        data = self._get_search(url, "company search")
        if dump_raw:
            _dump_json(dump_raw, data, "raw company search response")
        _, items = self._page_items(data)
        companies, seen = [], set()
        for item in items:
            result = (item.get("item") or {}).get("entityResult") if isinstance(item, dict) else None
            company = parse_company(result) if isinstance(result, dict) else None
            if company and company["id"] not in seen:
                seen.add(company["id"])
                companies.append(company)
        if items and not companies:
            raise LinkedInError("the company search returned results but no company IDs could be read from them "
                                "(LinkedIn may have changed the format; try --dump-raw)")
        return companies

    @staticmethod
    def _page_items(data):
        """Return (total, items) from a search response; items is the first cluster of people results."""
        try:
            clusters = data["data"]["searchDashClustersByAll"]
            total = clusters["paging"]["total"]
            elements = clusters["elements"]
        except (KeyError, TypeError) as exc:
            raise LinkedInError("unexpected search response format (LinkedIn may have changed it; try --dump-raw)") from exc
        for element in elements:
            items = element.get("items") if isinstance(element, dict) else None
            # Clusters can carry an entityResult key whose value is null (banners, feedback cards), so
            # require an actual result rather than just the key.
            if items and any(isinstance(item, dict) and isinstance((item.get("item") or {}).get("entityResult"), dict)
                             for item in items):
                return total, items
        return total, []

    def iter_employees(self, company_id, delay=1.0, dump_raw=None):
        """Yield one employee dict at a time, so callers can save progress as it arrives."""
        seen = set()
        start, total = 0, 1
        while start < total:
            data = self._search_page(company_id, start)
            if dump_raw and start == 0:
                _dump_json(dump_raw, data, "raw search response")
            total, items = self._page_items(data)
            for item in items:
                result = (item.get("item") or {}).get("entityResult") if isinstance(item, dict) else None
                employee = parse_entity(result) if isinstance(result, dict) else None
                if employee is None:
                    continue
                if employee["profile_url"]:
                    if employee["profile_url"] in seen:
                        continue
                    seen.add(employee["profile_url"])
                yield employee
            start += PAGE_SIZE
            log.info("Fetched %d of %d results", min(start, total), total)
            if start < total:
                time.sleep(delay)


def _text(node):
    """LinkedIn wraps strings as {"text": "..."}; return "" for anything else."""
    value = node.get("text") if isinstance(node, dict) else None
    return value if isinstance(value, str) else ""


def parse_entity(result):
    """Turn one search entityResult into an employee dict, or None for hidden / unusable results."""
    name = _text(result.get("title"))
    if not name or name == "LinkedIn Member":
        return None
    nav = result.get("navigationUrl") or result.get("trackingUrn") or ""
    return {
        "name": name,
        "headline": _text(result.get("primarySubtitle")),
        "location": _text(result.get("secondarySubtitle")),
        # the profile URL minus its tracking query string is the only stable per-person ID
        "profile_url": nav.split("?")[0] if isinstance(nav, str) else "",
        # "Current: <role> at <company>" snippet when LinkedIn includes it
        "current": _text(result.get("summary")),
        # connection degree, e.g. "3rd+"; explains why some last names are truncated
        "connection": _text(result.get("badgeText")).lstrip("•· ").strip(),
    }


def _printable(value):
    """Collapse whitespace and drop control characters; names come from LinkedIn and are shown in your terminal."""
    return "".join(ch for ch in " ".join(value.split()) if ch.isprintable())


def extract_company_id(result):
    """Find the numeric company ID in a company search result, wherever LinkedIn put the URN."""
    candidates = [result.get(key) for key in ("entityUrn", "trackingUrn", "navigationUrl")]
    candidates.append(json.dumps(result))  # last resort: anywhere in the result
    for text in candidates:
        if isinstance(text, str):
            match = COMPANY_URN_ID.search(unquote(text))  # URNs inside URLs are percent-encoded
            if match:
                return match.group(1)
    return None


def parse_company(result):
    """Turn one company entityResult into a dict, or None if it has no name or readable ID."""
    name = _printable(_text(result.get("title")))
    company_id = extract_company_id(result)
    if not name or not company_id:
        return None
    nav = result.get("navigationUrl")
    return {
        "id": company_id,
        "name": name,
        "detail": _printable(_text(result.get("primarySubtitle"))),    # e.g. "Hospitals and Health Care • Tampa, FL"
        "extra": _printable(_text(result.get("secondarySubtitle"))),   # e.g. "12K followers"
        "url": nav.split("?")[0] if isinstance(nav, str) else "",
    }


def format_company(company):
    info = " · ".join(part for part in (company["detail"], company["extra"]) if part)
    return f"{company['name']}  —  {info}  [ID {company['id']}]" if info else f"{company['name']}  [ID {company['id']}]"


SEARCH_AGAIN = object()
CANCEL = object()


def _interactive():
    """True when we can show the arrow-key menu: a real terminal and questionary installed."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    try:
        import questionary  # noqa: F401
    except ImportError:
        log.info("Install 'questionary' (\"%s\" -m pip install -r requirements.txt) for an arrow-key menu; "
                 "using a numbered list instead", sys.executable)
        return False
    return True


def pick_company(companies, keywords):
    """Let the user choose one of `companies`. Returns a company dict, SEARCH_AGAIN, or None to cancel."""
    if _interactive():
        import questionary
        choices = [questionary.Choice(format_company(c), value=c) for c in companies]
        choices += [questionary.Choice("Search again…", value=SEARCH_AGAIN), questionary.Choice("Cancel", value=CANCEL)]
        choice = questionary.select(
            f"Companies matching {keywords!r} (arrows to move, type to filter, Enter to select):",
            choices=choices, use_search_filter=True, use_jk_keys=False).ask()
        return None if choice in (None, CANCEL) else choice  # ask() returns None on Ctrl+C
    for number, company in enumerate(companies, 1):
        print(f"  {number:>2}) {format_company(company)}")
    while True:
        try:
            answer = input("Select a number, 's' to search again, or Enter to cancel: ").strip().lower()
        except EOFError:
            return None
        if not answer:
            return None
        if answer == "s":
            return SEARCH_AGAIN
        if answer.isdigit() and 1 <= int(answer) <= len(companies):
            return companies[int(answer) - 1]
        print(f"Please enter a number from 1 to {len(companies)}.")


def choose_company(client, keywords, dump_raw=None):
    """Search for `keywords` and let the user pick a company, searching again as often as they like."""
    while True:
        companies = client.search_companies(keywords, dump_raw=dump_raw)
        if not companies:
            print(f"No companies found matching {keywords!r}.")
        choice = pick_company(companies, keywords)
        if choice is not SEARCH_AGAIN:
            return choice
        try:
            keywords = input("Search for: ").strip()
        except EOFError:
            return None
        if not keywords:
            return None


def load_names():
    """The name-parsing module, or None (with a warning) if its dependency isn't installed."""
    try:
        import names
    except ImportError as exc:
        log.warning("Name parsing unavailable (%s), so the CSV won't include first/last names or emails; "
                    "install the dependencies with: \"%s\" -m pip install -r requirements.txt", exc, sys.executable)
        return None
    return names


def _safe_cell(value):
    """Keep spreadsheets from treating scraped text that starts with = + - @ as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class CsvSink:
    """The results CSV, written as employees arrive so a crash or Ctrl+C keeps what was collected.

    With the names module each row is a parsed record: First / Middle / Last, Email and Email Note when an
    email template is given (blank when no address can be built, e.g. the last name is only an initial),
    credentials, a Review note for names worth checking by hand, then the LinkedIn fields. Without it
    (nameparser not installed) the rows are just the LinkedIn fields.

    Duplicate-address notes need every row, so finish() rewrites the file once at the end if any turned up.
    """
    RAW_COLUMNS = [("Name", "name"), ("Headline", "headline"), ("Location", "location"),
                   ("Profile URL", "profile_url"), ("Current", "current"), ("Connection", "connection")]

    def __init__(self, path, names_module=None, email_template=None):
        self._path = path
        self._names = names_module
        self._template = email_template if names_module else None
        self._columns = names_module.csv_columns(bool(self._template)) if names_module else self.RAW_COLUMNS
        self._records = []
        self._file = open(path, "w", encoding="utf-8-sig", newline="")  # BOM so Excel reads UTF-8
        self._writer = csv.writer(self._file)
        self._writer.writerow(self._header())
        self._file.flush()

    def _header(self):
        return [header for header, _ in self._columns]

    def _cells(self, record):
        return [_safe_cell(record.get(key, "")) for _, key in self._columns]

    def write(self, employee):
        record = self._names.enrich(employee, self._template) if self._names else employee
        self._records.append(record)
        self._writer.writerow(self._cells(record))
        self._file.flush()

    def finish(self):
        self._file.close()
        if not (self._template and self._names.mark_duplicates(self._records)):
            return
        temp = self._path + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self._header())
                writer.writerows(self._cells(record) for record in self._records)
            os.replace(temp, self._path)  # fails if the file is open in Excel; the unannotated copy stays
        except OSError as exc:
            log.warning("Could not add duplicate-address notes to %s: %s", self._path, exc)
            try:
                os.remove(temp)
            except OSError:
                pass


def _dump_json(path, payload, what):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        log.info("Wrote %s to %s", what, path)
    except (OSError, TypeError, ValueError) as exc:
        log.warning("Could not write %s: %s", path, exc)


def authenticate(client, args):
    """Reuse the stored session or log in, prompting for credentials as needed. Returns success."""
    if client.check_logged_in():
        return True
    username = args.username or os.environ.get("LINKEDIN_USERNAME")
    password = args.password or os.environ.get("LINKEDIN_PASSWORD")
    for attempt in range(1, LOGIN_ATTEMPTS + 1):
        try:
            if attempt > 1 or not username:
                default = f" [{username}]" if username else ""
                username = input(f"Username{default}: ").strip() or username
            if attempt > 1 or not password:
                password = getpass.getpass("Password: ")
        except EOFError:
            log.error("No credentials supplied and no terminal to prompt on (use -u/-p or LINKEDIN_USERNAME/LINKEDIN_PASSWORD)")
            return False
        if client.login(username, password):
            return True
        if attempt < LOGIN_ATTEMPTS:
            log.warning("Please re-enter your LinkedIn credentials")
    return False


def print_table(employees, emails=None):
    """Console summary (with an Email column when `emails` is given); headlines are truncated and
    flattened so one row is always one line."""
    def cell(value, limit=None):
        value = _printable(value)
        return value if limit is None or len(value) <= limit else value[:limit - 1] + "…"

    titles = ["Name"] + (["Email"] if emails is not None else []) + ["Headline", "Location"]
    rows = []
    for i, e in enumerate(employees):
        row = [cell(e["name"])]
        if emails is not None:
            row.append(cell(emails[i]))
        rows.append(row + [cell(e["headline"], 60), cell(e["location"])])
    widths = [max([len(t)] + [len(r[i]) for r in rows]) + 1 for i, t in enumerate(titles)]
    fmt = " | ".join("{:<%d}" % w for w in widths)
    header = fmt.format(*titles)
    print("\n" + header)
    print("=" * len(header))
    for row in rows:
        print(fmt.format(*row))


def company_id(value):
    if not value.isdigit():
        raise argparse.ArgumentTypeError("must be the numeric company ID (digits only)")
    return value


def search_text(value):
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("search text can't be empty")
    return value


def companies_dump_path(path):
    """--dump-raw PATH holds the people search; the company search goes next to it as PATH-companies.ext."""
    root, ext = os.path.splitext(path)
    return f"{root}-companies{ext}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="linkedin-scraper",
        description="Scrape the employees of a LinkedIn company, and optionally generate email addresses for them.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            email format placeholders (case-insensitive result, accents and punctuation stripped):
              {first} {last} {middle}   whole names
              {f} {l} {m}               first letters
            People whose last name is only an initial are skipped when the format uses {last}.

            examples:
              %(prog)s -c 1234567 -o employees.csv
              %(prog)s -s "Acme Corp" -o employees.csv -f "{f}.{last}@example.com"
              %(prog)s -c 1234567 -f "{first}.{last}@example.com" -eo emails.txt

            files are only written where you ask: -o is the results CSV (First, Middle, Last, Email, Email Note,
            Credentials, Alt Name, Review, Name, Headline, Location, Current, Connection, Profile URL; Email and
            Email Note need -f), -eo is a plain text list of the generated addresses, and --json-out and
            --dump-raw are optional extras.

            -s searches LinkedIn for companies by name and shows a menu to pick one; it prints the
            company ID it chose so later runs can skip the search with -c.

            credentials may also come from LINKEDIN_USERNAME / LINKEDIN_PASSWORD, which keeps the
            password out of your shell history and process list.

            the login session is stored in ~/.linkedin-scraper/ (override with LINKEDIN_COOKIE_FILE);
            --clear forces a fresh login."""))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("-c", "--company", type=company_id, help="numeric company ID to scrape")
    target.add_argument("-s", "--search", type=search_text, metavar="NAME",
                        help="search for a company by name and pick it from a menu")
    parser.add_argument("-o", "--outfile", metavar="CSV",
                        help="results CSV: parsed names, emails (with -f), review notes and the LinkedIn fields; overwritten each run")
    parser.add_argument("-u", "--username", help="LinkedIn username")
    parser.add_argument("-p", "--password", help="LinkedIn password")
    parser.add_argument("--clear", action="store_true", help="clear stored cookies and force a fresh login")
    parser.add_argument("-f", "--email-format", metavar="TEMPLATE", help='generate emails, e.g. "{f}.{last}@example.com"')
    parser.add_argument("-eo", "--email-out", metavar="TXT",
                        help="text file of the generated email addresses, one per line, no duplicates (needs -f; overwritten each run)")
    parser.add_argument("--json-out", metavar="JSON", help="also save the raw scrape as JSON")
    parser.add_argument("--dump-raw", metavar="JSON",
                        help="save the first raw search response (and, with -s, the company search as <name>-companies.json) "
                             "to see what other fields LinkedIn returns")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between result pages (default: 1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    if args.email_out and not args.email_format:
        parser.error("-eo/--email-out needs -f/--email-format to say how to build the addresses")
    if args.email_format:
        try:
            import names
        except ImportError as exc:
            parser.error(f"name parsing needs the 'nameparser' package ({exc}). This is running under {sys.executable}; "
                         f"install the dependencies into that environment with: "
                         f"\"{sys.executable}\" -m pip install -r requirements.txt")
        try:
            names.template_fields(args.email_format)
        except ValueError as exc:
            parser.error(str(exc))
    return args


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="[%(levelname)s] %(message)s")
    employees = []
    status = 0
    names_module = load_names() if (args.outfile or args.email_format) else None

    client = LinkedInClient()
    if args.clear:
        client.clear_cookies()
    try:
        if not authenticate(client, args):
            return 1
        company = args.company
        if args.search:
            chosen = choose_company(client, args.search,
                                    dump_raw=companies_dump_path(args.dump_raw) if args.dump_raw else None)
            if chosen is None:
                log.error("No company selected")
                return 1
            company = chosen["id"]
            log.info("Using %s (company ID %s); skip the search next time with: -c %s", chosen["name"], company, company)
        sink = None  # created on the first result, so a run that fails early can't truncate an earlier good file
        try:
            for employee in client.iter_employees(company, delay=args.delay, dump_raw=args.dump_raw):
                employees.append(employee)
                if args.outfile:
                    if sink is None:
                        sink = CsvSink(args.outfile, names_module, args.email_format)
                    sink.write(employee)
        finally:
            if sink:
                sink.finish()
    except KeyboardInterrupt:
        log.warning("Interrupted; keeping the %d employees collected so far", len(employees))
        status = 130
    except LinkedInError as exc:
        log.error("%s", exc)
        log.error("Keeping the %d employees collected so far", len(employees))
        status = 1
    except OSError as exc:
        log.error("File error while saving results: %s", exc)
        status = 1

    if not employees:
        log.warning("No employees collected; nothing saved")
        return status or 1

    if args.json_out:  # only written when there is data, so a failed run can't clobber an earlier good file
        _dump_json(args.json_out, employees, f"{len(employees)} employees")

    records = None
    if args.email_format and names_module:  # parse_args already checked the names module imports
        records = names_module.build_records(employees, args.email_format)
    print_table(employees, [r["email"] for r in records] if records else None)
    if records:
        print(f"\n{names_module.summary(records, args.email_format)}" + (f" -> {args.outfile}" if args.outfile else ""))
        if args.email_out:
            try:
                count = names_module.write_emails(args.email_out, records)
            except OSError as exc:
                log.error("Cannot write %s: %s", args.email_out, exc)
                status = status or 1
            else:
                if count:
                    print(f"{count} email addresses -> {args.email_out}")
                else:
                    log.warning("No email addresses were generated, so %s was not written", args.email_out)
        if not (args.outfile or args.email_out):
            print("(no -o or -eo given, so nothing was saved)")
    elif args.outfile:
        print(f"\n{len(employees)} employees -> {args.outfile}")
    return status


if __name__ == "__main__":
    sys.exit(main())
