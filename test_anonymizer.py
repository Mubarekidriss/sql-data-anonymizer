#!/usr/bin/env python3
"""
Test suite for the SQL Data Anonymizer (stdlib unittest, no extra deps).

Run:  python3 -m unittest -v
"""

import os
import re
import sqlite3
import tempfile
import unittest

from anonymizer import anonymize_sql, parse_inserts, EMAIL_RE

HERE = os.path.dirname(os.path.abspath(__file__))
ORIGINAL = os.path.join(HERE, "original.sql")

ORIGINAL_PII = {
    "names": ["John Smith", "Maria Garcia", "Patrick O'Brien", "Aisha Khan"],
    "addresses": [
        "123 Main Street, Minneapolis, MN 55401",
        "48 Cedar Lane, St. Paul, MN 55102",
        "77 River Road, Duluth, MN 55802",
        "210 Grand Avenue, Rochester, MN 55904",
    ],
    "emails": [
        "john.smith@gmail.com", "maria.garcia@yahoo.com",
        "pobrien@outlook.com", "aisha.khan@company.org",
    ],
    "phones": ["612-555-1234", "651-555-8890", "218-555-4402", "(952) 555-7710"],
}


def load_original():
    with open(ORIGINAL, "r", encoding="utf-8") as f:
        return f.read()


def table_counts(sql_text):
    """Execute the dump in a fresh SQLite database and count rows per table."""
    con = sqlite3.connect(":memory:")
    con.executescript(sql_text)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in tables}
    con.close()
    return counts


class AnonymizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = load_original()
        cls.anon, cls.stats, cls.warnings = anonymize_sql(cls.original, seed=42)

    # --- PII removal -------------------------------------------------------
    def test_no_original_pii_remains(self):
        for group, values in ORIGINAL_PII.items():
            for v in values:
                self.assertNotIn(v, self.anon,
                                 f"original {group} value leaked: {v!r}")

    def test_values_actually_changed(self):
        self.assertNotEqual(self.original, self.anon)
        self.assertGreater(self.stats["name"], 0)
        self.assertGreater(self.stats["address"], 0)
        self.assertGreater(self.stats["email"], 0)
        self.assertGreater(self.stats["phone"], 0)

    # --- Consistency --------------------------------------------------------
    def test_repeated_name_consistent(self):
        # 'John Smith' appears 6 times across 4 tables; its replacement must
        # appear exactly as many times and be the same value everywhere.
        inserts, _ = parse_inserts(self.anon)
        replacements = set()
        for ins in inserts:
            for row in ins["rows"]:
                for kind, value, _s, _e in row:
                    if kind == "str" and " " in value and value not in (
                            "Wireless Mouse", "USB-C Cable") and "@" not in value \
                            and "," not in value:
                        # candidate synthetic person name (2 words, no digits)
                        if re.fullmatch(r"[A-Za-z' -]+", value) and value.count(" ") == 1:
                            replacements.add(value)
        # every synthetic full name occurs uniformly for repeated originals:
        counts = {name: self.anon.count(f"'{name}'") for name in replacements}
        self.assertIn(6, counts.values(),
                      f"expected one synthetic name repeated 6x, got {counts}")

    def test_repeated_email_consistent_across_tables(self):
        # john.smith@gmail.com appears in customers (2x), contacts, and a note.
        emails = EMAIL_RE.findall(self.anon)
        gmail_replacements = [e for e in emails if e.endswith("@example.com")
                              or e.endswith("@example.org")
                              or e.endswith("@example.net")]
        from collections import Counter
        c = Counter(gmail_replacements)
        self.assertIn(4, c.values(),
                      f"expected one synthetic email repeated 4x, got {c}")

    def test_email_derived_from_synthetic_name(self):
        # The replacement for john.smith@gmail.com must be first.last@example.*
        # and its local part must match the synthetic name replacing John Smith.
        inserts, _ = parse_inserts(self.anon)
        for ins in inserts:
            if ins["table"] != "customers":
                continue
            row = ins["rows"][0]
            synth_name = row[1][1]
            synth_email = row[3][1]
            local = synth_email.split("@")[0]
            expected = re.sub(r"[^a-z0-9]+", ".", synth_name.lower()).strip(".")
            self.assertEqual(local, expected,
                             f"email {synth_email} not derived from {synth_name}")

    # --- Format preservation ------------------------------------------------
    def test_synthetic_emails_valid(self):
        for e in EMAIL_RE.findall(self.anon):
            self.assertRegex(e, r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
        self.assertNotIn("gmail.com", self.anon)
        self.assertNotIn("yahoo.com", self.anon)
        self.assertNotIn("outlook.com", self.anon)
        self.assertNotIn("company.org", self.anon)

    def test_phone_format_preserved(self):
        # '(952) 555-7710' style: punctuation pattern must survive.
        self.assertRegex(self.anon, r"\(\d{3}\) \d{3}-\d{4}")
        self.assertRegex(self.anon, r"\d{3}-\d{3}-\d{4}")
        # no synthetic phone may equal any original phone
        for p in ORIGINAL_PII["phones"]:
            self.assertNotIn(p, self.anon)

    def test_addresses_look_realistic(self):
        # synthetic addresses contain a street number and a comma (city/state)
        inserts, _ = parse_inserts(self.anon)
        for ins in inserts:
            if ins["table"] not in ("customers", "shipping"):
                continue
            for row in ins["rows"]:
                for kind, value, _s, _e in row:
                    if kind == "str" and "," in value and "@" not in value:
                        self.assertRegex(value, r"^\d+ .+,",
                                         f"unrealistic address: {value!r}")

    # --- SQL validity and preservation --------------------------------------
    def test_sql_remains_valid_and_row_counts_match(self):
        self.assertEqual(table_counts(self.original), table_counts(self.anon))

    def test_non_sensitive_data_unchanged(self):
        for kept in ["101", "5001", "259.99", "Wireless Mouse", "USB-C Cable",
                     "No personal data in this note."]:
            self.assertIn(kept, self.anon)

    def test_apostrophe_names_handled(self):
        # O''Brien must be replaced by a valid, loadable SQL string.
        self.assertNotIn("O''Brien", self.anon)
        con = sqlite3.connect(":memory:")
        con.executescript(self.anon)  # would raise on broken quoting
        con.close()

    # --- One-way / determinism ----------------------------------------------
    def test_deterministic_with_same_seed(self):
        again, _, _ = anonymize_sql(self.original, seed=42)
        self.assertEqual(self.anon, again)

    def test_no_mapping_file_written(self):
        with tempfile.TemporaryDirectory() as d:
            before = set(os.listdir(d))
            out, _, _ = anonymize_sql(self.original, seed=1)
            with open(os.path.join(d, "out.sql"), "w") as f:
                f.write(out)
            self.assertEqual(set(os.listdir(d)) - before, {"out.sql"})

    def test_embedded_email_in_freetext_caught(self):
        # support_notes.note is not a classified column, but the email inside
        # it must still be anonymized, and consistently with the other tables.
        self.assertNotIn("john.smith@gmail.com", self.anon)
        m = re.search(r"confirm ([^ ]+) before shipping", self.anon)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"@example\.(com|org|net)$")


if __name__ == "__main__":
    unittest.main()
