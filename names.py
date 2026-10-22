#!/usr/bin/python3
import argparse
import csv
import json
import re
import string
import sys
import unicodedata
from collections import Counter
from nameparser import HumanName
from nameparser.config import Constants


def norm(token):
    return re.sub(r"[^A-Za-z0-9]", "", token).upper()


# Post-nominal credentials, grouped by field. Everything is compared after uppercasing and removing all
# but letters/digits, so "D.O.", "PA-C", "NPD-BC", "R.T." and "Ph.D." all match. Matching is also
# case-sensitive (see is_credential), so a surname like "Ma", "Do" or "Pe" is never mistaken for one.
# Add new ones to the right group; anything unknown still gets flagged for review rather than guessed.
_CREDENTIAL_GROUPS = {
    "associate/bachelor degrees": """
        AA AAS AGS ASN BA BS BSc BSci BSE BSEE BSME BSCE BSChE BSAE BSCS BSIT BSBA BSPH BSEd BSW BBA BCom
        BFA BEd BEng BTech BArch BMus BLA BPharm BDS MBBS MBChB BCh BAO BMBS BHSc BAS BSN BSDI BPH LLB BCL
        BCS BMed BPS BSPT BSOT BSRT BEcon BMath BAcc
    """,
    "master's degrees": """
        MA MS MSc MSci MEng MBA EMBA PMBA MPA MPH MPP MSW MFA MEd MSEd MMS MHA MHSA MSN MSPH MLIS MLS MIS MIM
        MFin MSF MAcc MSA MSBA MSCS MSIS MSIT MSEE MSME MSE MTech MArch MMus MDiv MTh LLM JSM MPhil MRes MST
        MSM MHR MHRM MSHRM MOT MPT MSPT MCS MSL MAT MAEd MBAN MSOD MSLS MCom MChem MPhys MMath MBiol MGeol
        MPAS MSCM MSEM MSIE MSBME MSHI MSHA MSHS MSNEd MCP MUP MPS MPD MIB
    """,
    "doctorates": """
        PhD DPhil EdD EdS DBA PsyD DrPH DSc DSci DEng DPA DMin ThD DNP DPT DHA DHSc DSW DMA DMD DDS DO MD DVM
        VMD OD DC DPM PharmD JD SJD LLD DMSc DBH DOT AuD DSL DCS DIT DLitt DEd DAT OTD
    """,
    "nursing/medicine/allied health": """
        RN LPN LVN CNA NP FNP ANP ACNP AGNP AGACNP AGPCNP PNP PMHNP NNP WHNP CNM CRNA CNS APRN ARNP CRNP
        RNBC FNPBC CCRN CEN CNOR CPN CPHQ CPEN CMSRN PCCN CRRN OCN CHPN CWOCN CWCN CNRN CGRN CAPA CPAN
        NPDBC NEBC RNC CLC IBCLC PA PAC PAS RT RRT CRT RRTNPS CRNFA RDMS RDCS RVT RVS RPhS RCS RCIS RTR ARRT
        ARDMS CCT CST CNMT RDH RDN RD LDN CDE CDCES BCBA BCBAD BCaBA CCCSLP CCC CCCA SLP CFYSLP OTR OTRL COTA
        PT PTA LMT LAC LPC LPCC LCSW LMFT LMHC LCPC LSW LMSW LICSW LISW CSW ACSW NCC CRC CADC LADC CASAC ATC
        ATCL CSCS CPT EMT EMTB EMTP NREMT CMA RMA CPhT RPh BCPS BCACP BCOP BCGP BCNSP LP NRCMA
    """,
    "medical coding/health information/administration": """
        CPC CPCO CCS CCSP COC CIC CPMA CPB CPPM CHC CHPC CPHRM CPPS CPHIMS CAHIMS RHIA RHIT CHDA CPCS CPLS
        CPMSM PAHM CMPE FACMPE CMQ
    """,
    "medical fellowships/board certifications": """
        FACS FACOS FACP FACC FACOG FACEP FAAP FAAN FAAFP FACR FACG FASN FASCP FSCAI FCCP FCCM FHRS FAHA FASE
        FACPE FASHP FACSM FAAOS FAANS FRCS FRCP FRCPC FRCSC FRACS FRACP MRCP MRCS MRCOG MRCGP DABR DABIM
        DABVLM ABVLM FAVLS FASMBS FACHE FAAD DABD FAAO FAACAP FAPA FAAEM FCAP FACE FACN FAAHPM ABD
    """,
    "accounting/finance/insurance/real estate": """
        CPA CMA CFA CFP CFE CIA CISA CGMA CTP EA CRPC ChFC CLU CIMA CIMC CPWA AEP PFS CAIA FRM PRM CQF CBA
        CCE CCIFP CFF ABV CVA ASA ARM CPCU AIC CRM CWCA FLMI ACS CLF RICP CEBS CFS MSFS CAP CAS FCAS ACAS FSA
        FIA MAAA FCA ACA ACCA FCCA CGA FCMA CRMA CCSA CGAP CICA AAMS CRPS CKA CDFA CEPA CPFA CMFC CRE CCIM
        SIOR MAI SRA CRB GRI ABR SRES CRS CIPS CDPE EPRO CLHMS REBC RHU LUTCF CLTC ChSNC CA
    """,
    "project/quality/operations/supply chain/safety": """
        PMP CAPM PgMP PfMP PMIACP PMIRMP PMISP PMIPBA PRINCE2 CSM CSPO PSM PSPO SPC RTE POPM SSBB SSBBP SSGB
        SSYB CSSBB CSSGB LSSBB LSSGB LSSYB LSSMBB CQE CQA CQIA CQM CMQ CMQOE CSQE CRE CQT CPIM CSCP CLTD
        CPSM CSCMP CPM CCM CPP CIRM CIH CHST OHST CSHM ASP GSP CMIOSH CPEA CEM CMVP CSP CPE
    """,
    "engineering/architecture/surveying": """
        PE PEng EIT CEng IEng PLS AIA FAIA NCARB LEED LEEDAP LEEDGA AP GA BDC IDC OMC NDC
    """,
    "HR/legal/privacy/compliance": """
        SHRMCP SHRMSCP PHR SPHR GPHR PHRca SPHRca PHRi SPHRi CCP CPLP CPTD APTD HRMP CPHR CHRP CHRL Esq LLM
        SJD CIPP CIPPUS CIPPE CIPPC CIPPA CIPPG CIPM CIPT FIP AIGP CCEP CCEPI CAMS CRCM CHC CHPC CFE
    """,
    "marketing/communications/nonprofit/business analysis": """
        CFRE ACFRE CMP CAE CMM CPSM CSP CPRC APR CCXP CBAP CCBA PCM
    """,
    "information security": """
        CISSP ISSAP ISSEP ISSMP CSSLP CCSP SSCP CAP CISM CISA CRISC CGEIT CDPSE CCISO CEH CHFI CND ECSA LPT
        CPENT OSCP OSCE OSCE3 OSEP OSWE OSED OSWP OSDA GPEN GWAPT GCIH GCIA GSEC GSLC GCFA GCFE GREM GXPN
        GISP GCED GMON GCWN GCTI GRID GSNA GSTRT GLEG GIAC GASF GNFA GDAT GOSI GCPM GICSP GRTP GCUX GWEB
        GAWN PNPT eJPT eCPPT CRTP CRTE CRTO CPTS CBBH PenTest CySA CASP CCSK CCZT CGRC CSX CPT CFR CSA QSA
        ISA CBCP MBCP CRMP CFSE
    """,
    "IT/networking/cloud/data": """
        CCNA CCNP CCIE CCDA CCDP CCT MCSE MCSA MCSD MCITP MCT MCP MCTS MCPD MCDBA CKA CKAD CKS RHCE RHCSA
        RHCA RHCSS LPIC ITIL ITILF COBIT TOGAF VCP VCAP VCDX VCIX JNCIA JNCIS JNCIP JNCIE CBIP CDMP CDP
    """,
    "education": """
        NBCT CAGS ABD NCSP TEFL TESOL CELTA
    """,
    "UK/Commonwealth professional bodies": """
        FRSA FRS FREng FIET MIET FCIPD MCIPD CMgr FCMI CMI CITP FBCS MBCS CSci CChem FRSC MRSC FRICS MRICS
        FCIOB MCIOB FCIBSE MCIBSE FICE MICE CPhys CEnv CGeol
    """,
    "military/aviation": """
        USMC USN USAF USCG USNR USAR CFI CFII ATP
    """,
}
CREDENTIALS = {norm(c) for group in _CREDENTIAL_GROUPS.values() for c in group.split()}

