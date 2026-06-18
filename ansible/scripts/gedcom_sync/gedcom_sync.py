"""Sync Webtrees MariaDB individuals/families into PocketBase persons/couples.

Idempotent (keyed on persons.gedcom_id), fill-blanks-only (never overwrites
edits made in the reunion SPA), redacts living people, supports --dry-run.

Heavy I/O deps (PyMySQL, requests) are imported lazily so the pure parsing /
mapping functions remain unit-testable without them installed.
"""

import argparse
import os
import sys


# ── GEDCOM parsing ───────────────────────────────────────────────────────────
_MONTHS = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05",
           "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10",
           "NOV": "11", "DEC": "12"}


def parse_lines(gedcom_text):
    """Parse a GEDCOM record fragment into (level, tag, value) tuples.

    For a record header like "0 @I1@ INDI" the tag is the structure tag (INDI)
    and the value is the xref (@I1@).
    """
    out = []
    for raw in gedcom_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        level = int(parts[0])
        rest = parts[1] if len(parts) > 1 else ""
        if rest.startswith("@") and " " in rest:
            xref, tag_and_val = rest.split(" ", 1)
            tv = tag_and_val.split(" ", 1)
            tag = tv[0]
            out.append((level, tag, xref))
        else:
            tv = rest.split(" ", 1)
            tag = tv[0] if tv[0] else ""
            value = tv[1] if len(tv) > 1 else ""
            out.append((level, tag, value))
    return out


def normalize_date(gedcom_date):
    """'3 MAR 1947'->'1947-03-03'; '1947'->'1947'; 'MAR 1947'->'1947-03'.
    Drops qualifiers (ABT/EST/BEF/AFT/...). Returns '' if no 4-digit year."""
    if not gedcom_date:
        return ""
    toks = [t for t in gedcom_date.replace(",", " ").split()
            if t.upper() not in ("ABT", "EST", "BEF", "AFT", "CAL",
                                 "FROM", "TO", "BET", "AND")]
    day = month = year = ""
    for t in toks:
        tu = t.upper()
        if tu in _MONTHS:
            month = _MONTHS[tu]
        elif t.isdigit() and len(t) == 4:
            year = t
        elif t.isdigit() and len(t) <= 2:
            day = t.zfill(2)
    if not year:
        return ""
    if month and day:
        return f"{year}-{month}-{day}"
    if month:
        return f"{year}-{month}"
    return year


def _sub_date(lines, start_idx):
    """DATE value among the deeper-level lines following a fact at start_idx."""
    base_level = lines[start_idx][0]
    for level, tag, value in lines[start_idx + 1:]:
        if level <= base_level:
            break
        if tag == "DATE":
            return value
    return ""


def parse_individual(gedcom_text):
    lines = parse_lines(gedcom_text)
    given = family = ""
    gender = "unknown"
    birth = death = ""
    for i, (level, tag, value) in enumerate(lines):
        if level == 1 and tag == "NAME":
            if "/" in value:
                pre, sur = value.split("/", 1)
                given = pre.strip()
                family = sur.replace("/", "").strip()
            else:
                given = value.strip()
        elif level == 1 and tag == "SEX":
            gender = {"M": "male", "F": "female"}.get(value.strip().upper(), "other")
        elif level == 1 and tag == "BIRT":
            birth = normalize_date(_sub_date(lines, i))
        elif level == 1 and tag == "DEAT":
            death = normalize_date(_sub_date(lines, i))
    display = " ".join(p for p in (given, family) if p).strip() or "Unknown"
    out = {"given_name": given, "family_name": family,
           "display_name": display, "gender": gender}
    if birth:
        out["birth_date"] = birth
    if death:
        out["death_date"] = death
    return out


def parse_family(gedcom_text):
    lines = parse_lines(gedcom_text)
    husb = wife = married = ""
    children = []
    for i, (level, tag, value) in enumerate(lines):
        if level == 1 and tag == "HUSB":
            husb = value.strip()
        elif level == 1 and tag == "WIFE":
            wife = value.strip()
        elif level == 1 and tag == "CHIL":
            children.append(value.strip())
        elif level == 1 and tag == "MARR":
            married = normalize_date(_sub_date(lines, i))
    return {"husb": husb, "wife": wife, "children": children,
            "married_date": married}


