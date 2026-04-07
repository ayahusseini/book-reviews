BEGIN;

CREATE TABLE items (
    item_id SERIAL PRIMARY KEY,
    name    TEXT           NOT NULL,
    cost    NUMERIC(10, 2) NOT NULL
);

CREATE TABLE purchases (
    purchase_id SERIAL PRIMARY KEY,
    item_id     INT  REFERENCES items(item_id),
    date        DATE NOT NULL
);

INSERT INTO items (name, cost) VALUES
    ('Coffee',       3.50),
    ('Notebook',     8.99),
    ('Pen',          1.49),
    ('Desk lamp',   24.99),
    ('Sticky notes', 4.00);

INSERT INTO purchases (item_id, date) VALUES
    (1, '2026-01-05'),
    (1, '2026-01-12'),
    (3, '2026-02-03'),
    (5, '2026-03-18'),
    (1, '2026-04-01');

SELECT * FROM items;

SELECT * FROM purchases;

ROLLBACK;