# nameparser ships ~600 more vetted credential acronyms; reuse them (matched case-sensitively here).
# RA is left out: it is also a Korean surname, and an all-caps name gives no case to tell them apart.
try:
    from nameparser.config.suffixes import SUFFIX_ACRONYMS as _NAMEPARSER_ACRONYMS
except ImportError:  # moved in some nameparser release; the curated list above still applies
    _NAMEPARSER_ACRONYMS = ()
CREDENTIALS |= {norm(c) for c in _NAMEPARSER_ACRONYMS} - {"RA"}

# Credentials that carry digits or vary in form, matched on the normalized token:
# Microsoft exam codes (AZ-104, SC-200, DP-203), LPIC-1, ITIL4, PRINCE2.
CREDENTIAL_PATTERNS = [
    re.compile(r"^(?:AZ|SC|MS|MB|DP|PL|AI|MD|AWS)\d{3,4}[A-Z]?$"),
    re.compile(r"^(?:LPIC|ITIL|PRINCE)\d[A-Z]*$"),
]
TITLECASE_OK = {"ESQ"}  # the only credentials normally written Capitalized

# nameparser matches its own acronym suffix list case-insensitively, which strips real surnames such as
# "Pe" or "Ra". Credentials are handled here with case awareness, so switch that list off; nameparser
# still handles Jr / Sr / III / Esq.
try:
    NAME_CONSTANTS = Constants(suffix_acronyms=set())