# ── Privacy + merge logic ────────────────────────────────────────────────────
def apply_privacy(fields, now_year):
    """Decide living vs deceased and redact living people's sensitive fields.
    Living = no death_date AND (no birth year OR birth within 100 years)."""
    death = fields.get("death_date", "")
    birth = fields.get("birth_date", "")
    birth_year = int(birth[:4]) if birth[:4].isdigit() else None
    if death:
        living = False
    elif birth_year is None:
        living = True
    else:
        living = (now_year - birth_year) < 100
    fields["living"] = living
    if living:
        fields["birth_date"] = ""
        fields["bio"] = ""
    return fields


def fill_blanks(existing, incoming):
    """Return only incoming fields whose existing value is empty/missing.
    Protects edits already made in the SPA (PocketBase is source of truth)."""
    patch = {}
    for k, v in incoming.items():
        cur = existing.get(k, "")
        # "" / None are blank everywhere; "unknown" is the gender placeholder
        # default, so a known incoming gender should fill it.
        blank = cur in ("", None) or (k == "gender" and cur == "unknown")
        if blank and v not in ("", None) and not (k == "gender" and v == "unknown"):
            patch[k] = v
    return patch


def plan_person_write(existing, gedcom_id, mapped):
    """Decide how to write a person. mapped already has living + redaction.
    Returns (action, fields) with action in {create, update, noop}."""
    if existing is None:
        fields = dict(mapped)
        fields["gedcom_id"] = gedcom_id
        return "create", fields
    patch = fill_blanks(existing, mapped)
    patch.pop("living", None)  # SPA owns the living flag on existing records
    if patch:
        return "update", patch
    return "noop", {}


# ── I/O: Webtrees MariaDB reader ─────────────────────────────────────────────
def fetch_webtrees(db_host, db_name, db_user, db_pass, prefix="wt_"):
    """Return (individuals, families) dicts of {xref: gedcom_text}. xref is @...@."""
    import pymysql
    conn = pymysql.connect(host=db_host, user=db_user, password=db_pass,
                           database=db_name, charset="utf8mb4",
                           cursorclass=pymysql.cursors.Cursor)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT i_id, i_gedcom FROM {prefix}individuals")
            individuals = {f"@{row[0]}@": row[1] for row in cur.fetchall()}
            cur.execute(f"SELECT f_id, f_gedcom FROM {prefix}families")
            families = {f"@{row[0]}@": row[1] for row in cur.fetchall()}
        return individuals, families
    finally:
        conn.close()


