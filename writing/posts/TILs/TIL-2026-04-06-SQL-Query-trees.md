---
title: TIL 2026-04-06  - SQL Query trees
author: Aya
type: note
slug: TIL-2026-04-06-SQL-Query-trees
date: 2026-04-06
---
Part of a series of "Today I Learned"s. 
## Technical
- [[#Query trees]]
- [[#`BEGIN` and `ROLLBACK`]] 
- [[#Correlated and Uncorrelated Subqueries]]

## Query trees

### The separation of what and how in SQL 

SQL is a **declarative language** - you describe *what* result you want. E.G. *I'd like all customers who bought something in the last 30 days*

```sql
SELECT customer_id
FROM purchases
WHERE DATEDIFF(DAY, date_of_purchase, GETDATE() ) < 30;
```

This says nothing about how to find this information from the database. The same SQL query could in principle be executed in many different orders, using different strategies, and still return the same correct result. 

Every major relational database (PostgreSQL, MySQL, SQL Server, Oracle, SQLite) has a component called the **query planner** or **query optimiser** that sits between your SQL and the actual execution.  It takes your query, analyses it, and produces an **execution plan**.

### Parsing things into trees

Lots of languages get parsed into trees, not just SQL. Consider this fragment:

```sql
SELECT * 
FROM employees
WHERE 
	salary > 80000 
	AND (department_id = 1 OR department_id = 2);
```

How can we represent this in memory in a way that:
- Preserves correct operator precedence (`AND` should be before `OR` unless overridden by parentheses)?
- Is easy to evaluate, transform, or optimise?
- Handles arbitrary nesting depth (subqueries inside subqueries inside subqueries)?

A flat list immediately fails:

```
[salary] [>] [80000] [AND] [(] [department_id] [=] [1] [OR] [department_id] [=] [2] [)]
```

This is just the raw tokens. The structure tells us nothing about how they get grouped. If we want to evaluate the query, we'd need to re-parse the whole statement each time, tracking parentheses by hand and maintaining an extra state to remember precedence rules. This is fragile and slow.

A tree structure solves all of these issues naturally:

![[excalidraw/decomposition-ofquery-into-parse-tree.excalidraw.svg]]

This tree is naturally traversable with recursive algorithms. It's easiest to read this bottom-up, visiting the children before the parents (**post-order**) such that each operator receives its operands' values as an input, before computing its own result. The structure contains the meaning; no extra state is needed:
- Precedence is encoded as depth. `AND` is the root, which means it binds last (lowest precedence at this level). `>` and `=` are leaves, binding tightest.
- Any node can be replaced with an arbitrarily deep subtree — this is how subqueries work.

#### Tangent: Minimum data structures

A tree is the minimum data structure that can represent a recursive and nested language. It's worth unpacking what this phrase means: A tree is the least powerful structure that is still capable of representing the problem without any loss of information. 

Every data structure has an expressive capacity (what information can it represent?). An insufficient structure has information it can't encode at all, or information we can only encode by adding external rules and patches.

Consider what information our conditional fragment contained:
```SQL
salary > 80000 AND (department_id = 1 OR department_id = 2)
```

There are three distinct pieces of information we want to express:
1. **What** the operations are: `>`, `AND`, `OR`, `=`
2. **What** the operands are: `salary`, `80000`, `department_id`, `1`, `2`
3. **How** the operations group together. `OR` applies to the two `=` comparisons as a unit, and `AND` applies to the `>` result and the `OR` result as a unit

The third, **grouping rules**, is the one that causes trouble. Every candidate structure except a tree either loses it entirely or can only recover it by adding complexity that effectively re-creates a tree. I'll go through a few examples to demonstrate why:

##### Flat lists lose information 

We can try to parse the query into a flat list of tokens:

```python
["salary", ">", "80000", "AND", "(", "department_id", "=", "1", "OR", "department_id", "=", "2", ")"]
```

The grouping information can be recovered using the parentheses tokens. To evaluate this, we need to scan for matching parentheses, track depth counters, and reconstruct grouping on the fly. We aren't capturing all of this information in the list itself since we need to re-parse it every time. This is the key failure: a flat list requires a separate algorithm to recover structural information that was already present in the original SQL

### 3. Planning queries 
- This takes the logical **parsed** tree and converts it into a query tree or a plan tree. This is a tree of the physical operations. Each node represents some type of an action.
- Examples of nodes:
	- `SeqScan` - "read every row in the table"
	- `IndexScan` - "Traverse the B-tree index"
	- `NestedLoop` - "for each outer row, run this inner query"
	- `HashJoin`
	- `MergeJoin` 
- Each node takes as input its childrens' output. 
	- Ever node has a `next()` operation. When the executor calls `next()` on a root, the root calls `next()` on all of its children and so on. The data flows **bottom up**
- For example, take a query joining `orders` to `users`:
	```sql
	SELECT users.name, orders.total
	FROM orders
	JOIN users ON orders.user_id = users.user_id;
	```
	- The plan might look like:
		```
		HashJoin
		├── SeqScan on orders   (build side)
		└── SeqScan on users    (probe side)
		```
	- The executor calls `next()` on the `HashJoin` root. HashJoin's strategy is:
		1. Fully exhaust its left child (`SeqScan on orders`) by calling `next()` repeatedly until there are no more rows, loading them all into an in-memory hash table keyed on `user_id`
		2. Then call `next()` on its right child (`SeqScan on users`), one row at a time. For each user row, look up `user_id` in the hash table. Every match is an output row.
	- The executor never knows or cares how deep the tree goes - it just calls `next()` on the root, and each node is responsible for pulling from its own children in turn.
	- This pull-based model is sometimes called the **Volcano model** or **iterator model**. Each node is a lazy iterator: it does no work until asked, and produces one row at a time.

- This is also why InitPlan and SubPlan look different in the plan tree:
	- An **InitPlan** is not a true child in the iterator sense. It runs to completion before the main tree starts - it's more like a setup step that deposits a value into a parameter slot (`$0`), and then the main tree uses that slot as if it were a constant.
	- A **SubPlan** is a true child of the Seq Scan node, called from inside the scan's `next()` loop. Every time the scan calls `next()` to get another row, it triggers a full execution of the SubPlan before returning that row.

### `BEGIN` and `ROLLBACK`

- While setting up demo SQL files for this post, I ran into the `BEGIN` and `ROLLBACK` statements. Normally, I'd create temporary tables using `CREATE TEMP TABLE` - but it's easy to forget the `TEMP` prefix by accident, which leaves real tables sitting in your database.

```sql 
CREATE TEMP TABLE table_name AS (
	-- SELECT statement defining the table
);

-- Some INSERT statement to populate the table
```

- **A cleaner approach** is to wrap the whole script in a transaction.

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

---

### Correlated and Uncorrelated Subqueries 

- To build intuition here, let's work with two concrete tables throughout.
- **`items`** - a catalogue of things you can buy:

| item_id | name   | cost |
|---------|--------|------|
| 1       | Coffee | 3.50 |
| 2       | Tea    | 2.00 |
| 3       | Cake   | 5.00 |

- **`purchases`** - a log of individual purchases:

| purchase_id | item_id | customer |
|-------------|---------|----------|
| 1           | 1       | Alice    |
| 2           | 1       | Bob      |
| 3           | 2       | Alice    |
| 4           | 1       | Carol    |

#### Uncorrelated subqueries

- Within SQL, we can nest queries inside other queries. Here's a query that finds items costing more than average:

```sql 
-- outer query
SELECT name, cost FROM items 
WHERE cost > (
    -- inner query
    SELECT AVG(cost) FROM items 
)
```

- The average cost across all items is `3.50`. So the outer query becomes:

```sql
SELECT name, cost FROM items WHERE cost > 3.50
```

- Result:

| name | cost |
|------|------|
| Cake | 5.00 |

- The key thing here: the inner query has no reference to the outer query at all. It produces a single number - `3.50` - and that number is the same regardless of which row the outer query is currently looking at. This is an **uncorrelated subquery**.

#### Correlated subqueries

Now suppose we want to see how many times each item has been purchased. We can write that as:

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

- Result:

| item_id | name   | purchase_count |
|---------|--------|----------------|
| 1       | Coffee | 3              |
| 2       | Tea    | 1              |
| 3       | Cake   | 0              |

- Here the inner query references `items.item_id` - a column from the outer query. That means the inner query can't produce a result until it knows which row from `items` we're currently examining. This is a **correlated subquery**: the inner and outer queries are linked by a dependency.

### How relational databases handle subqueries


#### What planners generally do with subqueries

- When the planner encounters a subquery, the first thing it asks is: does this subquery depend on the outer query?
	- If the subquery is **uncorrelated**, the planner recognises that it produces the same result no matter which outer row we're looking at. 
		- Most planners will hoist it out of the loop entirely, computing it once before the outer scan begins and treating the result as a constant. 
		- This isn't caching - the planner doesn't run it once and then check a cache before running it again. It schedules it to run once, structurally, as a separate pre-computation step. The result is stored as a parameter and substituted in wherever the subquery appeared.
			- We can use the following mental model:
				```sql
				-- uncorrelated: compute once, reuse
				avg_cost = SELECT AVG(cost) FROM items   -- runs once: 3.50
				
				for each row in items:
				    if row.cost > avg_cost:
				        return row
				```
	- If the subquery is **correlated**, the planner re-evaluates it per row. 
		- The straightforward execution is a loop: for each outer row, run the subquery with the current row's values. This is the correct but potentially expensive approach.
		```sql 
		-- correlated: runs fresh for every row
		for each row in items:
		    count = SELECT COUNT(*) FROM purchases
		            WHERE purchases.item_id = row.item_id   -- runs once per row
		    return row.item_id, row.name, count
		```
		- The one optimisation planners can apply to correlated subqueries is **result caching**: if the same input value appears in multiple outer rows, cache the result the first time and return it for subsequent rows without re-running the subquery. 
		- Whether this helps depends on how many distinct values appear in the correlated column. 
			- If every outer row has a unique value, caching adds overhead without any benefit. Most planners will detect this and won't bother.

#### PostgreSQL specifically
- PostgreSQL is good to play around with because it will `EXPLAIN` how a query is actually planned. Take our uncorrelated query from earlier:
```sql
EXPLAIN 
SELECT name, cost FROM items 
WHERE cost > (SELECT AVG(cost) FROM items);
```
- The output is a tree. Here's why that structure makes sense:
	- A filter takes rows and produces a smaller set of rows. An aggregate takes rows and produces a single summary value. These steps chain together - the output of one becomes the input of the next.
- For a simple query, this looks like a flat list (a special case of a tree) 

```sql
                                   QUERY PLAN                                   
--------------------------------------------------------------------------------
 Seq Scan on items  (cost=22.76..45.51 rows=340 width=48)
   Filter: (cost > $0)
   InitPlan 1 (returns $0)
     ->  Aggregate  (cost=22.75..22.76 rows=1 width=32)
           ->  Seq Scan on items items_1  (cost=0.00..20.20 rows=1020 width=16)
```

- But queries can have multiple inputs. 
	- A `JOIN` combines two tables - it has two inputs flowing into one operation, which can't be expressed as a flat sequence. 
	- A subquery feeds its result into the outer query - again, two things flowing into one. 
	- The moment you have branching data flows, you need a structure that can represent "these two things feed into this one thing", which is exactly what a tree does.
- So the tree is just the natural shape of the computation: leaves are raw data sources (table scans), internal nodes are operations that transform or combine data, and the root is the final result. Data flows upward from leaves to the root.


##### Reading the EXPLAIN output

Before looking at InitPlan and SubPlan, it helps to understand what the EXPLAIN format is actually showing - because the visual layout doesn't map neatly onto execution order, and that's the source of most confusion.

The output is **a description of the plan tree**, not a top-to-bottom script of what runs first. Two things in particular trip people up:

**`Filter:` is not a separate step.** Lines like `Filter: (cost > $0)` are annotations on their parent node - they describe *how* the Seq Scan behaves, not a distinct operation that happens after it. The Seq Scan applies the filter itself as it reads each row. Think of it as a property of the scan, not a successor to it.

**Indentation shows association, not execution order.** Both InitPlan and SubPlan appear indented under the Seq Scan, which makes them look like they're "inside" it in the same way. But they have a fundamentally different relationship to it:

- An **InitPlan** is a *pre-condition* - it runs before the Seq Scan begins, produces a value (`$0`), and the Seq Scan then uses that value as a constant. It appears indented under the Seq Scan because the Seq Scan is the node that depends on it, but it is not running inside the scan's loop.
- A **SubPlan** is a *subroutine* - it runs once per row, inside the Seq Scan's loop. It genuinely lives inside the scan.

A rough translation into code makes the difference clear:

```python
# InitPlan: runs before the loop
$0 = SELECT AVG(cost) FROM items      # ← InitPlan runs here, once

for row in items:                     # ← Seq Scan begins
    if row.cost > $0:                 # ← Filter uses $0 (already known)
        yield row

# SubPlan: runs inside the loop
for row in items:                     # ← Seq Scan begins
    count = SELECT COUNT(*)           # ← SubPlan runs here, once per row
            FROM purchases
            WHERE item_id = row.item_id
    yield row.item_id, row.name, count
```

So when you look at the EXPLAIN output and see `Filter: (cost > $0)` appearing *before* `InitPlan 1 (returns $0)` in the text, it's not a contradiction - the filter is just a property of the Seq Scan node listed first, and the InitPlan is the thing that makes `$0` available. The execution order is InitPlan first, then the Seq Scan (with the filter applied inline).

##### Understanding InitPlan

```
 Seq Scan on items  (cost=22.76..45.51 rows=340 width=48)
   Filter: (cost > $0)              ← property of the scan: "only keep rows where cost > $0"
   InitPlan 1 (returns $0)          ← runs before the scan; stores AVG result as $0
     ->  Aggregate  (...)           ← computes AVG(cost)
           ->  Seq Scan on items_1  ← reads items to compute the average
```

`$0` is a parameter slot - a named placeholder, like a variable. By the time the outer Seq Scan starts, `$0` already holds `3.50`. The scan then uses it as if it were a literal.

##### Understanding SubPlan

```sql
EXPLAIN SELECT item_id, name,
    (
	    SELECT COUNT(*) 
	    FROM purchases 
	    WHERE purchases.item_id = items.item_id
	) AS purchase_count
FROM items;
```

```
 Seq Scan on items  (cost=0.00..25545.70 rows=1020 width=44)
   SubPlan 1                                    ← runs once per row, inside the loop
     ->  Aggregate  (cost=25.02..25.03 ...)
           ->  Seq Scan on purchases  (...)
                 Filter: (item_id = items.item_id)   ← the dependency: uses the current outer row
```

There's no `$0` here - the SubPlan can't store its result as a constant because the result changes depending on which row we're on. `Filter: (item_id = items.item_id)` makes the dependency explicit: the inner scan needs `items.item_id` from the current outer row, so it can't run until the outer scan is mid-loop.

With 3 items, the purchases scan runs 3 times. With 100,000 items, 100,000 times.


##### Understanding Memoize (PostgreSQL 14+)

SubPlans re-execute for every outer row with no memory of prior results. PostgreSQL 14 added a **Memoize** node that sits inside the SubPlan and acts as a result cache: the first time the subquery runs for a given `item_id`, the result is stored in a hash map. If the same `item_id` appears in a later outer row, the stored result is returned instead of re-running the subquery.

```
 Seq Scan on items
   SubPlan 1
     ->  Memoize
           Cache Key: items.item_id
           ->  Aggregate
                 ->  Seq Scan on purchases
                       Filter: (item_id = items.item_id)
```

This is genuine runtime caching - unlike an InitPlan (which is a structural, planning-time decision), Memoize checks at runtime whether it has seen this input before. It only helps when the outer query produces repeated values for the correlated column. If every `item_id` is distinct, Memoize adds overhead for no benefit, and the planner won't insert it. PostgreSQL estimates the expected number of distinct values and decides accordingly.

Knowing the difference matters in practice: if you run `EXPLAIN` on a slow query and see `SubPlan` against a large table, that's the signal to consider rewriting. `InitPlan` means you're already getting a one-time pre-computation. `Memoize` means PostgreSQL has decided caching is worthwhile, but it only helps if your data has repeated values in the correlated column.

#### Performance implications and when to use what

Because a correlated subquery (as a SubPlan) runs once per row, it can be slow on large datasets. In many cases you can rewrite it as a JOIN, which gives the planner a much wider set of strategies:

```sql
-- correlated subquery version
SELECT item_id, name,
    (SELECT COUNT(*) FROM purchases WHERE purchases.item_id = items.item_id) AS purchase_count
FROM items;

-- equivalent JOIN version
SELECT items.item_id, items.name, COUNT(purchases.purchase_id) AS purchase_count
FROM items
LEFT JOIN purchases ON purchases.item_id = items.item_id
GROUP BY items.item_id, items.name;
```

Both return the same result. The JOIN version lets the planner choose from a wider set of strategies (hash joins, merge joins, etc.) rather than being constrained to a row-by-row loop. For large tables the JOIN is usually significantly faster.

The correlated subquery form is often more readable - especially in `WHERE` clauses where the intent is clearer. The practical rule: prefer the correlated subquery when clarity matters and the table is small; reach for a JOIN when scale matters.

---

### The `EXISTS` keyword in SQL 

`EXISTS` is a boolean test: given a subquery, it returns `true` if the subquery produces at least one row, and `false` if it produces none.

```sql
SELECT *
FROM people 
WHERE EXISTS (
    SELECT 1
    FROM employment_data
    WHERE people.full_name = employment_data.full_name
);
```

This is a correlated subquery - it references `people.full_name` from the outer query. For each person in `people`, the subquery checks whether any row exists in `employment_data` with a matching name. The query returns only those people who have at least one employment record.

To make this concrete: suppose `people` contains Alice, Bob, and Carol, and `employment_data` has records for Alice and Carol. The output would be:

| full_name |
|-----------|
| Alice     |
| Carol     |

Bob is excluded because the subquery returned no rows for him.

#### Short-circuit evaluation

As soon as the subquery finds one matching row, `EXISTS` returns `true` and stops scanning. It doesn't count all the matches or collect them - it just needs to confirm that at least one exists.

This is called **short-circuit evaluation**, and it's what makes `EXISTS` well-suited for existence checks. Compare that to writing `COUNT(*) > 0` in a subquery - that forces a full scan and count before returning anything. `EXISTS` can return as soon as the first match is found.

#### Why `SELECT 1`?

The subquery inside `EXISTS` selects `1` rather than any actual columns. `EXISTS` doesn't look at what you select - it only cares whether any rows come back. Writing `SELECT 1` makes this intent explicit: we're not interested in the data, only in whether the row exists. Writing `SELECT *` would behave identically, but `SELECT 1` signals clearly that the column values are irrelevant. It's a convention that communicates intent.

#### `NOT EXISTS`

The complement of `EXISTS` is `NOT EXISTS`, which returns `true` when the subquery produces no rows:

```sql
SELECT *
FROM people
WHERE NOT EXISTS (
    SELECT 1
    FROM employment_data
    WHERE people.full_name = employment_data.full_name
);
```

This gives you everyone in `people` who has no entry in `employment_data` - in our example, just Bob.

`NOT EXISTS` is particularly useful because the alternative approaches can be tricky to get right, as we'll see next.

#### `EXISTS` vs `IN`

`IN` and `EXISTS` are often interchangeable, but they behave differently in ways that matter.

Here's the `IN` version of the employment query:

```sql
SELECT *
FROM people
WHERE full_name IN (
    SELECT full_name FROM employment_data
);
```

For most data this returns the same rows as the `EXISTS` version. The differences:

**Short-circuiting.** `EXISTS` stops as soon as it finds one match. `IN` with a subquery typically collects all the values from the subquery first, building a set, then checks membership for each outer row. For large tables, this can make `EXISTS` faster when the match appears early in the subquery's results.

**NULL handling - the important one.** SQL has a rule: any comparison involving `NULL` produces `NULL`, not `true` or `false`. `NULL` represents an unknown value, and comparing something to an unknown produces an unknown result. This creates a subtle trap with `IN`.

Suppose `employment_data.full_name` contains a `NULL` value alongside real names. The `IN` subquery returns a set like `{'Alice', 'Carol', NULL}`. When SQL checks `WHERE full_name IN ('Alice', 'Carol', NULL)` for a name like Bob, it evaluates:

```
'Bob' = 'Alice'  →  false
'Bob' = 'Carol'  →  false
'Bob' = NULL     →  NULL   (unknown)
```

SQL's `WHERE` clause only keeps rows where the condition is `true`. A `NULL` result is not `true`, so Bob is correctly excluded. But now consider the `NOT IN` version - finding people *without* employment data:

```sql
SELECT * FROM people WHERE full_name NOT IN (SELECT full_name FROM employment_data);
```

For Bob, this evaluates:

```
'Bob' != 'Alice'  →  true
'Bob' != 'Carol'  →  true
'Bob' != NULL     →  NULL   (unknown)
```

SQL combines these with `AND` - so the result is `true AND true AND NULL`, which is `NULL`. Bob is *excluded from the result*, even though Bob genuinely has no employment record. The NULL in the subquery poisons the whole `NOT IN` check, and the query silently returns no rows.

`NOT EXISTS` sidesteps this entirely. It doesn't compare values directly - it just checks whether any rows were returned. A `NULL` in a column doesn't prevent a row from existing, so `NOT EXISTS` gives the correct answer regardless.

This is the main reason to reach for `EXISTS` and `NOT EXISTS`: they compose safely with `NULL`. `IN` is fine when you're matching against a known, clean list with no nulls. `NOT IN` against a subquery is almost always a mistake if the subquery column can contain nulls.