except TypeError:  # a nameparser without that option falls back to its defaults
    NAME_CONSTANTS = None
GENERATIONAL = {"II", "III", "IV", "JR", "SR"}
PARTICLES = {"de", "del", "della", "der", "den", "di", "da", "van", "von", "la", "le", "bin", "al", "st"}
LAST_INITIAL = re.compile(r"^[A-Za-z]\.?$")
EMOJI_AND_SYMBOLS = re.compile(r"[™®©‍️]|[\U0001F000-\U0001FFFF☀-➿]")
# two+ capital letters, but not dotted initials like "S." or "C.J."
ALL_CAPS_TOKEN = re.compile(r"^(?!(?:[A-Z]\.)+$)(?=(?:.*[A-Z]){2})[A-Z][A-Z/.\-]+$")
# comma, or a spaced slash / pipe / dash, ends the name and starts credentials or junk
SEPARATOR = re.compile(r",|\s[/|\-–—]\s")

# Input row fields (the scraper's field names), in legacy positional order.
ROW_FIELDS = ["name", "headline", "location", "profile_url", "current", "connection"]
# Header cells are matched on their letters only, lowercased. "_" marks columns the results CSV carries
# besides the raw fields (parsed names, emails, review notes); they are recomputed here, so they're
# recognized in a header but not read.
HEADER_ALIASES = {"name": "name", "headline": "headline", "location": "location",
                  "profileurl": "profile_url", "current": "current", "connection": "connection",
                  "first": "_", "middle": "_", "last": "_", "email": "_", "emailnote": "_",
                  "credentials": "_", "altname": "_", "review": "_"}

