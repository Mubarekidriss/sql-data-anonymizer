#!/usr/bin/env python3
"""
SQL Data Anonymizer (ICS 499)

Reads a MySQL dump containing CREATE TABLE and INSERT statements and writes a
new SQL file in which names, addresses, email addresses, and phone numbers are
replaced with realistic, consistent, one-way synthetic data.

Strategy (see README.md for the full design discussion):
  * CREATE TABLE statements are parsed to learn column names per table.
  * Column-name heuristics classify personal-data columns (name / address /
    email / phone). Non-personal "name" columns such as product_name or
    username are deliberately excluded.
  * INSERT ... VALUES tuples are parsed with a small string-aware tokenizer
    that understands '' escaped quotes, NULLs, numbers, and multi-row inserts.
  * Emails are additionally caught by regex anywhere inside string literals,
    so PII hiding in free-text columns is still anonymized.
  * Consistency: every distinct original value gets exactly one synthetic
    replacement, reused across the whole file and across all tables.
  * Coherence: when a row contains both a name and an email, the synthetic
    email is derived from the synthetic name (michael.anderson@example.com).
  * Format preservation: phone replacements keep the original separators and
    punctuation; emails stay syntactically valid on reserved example domains.
  * One-way: no mapping file is ever written. A fixed --seed only makes runs
    reproducible; it cannot recover original values.
"""

import argparse
import random
import re
import sys

from faker import Faker

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+[`\"]?(\w+)[`\"]?\s*(?:\(([^)]*)\))?\s*VALUES", re.IGNORECASE
)
CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(", re.IGNORECASE
)

# "name" columns that do NOT hold personal data and must stay untouched.
NAME_EXCLUDES = ("user", "product", "item", "file", "table", "column",
                 "schema", "category", "db")

# Reserved documentation domains (RFC 2606): guaranteed not to belong to anyone.
EXAMPLE_DOMAINS = ["example.com", "example.org", "example.net"]

CONSTRAINT_STARTERS = {"PRIMARY", "FOREIGN", "UNIQUE", "KEY", "INDEX",
                       "CONSTRAINT", "CHECK"}


def classify_column(column):
    """Classify a column as 'name', 'first_name', 'last_name', 'address',
    'email', 'phone', or None (not personal data)."""
    c = column.lower().strip("`\"")
    if "email" in c or "e_mail" in c:
        return "email"
    if any(k in c for k in ("phone", "mobile", "fax", "tel")):
        return "phone"
    if any(k in c for k in ("address", "addr", "street")):
        return "address"
    if "name" in c and not any(k in c for k in NAME_EXCLUDES):
        if "first" in c:
            return "first_name"
        if "last" in c:
            return "last_name"
        return "name"
    return None


def parse_string(sql, i):
    """Parse a '...' SQL string literal starting at sql[i] == "'".
    Handles '' escaped quotes. Returns (value, end_index_exclusive)."""
    j = i + 1
    out = []
    n = len(sql)
    while j < n:
        c = sql[j]
        if c == "'":
            if j + 1 < n and sql[j + 1] == "'":
                out.append("'")
                j += 2
                continue
            return "".join(out), j + 1
        out.append(c)
        j += 1
    raise ValueError("unterminated string literal")


def parse_value(sql, i):
    """Parse one value inside a VALUES tuple.
    Returns ((kind, value, span_start, span_end), next_index)."""
    n = len(sql)
    while i < n and sql[i] in " \t\r\n":
        i += 1
    if i < n and sql[i] == "'":
        value, end = parse_string(sql, i)
        return ("str", value, i, end), end
    j = i
    while j < n and sql[j] not in ",)":
        j += 1
    return ("raw", sql[i:j].strip(), i, j), j


def parse_create_tables(sql):
    """Return {table_name: [column, ...]} from CREATE TABLE statements."""
    tables = {}
    for m in CREATE_RE.finditer(sql):
        table = m.group(1)
        i = m.end()
        depth = 1
        start = i
        n = len(sql)
        while i < n and depth:
            if sql[i] == "(":
                depth += 1
            elif sql[i] == ")":
                depth -= 1
            i += 1
        body = sql[start:i - 1]
        # split column definitions on top-level commas
        parts, d, s = [], 0, 0
        for k, ch in enumerate(body):
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
            elif ch == "," and d == 0:
                parts.append(body[s:k])
                s = k + 1
        parts.append(body[s:])
        cols = []
        for part in parts:
            tokens = part.strip().split()
            if not tokens:
                continue
            if tokens[0].upper() in CONSTRAINT_STARTERS:
                continue
            cols.append(tokens[0].strip("`\"'"))
        tables[table] = cols
    return tables


