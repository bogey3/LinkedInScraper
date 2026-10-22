# LinkedIn Scraper
I know it's not a very creative name, but it sure is descriptive.

## How it works
Lists the employees of a LinkedIn company, either by company ID or by searching for the company by name, and can turn the names into email addresses using a template you supply. It works by emulating the API calls made by the LinkedIn app on iOS.

Display names are messy (`Michelle Vecchione McEvoy MSN/Ed, RN, NPD-BC`, `Cari S.`, `Dr. Rob Worthington-Kirsch`), so the names are split into first / middle / last with credentials, titles and nicknames separated out.

Only use this where you are authorized to. Scraping LinkedIn is against its terms of service and the account you use may be restricted.

## Install
Requires Python 3.9+. The easiest way is [pipx](https://pipx.pypa.io), which puts the commands on your PATH in their own virtual environment:
```
pipx install git+https://github.com/bogey3/LinkedInScraper
```
From a local clone: `pipx install .` (or `pipx install --editable .` while developing). Upgrade with `pipx upgrade linkedin-scraper`, remove with `pipx uninstall linkedin-scraper`.

Without installing, from a clone: `pip install -r requirements.txt`, then run `python linkedin.py` / `python names.py`.

This provides two commands:

| Command | What it does |
|---|---|
| `linkedin-scraper` | Scrapes a company and optionally parses names / generates emails |
| `linkedin-names` | Parses names / generates emails from a previous scrape's JSON or CSV |

## Usage
```
linkedin-scraper -s "Acme Corp" -f "{f}.{last}@example.com"
linkedin-scraper -s "Acme Corp" -o employees.csv -f "{f}.{last}@example.com"
linkedin-scraper -c 1234567 -o employees.csv
linkedin-scraper -c 1234567 -f "{first}.{last}@example.com" -eo emails.txt
linkedin-names employees.csv -f "{last}.{first}@example.com" -o people.csv -eo emails.txt
```
Files are written only where you ask: `-o` is the results CSV and `-eo` is a plain list of emails; nothing else is created unless you pass `--json-out` or `--dump-raw`.

| Option | |
|---|---|
| `-c`, `--company ID` | Numeric company ID to scrape |
| `-s`, `--search NAME` | Search for a company by name and pick it from a menu (prints the ID it chose, so later runs can use `-c`) |
| `-o`, `--outfile CSV` | The results CSV (see [Output](#output); overwritten each run). Without it, results are only shown on the console |
| `-f`, `--email-format TEMPLATE` | Generate email addresses, e.g. `{f}.{last}@example.com` |
| `-eo`, `--email-out TXT` | A plain text file of the generated addresses: one per line, no duplicates, nobody without an address. Needs `-f`; works with or without `-o` (overwritten each run) |
| `--json-out JSON` | Also save the raw scrape as JSON |
| `-u`, `-p` | LinkedIn username / password (or `LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD`) |
| `--clear` | Forget the stored session and log in again |
| `--delay SECONDS` | Wait between result pages (default 1) |
| `--dump-raw JSON` | Save the first raw search response (with `-s`, also the company search as `<name>-companies.json`) to see what else LinkedIn returns |
| `-v` | Debug logging |

You are prompted for credentials if there is no valid stored session. `-s` shows an arrow-key menu (type to filter) in a terminal, or a numbered list when there is no terminal.

The login session is kept in `~/.linkedin-scraper/` (override with `LINKEDIN_COOKIE_FILE`). Results are saved as they arrive, so a failure or Ctrl+C keeps what was collected.

## Email formats
The template can use `{first}` `{last}` `{middle}` and `{f}` `{l}` `{m}` (first letters), plus any literal text:

| Template | Result for *Jane Q. Smith* |
|---|---|
| `{f}.{last}@example.com` | `j.smith@example.com` |
| `{first}.{last}@example.com` | `jane.smith@example.com` |
| `{last}{f}@example.com` | `smithj@example.com` |

Names are lowercased with accents folded and spaces, dots and apostrophes removed (hyphens are kept), so `José García-López` becomes `jose` / `garcia-lopez`. People without a usable last name (LinkedIn shows only an initial for people outside your network) get no address when the format uses `{last}`; `Email Note` says why, and addresses that would collide are marked as duplicates. The format is a guess at the company's convention, so check it against a known address.

## Output
The console shows a summary table (with an `Email` column when you use `-f`):
```
Name                | Email                  | Headline                      | Location
=========================================================================================
Jane Q. Smith, RN   | j.smith@example.com    | Nurse Manager                 | Tampa, FL
Raj Patel           | r.patel@example.com    | Physician Liaison             | Denver, CO
```
The `-o` CSV is the whole product, one row per person:

| Column | Contents |
|---|---|
| `First`, `Middle`, `Last` | The parsed name, so `Michelle Vecchione McEvoy MSN/Ed, RN` gives `Michelle` / `McEvoy` |
| `Email`, `Email Note` | Only with `-f`. The address, blank when none can be built, with the reason (for example the last name is only an initial) or a duplicate-address warning in `Email Note` |
| `Credentials` | What was stripped from the name: `RN`, `PhD`, `Dr.` |
| `Alt Name` | Nicknames and maiden names: `Robert "Bobby" Greene` gives `Bobby` |
| `Review` | Why the name is worth checking by hand (blank when the parse looks fine), for example a three-word name that could be a middle name or a double surname |
| `Name` | The display name exactly as LinkedIn shows it |
| `Headline`, `Location`, `Current`, `Connection`, `Profile URL` | The LinkedIn fields |

Rows are written as they arrive, so a failure or Ctrl+C keeps what was collected. If duplicate addresses turn up, the file is rewritten once at the end to mark them; if it's open in Excel at that point, the first copy is kept and you get a warning. Text that begins with `=`, `+`, `-` or `@` is prefixed with `'` so spreadsheets don't read it as a formula. Without the `nameparser` package you get just `Name` and the LinkedIn fields, with a warning.

`linkedin-names` produces the same file from an earlier scrape. Give it `-o`, `-eo`, or both.

The `-eo` file is just the addresses, ready to paste into another tool:
```
j.smith@example.com
r.patel@example.com
```