EMAIL_FIELDS = {"first": "first name", "last": "last name", "middle": "middle name",
                "f": "first name", "l": "last name", "m": "middle name"}

# The results CSV, shared by `linkedin-names` and the scraper's -o file: (header, record key).
# Names and emails come first because they are what the file is for; "Review" is the reason a name
# should be checked by hand (blank when the parse looks fine).
NAME_COLUMNS = [("First", "first"), ("Middle", "middle"), ("Last", "last")]
EMAIL_COLUMNS = [("Email", "email"), ("Email Note", "email_note")]
DETAIL_COLUMNS = [("Credentials", "credentials"), ("Alt Name", "alt_name"), ("Review", "review_reason"),
                  ("Name", "raw_name"), ("Headline", "headline"), ("Location", "location"),
                  ("Current", "current"), ("Connection", "connection"), ("Profile URL", "profile_url")]
DUPLICATE_NOTE = "duplicate address (same name at this company?)"


def csv_columns(with_email):
    return NAME_COLUMNS + (EMAIL_COLUMNS if with_email else []) + DETAIL_COLUMNS


# ---- name parsing ---------------------------------------------------------

def _known(token):
    n = norm(token)
    return n in CREDENTIALS or any(p.match(n) for p in CREDENTIAL_PATTERNS)


def is_credential(token, strict_case=True):
    """True if token is a known credential.

    strict_case rejects "Ma", "Do", "Ba" (surnames) and lowercase tokens, so only
    credential-looking casing ("MA", "RPhS", "PhD", "MSN/Ed") is accepted.
    Compound forms count when every part is known: "MD/PhD", "CISSP-ISSAP", "CCC-SLP", "OTR/L".
    """
    if strict_case and (token.islower() or token == token.capitalize()) and norm(token) not in TITLECASE_OK:
        return False
    if _known(token):
        return True
    parts = [p for p in re.split(r"[/\-]", token) if p]
    return len(parts) > 1 and all(_known(p) for p in parts)


def titlecase_tokens(name):
    """Fix all-upper / all-lower names without mangling mixed-case ones like McEvoy."""
    if name.isupper() or name.islower():
        name = name.title()
    out = []
    for i, tok in enumerate(name.split()):
        if tok.islower() and (i == 0 or tok not in PARTICLES):
            tok = tok[:1].upper() + tok[1:]
        out.append(tok)
    return " ".join(out)


def split_attached_slash(tokens):
    """'Taylor/NRCMA' -> 'Taylor', 'NRCMA' (only when the right side is an uppercase credential)."""
    out = []
    for tok in tokens:
        left, slash, right = tok.rpartition("/")
        if slash and left and right.isupper() and _known(right) and not is_credential(tok):
            out += [left, right]
        else:
            out.append(tok)
    return out


