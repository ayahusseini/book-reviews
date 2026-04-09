---
title: TIL 2026-04-06  - SQL Parse Trees and Capitalism
author: Aya
type: note
slug: TIL-2026-04-06-SQL-parse-trees-and-capitalism
date: 2026-04-06
---
Part of a series of "Today I Learned"s. 


## Query trees

This is the first of two parts exploring how PostgreSQL treats SQL code as a tree. Here, I'll cover why languages are represented as trees at all, what other structures were considered and why they fall short, and the first two stages of PostgreSQL's processing pipeline — lexing (breaking SQL into tokens) and parsing (assembling those tokens into a parse tree). In some future TIL post, I'll pick up from there to cover how the parse tree is resolved against the database and ultimately executed. 

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
tokens = ["salary", ">", "80000", "AND", "(", "department_id", "=", "1", "OR", "department_id", "=", "2", ")"]
```

The grouping information can be recovered using the parentheses tokens. To evaluate this, we need to scan for matching parentheses, track depth counters, and reconstruct grouping on the fly. 

E.G. 
```python

def add_depth_counter(all_tokens: list[str]) -> list[tuple]:
	""" 
	Returns a list of tokens, with their depth, as a list of 
	tuples (depth, token)
	"""  
	grouped_tokens = []
	depth = 1
	for t in all_tokens:
		if t == "(":
			depth += 1
		elif t == ")":
			depth -= 1
		if t not in {")", "("}:
			grouped_tokens.append((group_number, t))
	return grouped_tokens
	
add_depth_counter(tokens)
# returns 
# [	
# (1, 'salary'), (1, '>'), (1, '80000'), (1, 'AND'), 
# (2, 'department_id'), (2, '='), (2, '1'), 
# (2, 'OR'), (2, 'department_id'), (2, '='), (2, '2')
# ]

```

We aren't capturing all of this information in the list itself since we need to re-parse it every time. This is the key failure: a flat list requires a separate algorithm to recover structural information that was already present in the original SQL

##### Stacks destroy information 

We can also try a **stack**. A stack is a sequence of items with a strict rule: you can only ever interact with the item on top. There are two operations on a stack:
- **Pushing** - placing a new item on top
- **Popping** - removing the topmost item
A physical analogy is a literal stack of plates, which follows the same LIFO (Last In, First Out) structure.

Before getting into why stacks *won't* work for storing query information, it's worth going over why we might consider them. They are extremely fast and simple. There isn't any indexing, searching, or memory allocation required beyond a single growing array.  This makes them attractive for situations where you process a stream of items in sequence and only ever need the most recent context.

The classic use case is the **"call stack"** most programming languages use- this data structure tracks which function called which other function.  Stacks are also used in calculators for evaluating mathematical expressions. 

Stacks can handle ordered and grouped operations by using [Reverse Polish Notation (RPN)](https://en.wikipedia.org/wiki/Reverse_Polish_notation). I won't go into much detail, but here's an example of how it works. In normal (infix) notation, operators sit _between_ their operands:

```
(3 + 4) * (2 + 1) = 21
```

In reverse polish notation, we represent it with the below sequence:
```
RPN sequence:   3  4  +  2  1  +  *
```
Now, this sequence is easier to evaluate. We work from left to right, processing each token. At the same time, we maintain a `stack`. The stack starts empty `[]` and grows rightward. 
- When you see a **value** (a number, a column name), push it to `stack`
- When you see an **operator**: **pop** two operands from the `stack`. Apply the operator and push the result

```
Token   Action                          Stack
─────   ──────────────────────────────  ──────────────
3       push 3                          [3]
4       push 4                          [3, 4]
+       pop (4,3), push 4+3=7           [7]
2       push 2                          [7, 2]
1       push 1                          [7, 2, 1]
+       pop (1,2), push 1+2=3           [7, 3]
*       pop (7,3), push 7*3=21          [21]
```

We could theoretically also translate queries into RPN and get our required rows. The problem with a stack is that it destroys as it evaluates. Once you pop two operands and an operator off the stack, they are out of memory. The stack is designed for processes that read input once and produce output once: evaluating a formula, compiling to bytecode, rendering a page. In contrast, a query goes through at least five transformation passes - lex, parse, analyse, rewrite, and plan. Each pass needs the full structure intact to hand to the next. 
##### Hash maps lose information 

A hash map is a data structure that stores key-value pairs. 

To capture the clause structure of a query

```SQL
SELECT 
	e.name, 
	d.name AS department_name, 
	e.salary
FROM employees e
JOIN departments d ON e.department_id = d.id
WHERE 
	e.salary == 0 
	AND 
	(d.department_id = 1 OR d.department_id = 2)
