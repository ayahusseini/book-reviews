---
title: "TIL 2026-04-06 SQL EXISTS"
author: "Aya"
type: "note"
slug: "TIL-2026-04-06-SQL-EXISTS"
date: 2026-04-06
---

## Technical

### `BEGIN` and `ROLLBACK`

- While setting up demo SQL files for this post, I ran into `BEGIN` and `ROLLBACK`. 
- Normally, I'd create temporary tables using `CREATE TEMP TABLE` - but it's easy to forget the TEMP prefix by accident, which leaves real tables sitting in your database.

```sql 
CREATE TEMP TABLE table_name AS (
	-- SELECT statement defining the table
);

-- Some INSERT statement to populate the table
```

- **A cleaner approach**: wrap the whole script in a transaction.

```sql 
  BEGIN;
  -- standard CREATE TABLE and INSERT statements
  ROLLBACK;
```


- Transactions are a bundle of commands that get treated as a single atomic unit. You can start a transaction block by running `BEGIN`
	- Nothing in a transaction gets written to the database until you call `COMMIT`. 
	- `ROLLBACK` does the opposite: it discards everything since `BEGIN`. 
- Transactions are useful beyond cleanup. If anything fails mid-script, the whole block rolls back automatically. Otherwise, we'd need to figure out which tables got created before the error and clean them up manually.

- That being said, if you'd like to follow along with this post, please see the [[demo.sql]] file. 

### Correlated and Uncorrelated Subqueries 

- Within SQL, we can have outer queries and inner queries 

```sql 

-- outer query
SELECT name, cost from items 
WHERE cost > (
	-- inner query
	SELECT AVG(cost) from items 
)
```

- In the above example, the inner query runs **one time** and is independent of the outer query. This is called an uncorrelated subquery. 
- This isn't always the case. We can also have a subquery that runs **multiple times** (once for each row in the outer query). It can reference columns and values from the outer query, creating a dependency. 
- For example, suppose we wanted to see how many times a particular item was purchased
```sql
SELECT 
	item_id, 
	name, 
	(
		SELECT COUNT(*) FROM purchases 
		WHERE purchases.item_id = items.item_id
	) AS purchase_count 
	FROM items;
```

#### How does PostgreSQL line things up?
- Here's a walkthrough of what actually happens:
	- `postgres` begins to iterate through the `items` table, one row at a time
	```
	Row 1: item_id = 1, name = 'Coffee', cost = 3.50
	```
	- Before moving onto the next row, it needs to evaluate the subquery **in the context of row 1**. 
	- The subquery runs, substituting `items.item_id` with `1`
- The same thing happens when running subqueries as part of `WHERE` clauses.

### The `EXISTS` keyword in SQL 

The `EXISTS` keyword in SQL is a boolean test that asks "*Does at least one row exist that satisfies this condition*"?.  

```SQL

SELECT *
FROM people 
WHERE EXISTS (
	SELECT 1
	FROM employment_data
	WHERE people.full_name = employment_data.full_name
)
; 
```

The above query filters `people` down to just those with available `employment_data` rows. Internally, for each row in the outer query (`select * from people`), we ask if *any* row exists 