def parse_inserts(sql):
    """Parse INSERT statements. Returns (inserts, warnings).
    Each insert: {"table", "columns", "rows": [[(kind, value, span), ...]],
                  "stmt_end"}."""
    inserts = []
    warnings = []
    create_map = parse_create_tables(sql)
    pos = 0
    n = len(sql)
    while True:
        m = INSERT_RE.search(sql, pos)
        if not m:
            break
        table = m.group(1)
        if m.group(2):
            columns = [c.strip().strip("`\"'") for c in m.group(2).split(",")]
        else:
            columns = create_map.get(table, [])
        i = m.end()
        rows = []
        stmt_end = None
        ok = True
        while True:
            while i < n and sql[i] in " \t\r\n":
                i += 1
            if i >= n or sql[i] != "(":
                ok = False
                break
            i += 1
            row = []
            while True:
                val, i = parse_value(sql, i)
                row.append(val)
                while i < n and sql[i] in " \t\r\n":
                    i += 1
                if i < n and sql[i] == ",":
                    i += 1
                    continue
                if i < n and sql[i] == ")":
                    i += 1
                    break
                ok = False
                break
            if not ok:
                break
            rows.append(row)
            while i < n and sql[i] in " \t\r\n":
                i += 1
            if i < n and sql[i] == ",":
                i += 1
                continue
            if i < n and sql[i] == ";":
                stmt_end = i + 1
                i += 1
                break
            ok = False
            break
        if not ok or stmt_end is None:
            warnings.append(
                f"skipped unparseable INSERT into '{table}' near offset {m.start()}"
            )
            pos = m.end()
            continue
        if columns and any(len(r) != len(columns) for r in rows):
            warnings.append(
                f"INSERT into '{table}': value count does not match column "
                f"count; only regex email catch-all applied there"
            )
        inserts.append({"table": table, "columns": columns,
                        "rows": rows, "stmt_end": stmt_end})
        pos = stmt_end
    return inserts, warnings


def sql_quote(value):
    return "'" + value.replace("'", "''") + "'"