ORDER BY e.salary DESC;
```

We can try to use a hash map instead of a tree:

```json
{
  "select": ["e.name", "d.name", "e.salary"],
  "from": "employees",
  "join": { 
	  "table": "departments", "on": "e.department_id = d.id" },
  "where": "e.salary == 0 AND ...",
  "order_by": "e.salary DESC"
}
```

This captures the top-level clause structure, but look at what happens to `"where"`: it's a **string**. The hash map ran out of expressiveness at the first level of nesting and fell back to storing raw SQL text. That string would need to be re-parsed to do anything with it. 

You could try to make the hash map deeper and store the `WHERE` clause as another hash map with `"left"`, `"operator"`, `"right"` keys. At this point, we'd have hash maps inside hash maps. 

```json
"where": [
	{"left": "e.salary", "operator" : "==", "right": "0"},
	# AND (
	{"left": "d.department_id", "operator" : "==", "right": "1"},
	# OR
	{"left": "d.department_id", "operator" : "==", "right": "2"},
	# )
]
```

We'd also need to decide how to represent `AND`s connecting two clauses: do we use a list of `WHERE` maps? At this point, we're just re-inventing an ad-hoc tree with a hash map as a node. In other words, a tree with worse ergonomics.  

##### The precise definition of 'minimum' 
A data structure is sufficient for a problem if it represents all instances of the problem without loss. It is minimal if removing any of its structural properties makes it insufficient. 

For example, a rooted and ordered tree has the following properties:
- Nodes representing individual operations and operands
- Parent-child relationships (where childrens' outputs are a parent's input)
- Ordered child nodes (because `a - b != b - a`)
- Arbitrary depth because of nesting subqueries 

Removing any one of these features means that some queries can't be represented.

A graph is a more general structure than a tree, allowing any node to connect to another, including cycles. Graphs are used later for query optimisation (e.g. for reasoning about what join ordering is best), but **parsing** requires a directed and acyclic structure. 
### Formal Grammars and Why They Produce Trees

So far, we have established that SQL _should_ be represented as a tree. There is a deeper level to this. Syntax is defined as a **grammar** - a precise set of rules that describes every valid statement. English has grammar rules like "a sentence is a noun phrase followed by a verb phrase".  SQL's syntax is called a [**context-free grammar** (CFG)](https://en.wikipedia.org/wiki/Context-free_grammar). When followed mechanically, this naturally produces a tree as a by-product. 

#### Terminals and Non-Terminals 

Every grammar has two kinds of things:
- Terminals are the tokens that appear in the code you write. They are called terminals because you can't break them down any further.
	- Examples include `SELECT`, `FROM`, `>`, `column_name`, `'abc'`, `80000`
- Non-terminals are named patterns that represent a *kind of thing* in the language, rather than a specific token.
	- E.G., in SQL, we have non-terminals like `expression`, `where_clause`, `select_stmt`, `column_reference`
What you see in actual SQL are terminals. `WHERE`, `salary`, `=`, `0`. The non-terminals are the parser's way of naming the _patterns_ that those terminals form. 

#### Production Rules
A production rule is a rule of the form:
```
non-terminal -> what it is made of
```
Read it as: "a `non-terminal` can be this sequence of things"
For example:
```
where_clause -> WHERE expression
```
This states that a `where_clause` is made up of the `WHERE` token and some non-terminal `expression` pattern. The `expression` rule might look something like this:
```
expression  →  expression '>' expression
            |  expression 'AND' expression
            |  expression 'OR' expression
            |  '(' expression ')'
            |  column_reference
            |  literal
```
where we've taken the `|` pipe to mean `OR`.  

Translating this to English:
```
An expression can be:
	- two expressions with `>` between them 
	- two expressions with `AND` between them
	- etc.
```

#### Recursive Production Rules Produce Trees

Notice that these rules are allowed to be **recursive**: an `expression` can appear on both sides of a production rule. Recursive production rules are what naturally lead to a tree structure:
- Every production rule says: "this non-terminal is made of these parts." 
- That parent-made-of-children relationship is exactly the definition of a tree node. 
- When a rule fires, you get one new parent with its components as children. When a rule's components are themselves non-terminals, those fire their own rules, giving those children their own children. The recursion produces depth.
- We must end at terminal nodes (leaf nodes)

### Beyond the Parse Tree

As an initial step, the database manager has taken your SQL string and produced a **raw parse tree**. This is a nested, hierarchical representation of the grammatical structure of your query. However, column and table names are still just names; Nothing has been verified against the actual database yet. In a future TIL, I'll describe how the parse tree is handed to the **analyser**, which resolves every name against the database system catalogues. From there, it passes through the **rewriter** (which expands views and applies rules), the **planner** (which decides the cheapest physical strategy for executing the query), and finally the **executor** (which actually runs the plan and returns rows).

## Less interesting: BEGIN and ROLLBACK

While setting up demo SQL files for this post, I ran into the `BEGIN` and `ROLLBACK` statements. Normally, I'd create temporary tables using `CREATE TEMP TABLE` - but it's easy to forget the `TEMP` prefix by accident, which leaves real tables sitting in your database.

```sql 
CREATE TEMP TABLE table_name AS (
	-- SELECT statement defining the table
);

