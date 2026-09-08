# Testing Evidence

Date: 2026-09-08 13:14 CDT
Environment: Python 3.10.12, Faker 40.38.0

## 1. Program run

```
Anonymized original.sql -> anonymized.sql
  INSERT statements processed : 6
  rows processed              : 16
  values replaced             : names=12 addresses=6 emails=8 phones=9
  distinct originals mapped   : names=4 addresses=4 emails=4 phones=4
  mapping file written        : none (one-way anonymization)
```

## 2. Unit test suite (python3 -m unittest -v)

```
test_addresses_look_realistic (test_anonymizer.AnonymizerTests) ... ok
test_apostrophe_names_handled (test_anonymizer.AnonymizerTests) ... ok
test_deterministic_with_same_seed (test_anonymizer.AnonymizerTests) ... ok
test_email_derived_from_synthetic_name (test_anonymizer.AnonymizerTests) ... ok
test_embedded_email_in_freetext_caught (test_anonymizer.AnonymizerTests) ... ok
test_no_mapping_file_written (test_anonymizer.AnonymizerTests) ... ok
test_no_original_pii_remains (test_anonymizer.AnonymizerTests) ... ok
test_non_sensitive_data_unchanged (test_anonymizer.AnonymizerTests) ... ok
test_phone_format_preserved (test_anonymizer.AnonymizerTests) ... ok
test_repeated_email_consistent_across_tables (test_anonymizer.AnonymizerTests) ... ok
test_repeated_name_consistent (test_anonymizer.AnonymizerTests) ... ok
test_sql_remains_valid_and_row_counts_match (test_anonymizer.AnonymizerTests) ... ok
test_synthetic_emails_valid (test_anonymizer.AnonymizerTests) ... ok
test_values_actually_changed (test_anonymizer.AnonymizerTests) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.025s

OK
```

## 3. Both SQL files load into a real database with identical row counts

```
original.sql   : {'contacts': 3, 'customers': 4, 'orders': 3, 'products': 2, 'shipping': 2, 'support_notes': 2}
anonymized.sql : {'contacts': 3, 'customers': 4, 'orders': 3, 'products': 2, 'shipping': 2, 'support_notes': 2}
row counts identical: True
```

## 4. Before / after sample (customers table)

Original:
```sql
INSERT INTO customers VALUES
(101, 'John Smith', '123 Main Street, Minneapolis, MN 55401', 'john.smith@gmail.com', '612-555-1234'),
(102, 'Maria Garcia', '48 Cedar Lane, St. Paul, MN 55102', 'maria.garcia@yahoo.com', '651-555-8890'),
(103, 'John Smith', '123 Main Street, Minneapolis, MN 55401', 'john.smith@gmail.com', '612-555-1234'),
(104, 'Patrick O''Brien', '77 River Road, Duluth, MN 55802', 'pobrien@outlook.com', '218-555-4402');
```

Anonymized:
```sql
INSERT INTO customers VALUES
(101, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563', 'danielle.johnson@example.com', '104-332-1819'),
(102, 'Jennifer Miles', '402 Peterson Drives Apt. 511, Davisstad, PA 35172', 'jennifer.miles@example.org', '600-133-8908'),
(103, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563', 'danielle.johnson@example.com', '104-332-1819'),
(104, 'Lindsay Blair', '84959 Janet Cape Apt. 413, South Joshuastad, GA 49021', 'lindsay.blair@example.net', '386-379-4026');
```

## 5. PII leak check (grep for every original PII value in the output)

```
gone: John Smith
gone: Maria Garcia
gone: Patrick O'Brien
gone: Aisha Khan
gone: 123 Main Street
gone: 48 Cedar Lane
gone: 77 River Road
gone: 210 Grand Avenue
gone: john.smith@gmail.com
gone: maria.garcia@yahoo.com
gone: pobrien@outlook.com
gone: aisha.khan@company.org
gone: 612-555-1234
gone: 651-555-8890
gone: 218-555-4402
gone: (952) 555-7710
gone: gmail.com
gone: yahoo.com
gone: outlook.com
gone: company.org
```