# ── I/O: PocketBase client ───────────────────────────────────────────────────
class PB:
    def __init__(self, base, token):
        self.base = base.rstrip("/")
        self.h = {"Authorization": token, "Content-Type": "application/json"}

    @classmethod
    def login(cls, base, identity, password):
        import requests
        r = requests.post(f"{base.rstrip('/')}/api/admins/auth-with-password",
                          json={"identity": identity, "password": password},
                          timeout=15)
        r.raise_for_status()
        return cls(base, r.json()["token"])

    def find_by_gedcom(self, gedcom_id):
        import requests
        r = requests.get(f"{self.base}/api/collections/persons/records",
                         params={"perPage": 1, "filter": f'(gedcom_id="{gedcom_id}")'},
                         headers=self.h, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        return items[0] if items else None

    def create_person(self, fields):
        import requests
        r = requests.post(f"{self.base}/api/collections/persons/records",
                          json=fields, headers=self.h, timeout=15)
        r.raise_for_status()
        return r.json()

    def patch_person(self, pid, fields):
        import requests
        r = requests.patch(f"{self.base}/api/collections/persons/records/{pid}",
                           json=fields, headers=self.h, timeout=15)
        r.raise_for_status()
        return r.json()

    def find_couple(self, a_id, b_id):
        import requests
        flt = (f'((partner_a="{a_id}" && partner_b="{b_id}") || '
               f'(partner_a="{b_id}" && partner_b="{a_id}"))')
        r = requests.get(f"{self.base}/api/collections/couples/records",
                         params={"perPage": 1, "filter": flt},
                         headers=self.h, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        return items[0] if items else None

    def create_couple(self, fields):
        import requests
        r = requests.post(f"{self.base}/api/collections/couples/records",
                          json=fields, headers=self.h, timeout=15)
        r.raise_for_status()
        return r.json()


# ── Orchestration ────────────────────────────────────────────────────────────
def build_person_fields(xref, individuals, now_year):
    mapped = parse_individual(individuals[xref])
    return apply_privacy(mapped, now_year=now_year)


def run(args):
    pb = PB.login(args.pb_url, args.admin_email, args.admin_password)
    individuals, families = fetch_webtrees(args.db_host, args.db_name,
                                           args.db_user, args.db_password)
    now_year = args.now_year
    counts = {"created": 0, "updated": 0, "noop": 0, "couples": 0, "redacted": 0}
    xref_to_pid = {}

    # Pass 1: upsert every individual as a person.
    for xref in individuals:
        mapped = build_person_fields(xref, individuals, now_year)
        if mapped.get("living"):
            counts["redacted"] += 1
        existing = pb.find_by_gedcom(xref)
        action, fields = plan_person_write(existing, xref, mapped)
        if args.dry_run:
            xref_to_pid[xref] = existing["id"] if existing else f"<new:{xref}>"
            if action == "noop":
                counts["noop"] += 1
            else:
                counts[action + "d" if action == "create" else "updated"] += 1
            continue
        if action == "create":
            rec = pb.create_person(fields)
            xref_to_pid[xref] = rec["id"]
            counts["created"] += 1
        elif action == "update":
            pb.patch_person(existing["id"], fields)
            xref_to_pid[xref] = existing["id"]
            counts["updated"] += 1
        else:
            xref_to_pid[xref] = existing["id"]
            counts["noop"] += 1

    # Pass 2: wire father/mother from families and create couples.
    for ftext in families.values():
        fam = parse_family(ftext)
        husb_pid = xref_to_pid.get(fam["husb"])
        wife_pid = xref_to_pid.get(fam["wife"])
        for child_xref in fam["children"]:
            child_pid = xref_to_pid.get(child_xref)
            if not child_pid or args.dry_run:
                continue
            existing = pb.find_by_gedcom(child_xref)
            patch = {}
            if husb_pid and not (existing or {}).get("father"):
                patch["father"] = husb_pid
            if wife_pid and not (existing or {}).get("mother"):
                patch["mother"] = wife_pid
            if patch:
                pb.patch_person(child_pid, patch)
        if husb_pid and wife_pid and not args.dry_run:
            if not pb.find_couple(husb_pid, wife_pid):
                fields = {"partner_a": husb_pid, "partner_b": wife_pid,
                          "status": "married"}
                if fam["married_date"]:
                    fields["married_date"] = fam["married_date"]
                pb.create_couple(fields)
                counts["couples"] += 1

    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sync Webtrees MariaDB -> PocketBase persons/couples")
    ap.add_argument("--pb-url", default=os.environ.get("PB_URL", "http://192.168.20.14:8094"))
    ap.add_argument("--admin-email", default=os.environ.get("PB_ADMIN_EMAIL"))
    ap.add_argument("--admin-password", default=os.environ.get("PB_ADMIN_PASSWORD"))
    ap.add_argument("--db-host", default=os.environ.get("WT_DB_HOST", "webtrees-db"))
    ap.add_argument("--db-name", default=os.environ.get("WT_DB_NAME", "webtrees"))
    ap.add_argument("--db-user", default=os.environ.get("WT_DB_USER", "webtrees"))
    ap.add_argument("--db-password", default=os.environ.get("WT_DB_PASSWORD"))
    ap.add_argument("--now-year", type=int, default=2026)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    missing = [n for n in ("admin_email", "admin_password", "db_password")
               if not getattr(args, n)]
    if missing:
        print(f"ERROR: missing required config: {missing}", file=sys.stderr)
        return 2
    counts = run(args)
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] created={counts['created']} updated={counts['updated']} "
          f"noop={counts['noop']} couples={counts['couples']} "
          f"redacted_living={counts['redacted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
