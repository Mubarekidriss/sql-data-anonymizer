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
(101, 'John Smith', '123 Main Street, Minneapolis, MN 55401', 'john.smith@gmail.com', '612-555-1234'),
(102, 'Maria Garcia', '48 Cedar Lane, St. Paul, MN 55102', 'maria.garcia@yahoo.com', '651-555-8890'),
(103, 'John Smith', '123 Main Street, Minneapolis, MN 55401', 'john.smith@gmail.com', '612-555-1234'),
(104, 'Patrick O''Brien', '77 River Road, Duluth, MN 55802', 'pobrien@outlook.com', '218-555-4402');

CREATE TABLE orders (
    order_id INT,
    customer_id INT,
    customer_name VARCHAR(100),
    total DECIMAL(10,2)
);

INSERT INTO orders (order_id, customer_id, customer_name, total) VALUES
(5001, 101, 'John Smith', 259.99),
(5002, 102, 'Maria Garcia', 89.50),
(5003, 101, 'John Smith', 42.00);

CREATE TABLE contacts (
    contact_id INT,
    contact_name VARCHAR(100),
    contact_email VARCHAR(100),
    contact_phone VARCHAR(30)
);

INSERT INTO contacts VALUES
(1, 'John Smith', 'john.smith@gmail.com', '612-555-1234'),
(2, 'Aisha Khan', 'aisha.khan@company.org', '(952) 555-7710'),
(3, 'Maria Garcia', 'maria.garcia@yahoo.com', '651-555-8890');

CREATE TABLE shipping (
    shipment_id INT,
    recipient_name VARCHAR(100),
    shipping_address VARCHAR(200),
    recipient_phone VARCHAR(30)
);

INSERT INTO shipping VALUES
(9001, 'John Smith', '123 Main Street, Minneapolis, MN 55401', '612-555-1234'),
(9002, 'Aisha Khan', '210 Grand Avenue, Rochester, MN 55904', '(952) 555-7710');

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
(1, 'Customer asked to confirm john.smith@gmail.com before shipping.'),
(2, 'No personal data in this note.');