-- Some INSERT statement to populate the table
```

**A cleaner approach** is to wrap the whole script in a transaction.

```sql 
  BEGIN;
  -- standard CREATE TABLE and INSERT statements
  ROLLBACK;
```

Transactions are a bundle of commands that get treated as a single atomic unit. You can start a transaction block by running `BEGIN`. Nothing in a transaction gets written to the database until you call `COMMIT`. `ROLLBACK` does the opposite: it discards everything since `BEGIN`. 

Transactions are useful beyond cleanup. If anything fails mid-script, the whole block rolls back automatically. Otherwise, we'd need to figure out which tables got created before the error and clean them up manually.

## Capitalism isn't the same thing as wanting to make money

For my sins, I was listening to the [New Statesman podcast](https://www.youtube.com/watch?v=Lp02g8zyRyg) episode with Sven Beckert. He talks about his book _Capitalism: A Global History_, which covers the last thousand years of economic life. 

I found the episode's central argument genuinely surprising. I fall into the trap of defining capitalism as "people wanting to make money." This, in turn, makes it seem natural. Wanting to maximise some arbitrary metric feels like a core human drive, and alternative systems start to look like radical deviations from instinct. 

I won't rewrite or summarise the entire contents of the podcast, since it's pretty compact, but here are some scattered notes:

For most of human history, economic life ran on two logics.
- The first was subsistence: most people farmed to produce enough to eat, and a little surplus to trade locally for things you couldn't grow yourself. A peasant family was not trying to expand output year on year.
- The second was tribute: Above the peasants sat lords and religious authorities who extracted a share of what peasants produced. They did this through obligation, custom, or servitude. 

Importantly, both systems still had a **profit drive**. The distinction with capitalists is that neither is involved in reinvestment. A lord could, in theory, have taken his extracted grain and ploughed it back into better equipment or more land clearance. And some did do this, but it never became the dominant logic:
- More gold didn't straightforwardly buy you more swords, because the whole structure of feudal society was built around land tenure as the basis of obligation, not cash. The lord's rational move was to acquire more land, which gave him more serfs, which gave him more military obligation, which gave him more power. Reinvesting grain into better ploughs didn't obviously advance that goal.
- Even if gold *did* buy power, there was no mechanism by which producing twice as much grain translated reliably into twice as much gold. The local markets weren't deep enough to absorb it. You'd need towns of a certain size, and enough monetary circulation for large transactions to happen at all.

### Merchants 

There were also merchant families that made money on the difference between what they paid and what they sold for. Beckert calls these "islands of capital". Some of them got rich doing this, but they operated on the fringes of societies whose logic was different. Though they were profit-maximisers, they rarely accumulated dynastic wealth. There was a ceiling on the scale of what they could do, because they depended entirely on other people's production. A merchant bought what peasants grew and moved it somewhere else. He couldn't reorganise how the peasants worked, because he didn't own the land or control the labour. The volume of goods available to trade was set by people farming to survive, not farming to supply merchants.

What changed, slowly from around the 16th century, was that capital started flowing into production itself. Merchants stopped just buying what peasants grew. They put money into the land and organised the whole process around generating a return. The goal was no longer to profit on the margin between two markets. It was now to own the means of producing the goods in the first place. 

Once capital controls production and sells into competitive markets, a new pressure emerges. If you own a textile mill and your competitor buys a faster loom while you sit on your profits, he produces cloth more cheaply, undercuts your prices, and eventually puts you out of business. Now, the market punishes you for not reinvesting. Nobody has to intend this; it just follows naturally from the structure of private owners competing in the same markets. 

The settlement of Barbados in the 17th century illustrates what it looked like when those new rules took hold entirely. European capital bought the land and enslaved the labour. The entire process of growing sugar was organised around maximising output for international markets. The usual constraints of local demand didn't apply. Beckert argues this was the first fully capitalist society in history. It was also built on slavery, which he treats not as a contradiction of capitalism but as one of the tools by which the capitalist logic was imposed on a place where free workers would never have accepted the conditions on offer.