def parse_name(raw):
    """Return dict of first/middle/last/credentials/alt_name/flags for one raw name."""
    reasons = []
    name = unicodedata.normalize("NFKC", raw)
    name = EMOJI_AND_SYMBOLS.sub("", name)

    creds = []
    m = SEPARATOR.search(name)
    if m:
        tail = re.sub(r"\s+", " ", name[m.end():]).strip(" ,")
        name = name[:m.start()]
        if tail:
            creds.append(tail)

    # parentheticals in the name itself: credentials -> creds, otherwise maiden name / nickname -> alt
    alt = []
    for inner in re.findall(r"\(([^)]*)\)", name):
        inner = inner.strip()
        if inner and all(is_credential(t) for t in inner.split()):
            creds.append(inner)
        elif inner:
            alt.append(inner)
    name = re.sub(r"\([^)]*\)", " ", name)

    tokens = split_attached_slash(name.split())
    all_caps = " ".join(tokens).isupper()  # no case signal, so surname-vs-credential is a guess
    if all_caps and len(tokens) > 2:
        reasons.append("all-caps name")
    # peel trailing credentials that had no comma ("Hayley Bowden RDMS RVT"), keeping 2 name tokens
    peeled = []
    while len(tokens) > 2 and is_credential(tokens[-1], strict_case=not all_caps):
        peeled.insert(0, tokens.pop())
    leftovers = [t for t in tokens if ALL_CAPS_TOKEN.match(t) and norm(t) not in GENERATIONAL]

    name = titlecase_tokens(" ".join(tokens))
    hn = HumanName(name, constants=NAME_CONSTANTS)
    first, middle, last = hn.first, hn.middle, hn.last
    if hn.nickname:
        alt.append(hn.nickname)
    creds = ([hn.title] if hn.title else []) + peeled + creds
    if hn.suffix:
        creds.append(hn.suffix)

    last_is_initial = bool(LAST_INITIAL.match(last))
    if not last:
        reasons.append("no last name")
    # a full-word middle name could really be a compound first name or double surname
    if any(len(w.rstrip(".")) > 1 for w in middle.split()):
        reasons.append("ambiguous middle/compound name")
    if leftovers and not all_caps:
        reasons.append("possible unrecognized credential: " + " ".join(leftovers))

    return {
        "first": first,
        "middle": middle,
        "last": last,
        "credentials": "; ".join(c for c in creds if c),
        "alt_name": "; ".join(alt),
        "last_is_initial": last_is_initial,
        "needs_review": bool(reasons),
        "review_reason": "; ".join(reasons),
    }


# ---- email generation -----------------------------------------------------

def template_fields(template):
    """Validate an email template and return the set of placeholders it uses. Raises ValueError."""
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"invalid email format {template!r}: {exc}") from None
    fields = set()
    for _, field, spec, conversion in parsed:
        if field is None:
            continue
        if field not in EMAIL_FIELDS or spec or conversion:
            shown = field + (f"!{conversion}" if conversion else "") + (f":{spec}" if spec else "")
            raise ValueError(f"unsupported placeholder {{{shown}}} in email format; "
                             f"use: {', '.join('{' + f + '}' for f in EMAIL_FIELDS)}")
        fields.add(field)
    if not fields:
        raise ValueError("email format needs at least one placeholder, e.g. '{f}.{last}@example.com'")
    if "@" not in template:
        raise ValueError("email format must contain '@', e.g. '{f}.{last}@example.com'")
    return fields


def email_part(value):
    """Lowercase ASCII-only name fragment: accents folded, spaces/dots/apostrophes dropped, hyphens kept."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9_-]", "", value)


def make_email(template, rec):
    """Return (email, note). email is "" when a field the template needs is unavailable."""
    last_full = email_part(rec["last"])
    values = {
        "first": email_part(rec["first"]),
        "last": "" if rec["last_is_initial"] else last_full,  # an initial is not a usable surname
        "middle": email_part(rec["middle"]),
    }
    values["f"] = values["first"][:1]
    values["l"] = last_full[:1]
    values["m"] = values["middle"][:1]

    missing = sorted(f for f in template_fields(template) if not values[f])
    if missing:
        if "last" in missing and rec["last_is_initial"]:
            return "", "last name is only an initial"
        return "", "no " + ", ".join(sorted({EMAIL_FIELDS[f] for f in missing}))
    return template.format(**values).lower(), ""


def enrich(row, email_template=None):
    """Parse one row (a dict with the ROW_FIELDS keys) into a record, with its email if a template is given."""
    rec = parse_name(row["name"])
    rec.update(raw_name=row["name"], **{k: row.get(k, "") for k in ROW_FIELDS if k != "name"})
    if email_template:
        rec["email"], rec["email_note"] = make_email(email_template, rec)
    return rec


def mark_duplicates(records):
    """Note addresses shared by several people (it needs every row). Returns True if any record changed."""
    counts = Counter(r["email"] for r in records if r.get("email"))
    changed = False
    for rec in records:
        if rec.get("email") and counts[rec["email"]] > 1 and rec["email_note"] != DUPLICATE_NOTE:
            rec["email_note"] = DUPLICATE_NOTE
            changed = True
    return changed


def build_records(rows, email_template=None):
    """Parsed records for all rows, with emails (and duplicate notes) if a template is given."""
    records = [enrich(row, email_template) for row in rows]
    if email_template:
        mark_duplicates(records)
    return records


def summary(records, email_template=None):
    flagged = sum(r["needs_review"] for r in records)
    text = (f"{len(records)} people ({sum(r['last_is_initial'] for r in records)} last-initial only, "
            f"{flagged} flagged for review)")
    if email_template:
        made = sum(1 for r in records if r["email"])
        dupes = sum(1 for r in records if r["email_note"].startswith("duplicate"))
        text += f"; {made} emails generated, {len(records) - made} skipped, {dupes} duplicate addresses"
    return text


# ---- reading / writing ----------------------------------------------------

def _row(values):
    return {field: str(values.get(field) or "") for field in ROW_FIELDS}


def _header_columns(cells):
    """Map a CSV header row to field names, or None if the row isn't a header."""
    columns = [HEADER_ALIASES.get(re.sub(r"[^a-z]", "", c.lower())) for c in cells]
    return columns if "name" in columns and all(columns) else None