def anonymize_sql(sql_text, seed=42):
    """Anonymize a SQL dump. Returns (new_sql_text, stats, warnings)."""
    rng = random.Random(seed)
    fake = Faker()
    fake.seed_instance(seed)

    inserts, warnings = parse_inserts(sql_text)

    # ----- Pass A: collect original values and name<->email associations ----
    originals = {"name": set(), "first_name": set(), "last_name": set(),
                 "address": set(), "email": set(), "phone": set()}
    email_assoc = {}          # original email -> original full name (if seen together)
    encounter_order = []      # (class, value) in first-appearance order
    seen_encounter = set()

    def record(cls, value):
        originals[cls].add(value)
        key = (cls, value)
        if key not in seen_encounter:
            seen_encounter.add(key)
            encounter_order.append(key)

    for ins in inserts:
        cols = ins["columns"]
        classes = [classify_column(c) for c in cols]
        for row in ins["rows"]:
            row_name = None
            row_emails = []
            aligned = len(row) == len(cols)
            for idx, (kind, value, _s, _e) in enumerate(row):
                if kind != "str":
                    continue
                cls = classes[idx] if aligned else None
                if cls in originals:
                    record(cls, value)
                    if cls == "name":
                        row_name = value
                    elif cls == "email":
                        row_emails.append(value)
                if cls != "email":
                    for em in EMAIL_RE.findall(value):
                        record("email", em)
                        row_emails.append(em)
            for em in row_emails:
                if row_name and em not in email_assoc:
                    email_assoc[em] = row_name

    # ----- Build the one-way replacement maps -------------------------------
    name_map, first_map, last_map = {}, {}, {}
    address_map, email_map, phone_map = {}, {}, {}
    used = {"name": set(), "first_name": set(), "last_name": set(),
            "address": set(), "phone": set()}
    used_email_ids = set()
    domain_map = {}

    def fresh_name():
        while True:
            v = f"{fake.first_name()} {fake.last_name()}"
            if v not in used["name"] and v not in originals["name"]:
                used["name"].add(v)
                return v

    def fresh_part(kind, gen):
        while True:
            v = gen()
            if v not in used[kind] and v not in originals[kind]:
                used[kind].add(v)
                return v

    def fresh_address():
        while True:
            v = fake.address().replace("\n", ", ")
            if v not in used["address"] and v not in originals["address"]:
                used["address"].add(v)
                return v

    def fresh_phone(orig):
        digits = "0123456789"
        while True:
            v = "".join(rng.choice(digits) if c.isdigit() else c for c in orig)
            if (v != orig and v not in used["phone"]
                    and v not in originals["phone"]):
                used["phone"].add(v)
                return v

    def mapped_domain(orig_domain):
        d = orig_domain.lower()
        if d not in domain_map:
            domain_map[d] = EXAMPLE_DOMAINS[len(domain_map) % len(EXAMPLE_DOMAINS)]
        return domain_map[d]

    def fresh_email(orig):
        orig_domain = orig.split("@", 1)[1] if "@" in orig else "example.com"
        domain = mapped_domain(orig_domain)
        assoc = email_assoc.get(orig)
        if assoc and assoc in name_map:
            base = name_map[assoc]
        elif assoc:
            base = assoc  # name not classified anywhere; still derive below
            base = fresh_name() if base == assoc else base
        else:
            base = f"{fake.first_name()} {fake.last_name()}"
        local = re.sub(r"[^a-z0-9]+", ".", base.lower()).strip(".") or "user"
        candidate, k = local, 1
        while (candidate, domain) in used_email_ids:
            k += 1
            candidate = f"{local}{k}"
        used_email_ids.add((candidate, domain))
        return f"{candidate}@{domain}"

    for cls, value in encounter_order:
        if cls == "name":
            name_map[value] = fresh_name()
        elif cls == "first_name":
            first_map[value] = fresh_part("first_name", fake.first_name)
        elif cls == "last_name":
            last_map[value] = fresh_part("last_name", fake.last_name)
        elif cls == "address":
            address_map[value] = fresh_address()
        elif cls == "phone":
            phone_map[value] = fresh_phone(value)
        elif cls == "email":
            email_map[value] = fresh_email(value)

    # ----- Pass B: build span replacements ----------------------------------
    replacements = []
    stats = {"name": 0, "first_name": 0, "last_name": 0, "address": 0,
             "email": 0, "phone": 0, "rows_processed": 0,
             "statements_processed": len(inserts)}

    for ins in inserts:
        cols = ins["columns"]
        classes = [classify_column(c) for c in cols]
        for row in ins["rows"]:
            aligned = len(row) == len(cols)
            stats["rows_processed"] += 1
            for idx, (kind, value, s, e) in enumerate(row):
                if kind != "str":
                    continue
                cls = classes[idx] if aligned else None
                new_value = None
                if cls == "name":
                    new_value = name_map[value]
                elif cls == "first_name":
                    new_value = first_map[value]
                elif cls == "last_name":
                    new_value = last_map[value]
                elif cls == "address":
                    new_value = address_map[value]
                elif cls == "phone":
                    new_value = phone_map[value]
                elif cls == "email":
                    new_value = email_map[value]
                elif EMAIL_RE.search(value):
                    new_value = EMAIL_RE.sub(
                        lambda mm: email_map[mm.group(0)], value)
                    cls = "email"
                if new_value is not None:
                    replacements.append((s, e, sql_quote(new_value)))
                    stats[cls] += 1

    for s, e, text in sorted(replacements, reverse=True):
        sql_text = sql_text[:s] + text + sql_text[e:]

    stats["distinct_values"] = {
        "names": len(name_map) + len(first_map) + len(last_map),
        "addresses": len(address_map),
        "emails": len(email_map),
        "phones": len(phone_map),
    }
    return sql_text, stats, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Anonymize PII (names, addresses, emails, phones) in a "
                    "MySQL dump with consistent realistic synthetic data.")
    parser.add_argument("input", nargs="?", default="original.sql",
                        help="input SQL file (default: original.sql)")
    parser.add_argument("output", nargs="?", default="anonymized.sql",
                        help="output SQL file (default: anonymized.sql)")
    parser.add_argument("--seed", type=int, default=42,
                        help="seed for reproducible synthetic data (default 42)")
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        sql_text = f.read()

    new_text, stats, warnings = anonymize_sql(sql_text, seed=args.seed)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(new_text)

    print(f"Anonymized {args.input} -> {args.output}")
    print(f"  INSERT statements processed : {stats['statements_processed']}")
    print(f"  rows processed              : {stats['rows_processed']}")
    print(f"  values replaced             : names={stats['name'] + stats['first_name'] + stats['last_name']} "
          f"addresses={stats['address']} emails={stats['email']} phones={stats['phone']}")
    d = stats["distinct_values"]
    print(f"  distinct originals mapped   : names={d['names']} addresses={d['addresses']} "
          f"emails={d['emails']} phones={d['phones']}")
    print("  mapping file written        : none (one-way anonymization)")
    for w in warnings:
        print(f"  WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
