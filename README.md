# SQL Data Anonymizer

A Python command-line program that anonymizes personal information in a MySQL
dump file. It reads a `.sql` file containing `CREATE TABLE` and `INSERT`
statements and writes a new `.sql` file where every name, address, email
address, and phone number has been replaced with realistic, consistent,
one-way synthetic data. Everything else in the file (table structures, IDs,
amounts, product names, comments, formatting) is left unchanged.

## Language and technologies

- Python 3.10+
- Standard library: `re`, `argparse`, `random`
- Third-party library: [Faker](https://faker.readthedocs.io/) for realistic
  synthetic names and addresses
- `unittest` (standard library) for the test suite
- SQLite (via the standard-library `sqlite3` module) is used by the tests to
  prove that both the original and the anonymized SQL still load into a real
  database with identical row counts

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python3 anonymizer.py original.sql anonymized.sql
```

- Argument 1: input SQL file (default `original.sql`)
- Argument 2: output SQL file (default `anonymized.sql`)
- Optional `--seed N`: fixes the random generator so repeated runs produce
  identical output (default 42). This only makes runs reproducible; it does
  not make anonymization reversible.

## Expected input

A MySQL export containing `CREATE TABLE` and `INSERT INTO ... VALUES`
statements. The program handles:

- Multi-row `INSERT ... VALUES (...), (...), (...);`
- Explicit column lists: `INSERT INTO t (a, b) VALUES ...`
- Strings with escaped apostrophes (`'O''Brien'`)
- Numbers, `NULL`, and other non-string values (left untouched)

## Generated output

A new SQL file with the same statements, structure, comments, and row count,
but with all personal data replaced. For example:

```sql
-- before
(101, 'John Smith', '123 Main Street, Minneapolis, MN 55401',
 'john.smith@gmail.com', '612-555-1234')

-- after
(101, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563',
 'danielle.johnson@example.com', '104-332-1819')
```

No mapping file is written. The anonymization is one-way by design.

## Anonymization strategy

The assignment requires realistic, consistent, one-way synthetic data. That
rules out most classical techniques:

- **Data masking** (`John Smith` -> `XXXX`): rejected. The assignment
  explicitly says masked output is not useful test data.
- **Hashing** (`john.smith@gmail.com` -> `a94f3c...`): rejected. Hashes are
  irreversible, which is good, but they are not realistic values and break
  email/phone formats.
- **Tokenization / pseudonymization**: rejected. Both keep a reversible link
  to the original (a token vault or mapping table), and the assignment
  forbids producing a mapping.
- **Synthetic data generation**: chosen. Every distinct original value is
  replaced by a newly generated realistic value from Faker (names, addresses)
  or a format-preserving generator (emails, phones). The link from synthetic
  back to original exists only in memory during the run and is never stored,
  which makes the result one-way.

So the strategy is: consistent synthetic substitution, driven by parsing the
SQL rather than blind find-and-replace.

### How fields are identified

1. `CREATE TABLE` statements are parsed to learn each table's column names.
2. Column-name heuristics classify personal-data columns:
   - contains `email` -> email
   - contains `phone`, `mobile`, `tel`, `fax` -> phone
   - contains `address`, `addr`, `street` -> address
   - contains `name` -> name, except non-personal names (`product_name`,
     `username`, `file_name`, etc., which are excluded on purpose)
3. `INSERT` values are parsed with a small string-aware tokenizer and matched
   to their columns.
4. Independent of columns, a regular expression finds email addresses inside
   any string literal, so an email buried in a free-text notes column is
   still anonymized (and mapped consistently with the rest of the file).

### How synthetic data is generated

- **Names**: Faker first + last name pairs.
- **Addresses**: Faker US-style addresses, flattened to one line.
- **Emails**: derived from the synthetic name of the same record
  (`john.smith@gmail.com` -> `danielle.johnson@example.com`) so the data
  stays internally believable. Original domains are mapped to reserved
  documentation domains (`example.com`, `example.org`, `example.net`,
  RFC 2606) which can never belong to a real person.
- **Phones**: every digit is replaced with a random digit while all
  punctuation and spacing stay in place, so `612-555-1234` and
  `(952) 555-7710` keep their original shapes.
- Every generated value is checked so it never collides with another
  synthetic value or with any original value in the file.

### How consistency is maintained

Two passes over the file. Pass A collects every distinct original name,
address, email, and phone and records which name appeared in the same row as
each email. It then builds exactly one replacement per distinct original
value. Pass B applies those replacements, so `John Smith` becomes the same
synthetic name in `customers`, `orders`, `contacts`, and `shipping`, and the
matching email becomes the same derived synthetic address everywhere,
including inside free text. Consistency is a property of the map, not of any
single statement, which is what keeps cross-table relationships intact.

### How SQL structure is preserved

Replacements are applied by character span inside the original file text.
Only string literals in classified columns (or string literals containing an
email) are rewritten. Numbers, `NULL`s, keywords, punctuation, comments, and
whitespace are never touched, so the output remains valid SQL. New string
values are re-escaped (`'` -> `''`) before being written.

## Testing

The suite in `test_anonymizer.py` (14 tests, `python3 -m unittest -v`)
demonstrates every requirement:

- names, addresses, emails, and phones are all anonymized
- no original PII string survives anywhere in the output
- repeated values map to one consistent replacement (within and across tables)
- synthetic emails are syntactically valid and derived from synthetic names
- synthetic phones keep their punctuation format
- both SQL files load into a real SQLite database with identical row counts
- non-sensitive values (IDs, prices, product names, notes without PII) are
  byte-identical
- apostrophe names (`O'Brien`) round-trip correctly
- output is deterministic for a fixed seed, and no mapping file is produced

Full captured output is in `TESTING.md`.

## Important design decisions

- **Parse, don't regex the structure.** SQL strings can contain commas,
  parentheses, and semicolons, so values are extracted with a tokenizer that
  understands quoted strings instead of splitting on punctuation.
- **Column names over value guessing.** Names and addresses have no reliable
  syntax, so classification trusts `CREATE TABLE` column names. Emails and
  phones do have reliable syntax, so emails additionally get a regex
  catch-all everywhere.
- **Phones are format-preserving substitutions** rather than Faker phone
  numbers, so exotic formats in the input stay exotic in the output.
- **Example domains for emails** guarantee no synthetic address can
  accidentally belong to a real mailbox.
- **Fixed seed by default** so a submitted run can be reproduced exactly.

## Known limitations

- Column classification is heuristic. A personal-data column with an
  unusual name (for example `c_field1`) will not be classified, though an
  email inside it is still caught by the regex.
- Phone replacement is only applied in phone-classified columns; a phone
  number embedded in free text is left alone to avoid mangling IDs and other
  digit strings.
- Only single-column full addresses are handled; separate city/state/zip
  columns are outside the four required categories and are left unchanged.
- `INSERT` statements whose value count does not match the known column
  count fall back to the regex email catch-all only.
- Text that merely looks like SQL inside comments or string literals could
  confuse the parser; dumps with heavy procedural SQL (triggers, procedures)
  are out of scope.
