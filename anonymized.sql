-- Sample production export containing PII (test fixture for the anonymizer)
-- Covers: multi-row inserts, explicit column lists, repeated PII across
-- tables, apostrophes in names, varied phone formats, and non-PII "name"
-- columns that must NOT be touched.

CREATE TABLE customers (
    customer_id INT,
    name VARCHAR(100),
    address VARCHAR(200),
    email VARCHAR(100),
    phone VARCHAR(30)
);

INSERT INTO customers VALUES
(101, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563', 'danielle.johnson@example.com', '104-332-1819'),
(102, 'Jennifer Miles', '402 Peterson Drives Apt. 511, Davisstad, PA 35172', 'jennifer.miles@example.org', '600-133-8908'),
(103, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563', 'danielle.johnson@example.com', '104-332-1819'),
(104, 'Lindsay Blair', '84959 Janet Cape Apt. 413, South Joshuastad, GA 49021', 'lindsay.blair@example.net', '386-379-4026');

CREATE TABLE orders (
    order_id INT,
    customer_id INT,
    customer_name VARCHAR(100),
    total DECIMAL(10,2)
);

INSERT INTO orders (order_id, customer_id, customer_name, total) VALUES
(5001, 101, 'Danielle Johnson', 259.99),
(5002, 102, 'Jennifer Miles', 89.50),
(5003, 101, 'Danielle Johnson', 42.00);

CREATE TABLE contacts (
    contact_id INT,
    contact_name VARCHAR(100),
    contact_email VARCHAR(100),
    contact_phone VARCHAR(30)
);

INSERT INTO contacts VALUES
(1, 'Danielle Johnson', 'danielle.johnson@example.com', '104-332-1819'),
(2, 'Michael Santiago', 'michael.santiago@example.com', '(542) 351-1615'),
(3, 'Jennifer Miles', 'jennifer.miles@example.org', '600-133-8908');

CREATE TABLE shipping (
    shipment_id INT,
    recipient_name VARCHAR(100),
    shipping_address VARCHAR(200),
    recipient_phone VARCHAR(30)
);

INSERT INTO shipping VALUES
(9001, 'Danielle Johnson', '18196 Anthony Forge, New Carolyn, OH 26563', '104-332-1819'),
(9002, 'Michael Santiago', '283 Steven Groves, Lake Mark, WI 07832', '(542) 351-1615');

CREATE TABLE products (
    product_id INT,
    product_name VARCHAR(100),
    price DECIMAL(10,2)
);

INSERT INTO products VALUES
(1, 'Wireless Mouse', 24.99),
(2, 'USB-C Cable', 12.49);

CREATE TABLE support_notes (
    note_id INT,
    note TEXT
);

INSERT INTO support_notes VALUES
(1, 'Customer asked to confirm danielle.johnson@example.com before shipping.'),
(2, 'No personal data in this note.');
