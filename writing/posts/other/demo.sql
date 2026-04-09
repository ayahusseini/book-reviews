BEGIN;

-- ============================================================
-- Tables used throughout the post
-- ============================================================

CREATE TABLE items (
    item_id SERIAL PRIMARY KEY,
    name    TEXT           NOT NULL,
    cost    NUMERIC(10, 2) NOT NULL
);

CREATE TABLE purchases (
    purchase_id SERIAL PRIMARY KEY,
    item_id     INT  REFERENCES items(item_id),
    customer    TEXT NOT NULL
);

CREATE TABLE people (
    full_name TEXT PRIMARY KEY
);

CREATE TABLE employment_data (
    full_name TEXT,
    employer  TEXT
);

-- ============================================================
-- Seed data
-- ============================================================

INSERT INTO items (name, cost) VALUES
    ('Coffee', 3.50),
    ('Tea',    2.00),
    ('Cake',   5.00);

-- Coffee (item_id=1) purchased 3 times, Tea (item_id=2) once, Cake (item_id=3) never
INSERT INTO purchases (item_id, customer) VALUES
    (1, 'Alice'),
    (1, 'Bob'),
    (2, 'Alice'),
    (1, 'Carol');

INSERT INTO people (full_name) VALUES
    ('Alice'),
    ('Bob'),
    ('Carol');

-- Alice and Carol have employment records; Bob does not
-- The NULL row is included to demonstrate the NOT IN / NULL trap
INSERT INTO employment_data (full_name, employer) VALUES
    ('Alice', 'Acme Corp'),
    ('Carol', 'Globex'),
    (NULL,    'Unknown');

-- ============================================================
-- Uncorrelated subquery
-- Items costing more than the average cost (3.50)
-- Expected: only Cake (5.00)
-- ============================================================

SELECT name, cost
FROM items
WHERE cost > (
    SELECT AVG(cost) FROM items
);

-- ============================================================
-- Correlated subquery
-- Purchase count per item
-- Expected: Coffee=3, Tea=1, Cake=0
-- ============================================================

SELECT
    item_id,
    name,
    (
        SELECT COUNT(*) FROM purchases
        WHERE purchases.item_id = items.item_id
    ) AS purchase_count
FROM items;

-- ============================================================
-- Query plans: see how PostgreSQL executes each type
-- InitPlan for uncorrelated, SubPlan for correlated
-- ============================================================

EXPLAIN SELECT name, cost
FROM items
WHERE cost > (
    SELECT AVG(cost) FROM items
);

EXPLAIN SELECT
    item_id,
    name,
    (
        SELECT COUNT(*) FROM purchases
        WHERE purchases.item_id = items.item_id
    ) AS purchase_count
FROM items;

-- ============================================================
-- EXISTS
-- People who have employment records
-- Expected: Alice, Carol
-- ============================================================

SELECT *
FROM people
WHERE EXISTS (
    SELECT 1
    FROM employment_data
    WHERE people.full_name = employment_data.full_name
);

-- ============================================================
-- NOT EXISTS
-- People who have no employment record
-- Expected: Bob
-- ============================================================

SELECT *
FROM people
WHERE NOT EXISTS (
    SELECT 1
    FROM employment_data
    WHERE people.full_name = employment_data.full_name
);

-- ============================================================
-- The NOT IN / NULL trap
-- employment_data contains a NULL full_name row.
-- NOT IN returns no rows at all because NULL poisons the check.
-- NOT EXISTS returns Bob correctly.
-- ============================================================

-- Returns no rows - the NULL in employment_data breaks NOT IN
SELECT *
FROM people
WHERE full_name NOT IN (
    SELECT full_name FROM employment_data
);

-- Returns Bob correctly - NOT EXISTS is unaffected by the NULL
SELECT *
FROM people
WHERE NOT EXISTS (
    SELECT 1
    FROM employment_data
    WHERE people.full_name = employment_data.full_name
);

ROLLBACK;