def load_rows(path):
    """Read scraper output (JSON or CSV) into deduplicated row dicts."""
    raw = []
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON list of employees")
        for item in data:
            raw.append(_row(item) if isinstance(item, dict) else _row(dict(zip(ROW_FIELDS, item))))
    else:
        columns = ROW_FIELDS  # legacy files have no (or a short) header; default to positional order
        with open(path, encoding="utf-8-sig", newline="") as f:
            for cells in csv.reader(f):
                if not cells:
                    continue
                header = _header_columns(cells)
                if header:  # also swallows header rows repeated by older appended runs
                    columns = header
                    continue
                raw.append(_row(dict(zip(columns, cells))))

    # Key on profile URL when available (a later row replaces an earlier one, so the newest
    # headline wins); older files without URLs fall back to matching the whole row.
    unique = {}
    for row in raw:
        if row["name"].strip():
            unique[row["profile_url"] or tuple(row.values())] = row
    return list(unique.values())


def safe_cell(value):
    """Neutralize spreadsheet formula injection from scraped text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def record_cells(rec, columns):
    return [safe_cell(rec.get(key, "")) for _, key in columns]


def write_records(path, records):
    columns = csv_columns(bool(records) and "email" in records[0])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([header for header, _ in columns])
        writer.writerows(record_cells(rec, columns) for rec in records)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="linkedin-names", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="scraper JSON or CSV file")
    ap.add_argument("-o", "--output", required=True, metavar="CSV", help="file to write (overwritten)")
    ap.add_argument("-f", "--email-format", metavar="TEMPLATE", help='e.g. "{f}.{last}@example.com"')
    ap.add_argument("--review", action="store_true", help="print rows flagged for review")
    args = ap.parse_args(argv)

    if args.email_format:
        try:
            template_fields(args.email_format)
        except ValueError as exc:
            ap.error(str(exc))
    try:
        rows = load_rows(args.input)
    except (OSError, ValueError, UnicodeDecodeError) as exc:  # JSONDecodeError is a ValueError
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 1

    records = build_records(rows, args.email_format)
    try:
        write_records(args.output, records)
    except OSError as exc:
        print(f"error: cannot write {args.output}: {exc}", file=sys.stderr)
        return 1

    print(f"{summary(records, args.email_format)} -> {args.output}")
    if args.review:
        for r in records:
            if r["needs_review"]:
                print(f"  {r['raw_name']!r:60} -> {r['first']!r} | {r['middle']!r} | {r['last']!r}  [{r['review_reason']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
