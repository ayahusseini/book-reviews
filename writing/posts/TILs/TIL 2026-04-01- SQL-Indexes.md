---
title: TIL 2026-04-01- SQL Indexes
author: Aya
type: note
slug: TIL 2026-04-01- SQL Indexes
date: 2026-04-01
---

Part of a series of "Today I Learned"s

# Technical - File Headers, Database Storage, and SQL Indexes

### What is a Header?
- In the context of file formats, a header is a block of bytes at the very start of the file containing metadata about the file itself
- It tells any `Reader` object some information on how actually to parse the file

### How does a database get stored?
- There are two main types of ways to store a database:
	- **File-based databases** live as a single file on your computer 
		- E.G. SQLite
	- **Server-based databases** are stored as multiple structured files within a directory. 
		- E.G. Postgres

### What is a page?

Before getting into Indexes, it's useful to understand pages. These are the fundamental unit both types of database use to organise data on disk.

A **page** is a fixed-size chunk of a database file. It holds multiple rows plus some bookkeeping metadata. 
- In **SQLite**, the single `.db` file is divided into pages from byte 0 onwards. Each page is 4096 bytes (4KB) by default. Page 1 starts at byte 0, page 2 at byte 4096, page 3 at byte 8192, and so on
- In **Postgres**, each table is stored as one or more files inside the data directory, and those files are also divided into pages - 8192 bytes (8KB) each by default

The fixed size means the database can jump to any page with a single operation:

```
byte offset of page N = N × page_size
```

### The headers of these files
- For SQLite, the first $100$ bytes of any `.db` file are the database header. These contain things like:
    - **A magic string:** "SQLite format 3\000" - this is how programs (and tools like file) recognise that this is a SQLite file at all, before reading anything else
    - The page size
    - The schema version 
- For server-based databases, there is no single file header for the whole database. The database spans too many files for that to be meaningful. Instead, every individual **page** carries its own small header 
        - Global metadata - which tables exist, what their columns are, their types - lives in special system tables (`pg_class`, `pg_attribute`, etc.), stored in their own pages like any other data

### Finding a particular row
- Suppose we wanted to find a particular row - say, the user whose email is `aya@example.com`
    - The most naive approach is to open the file and scan through it byte by byte from the start, reading each row until we find a match
    - We can try to be clever. What happens if we sort all the emails alphabetically and then jump to the mid-point, decide whether we need to go higher or lower and repeat (e.g. just a binary search)?
    - This runs into a problem: rows are variable-length. 
	    - A `VARCHAR(255)` column might use 3 bytes for one row and 200 for another. Without knowing where each row ends, you can't jump to row N directly - you have to read everything before it to figure out where it starts
    - In **SQLite**, this is easy to observe. A SQLite database is literally a single file on disk. You can open a terminal and run:
 
```bash
# create a small database and look at the raw bytes
sqlite3 test.db "CREATE TABLE users (id INTEGER, email TEXT); INSERT INTO users VALUES (1, 'aya@example.com');"
xxd test.db | head -20
```

- The output is mostly zeros and headers at first, but the string `aya@example.com` is sitting in there in plain ASCII, packed alongside other row data. There's no fast path to find it - a query on this table reads the whole file

- In **Postgres**, the same scan happens, but the scale is more visible. Postgres stores each table as a file (or a set of files) inside its data directory. You can find where a table lives with:
```sql
SELECT pg_relation_filepath('users');
-- returns something like: base/16384/16385
```
- Running `EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'aya@example.com'` on a table without an index will show `Seq Scan` - Postgres is reading every page of that file, top to bottom

#### Scanning each row gets expensive fast

- Pages make the in-memory cache (the **buffer pool**) much simpler to manage. The database keeps a pool of fixed-size slots in memory. When it needs a page, it checks the pool first, and if it's not there, evicts an old page to make room. Fixed sizes mean no fragmentation
- Reading a page from disk is slow - orders of magnitude slower than reading from memory
- Even with pages, a query like `SELECT * FROM users WHERE email = 'aya@example.com'` without any further help still forces the database to load every page and check every row - a **full table scan**
    - On a table with 10 million rows, this might mean reading 80,000+ pages

### What an index actually is

- An index is a separate data structure stored alongside the table, built from one or more columns
    - It holds a sorted copy of those column values, each paired with a pointer to the actual row's location on disk
    - The pointer records which page the row lives on, and which slot within that page
- The most common structure is a **B-tree** (balanced tree)
    - A B-tree node holds multiple keys and multiple child pointers. This keeps the tree short and wide, which matters because each node fits in a page read
    - The tree stays balanced: every path from root to leaf has the same length
    - The leaf nodes are the actual index entries - each one is `(value, row_pointer)`
    - The leaf level is also a doubly-linked list, so range scans (e.g. `WHERE created_at BETWEEN ...`) can walk along leaves without going back up the tree

```
        [50 | 100]
       /     |     \
  [20|35] [60|80] [110|130]
    ...       ...       ...
leaf: [(20, →page4), (35, →page7), ...]
```

- To find `email = 'aya@example.com'`, the database starts at the root, compares the value to find the right child, follows that branch, and arrives at the correct leaf in O(log n) steps
    - Instead of reading 80,000 pages, it reads maybe 4 (the tree height) plus the data page itself
    - This is why indexes are the single most impactful performance tool in a relational database

### The trade-off

- Indexes are not free
    - Every index stores a full copy of the indexed column(s) plus pointers, so they consume disk space
    - On every `INSERT`, `UPDATE`, or `DELETE`, the database has to maintain each index on that table - adding write overhead
- A table with 10 indexes on it will answer reads much faster, but writes will slow down roughly in proportion
- In practice: index on columns you filter, join, or sort on frequently. Don't index everything

```sql
-- without index: full scan of orders table
SELECT * FROM orders WHERE customer_id = 1234;

-- with an index on customer_id: O(log n) lookup
CREATE INDEX idx_orders_customer ON orders(customer_id);
```

---

### Why Snowflake makes this almost invisible

- Snowflake is a cloud-native **columnar** data warehouse, and the architecture is different enough that traditional indexes don't apply
- **Columnar storage** changes the unit of I/O
    - Row-oriented databases (Postgres, MySQL) store each row together - all columns for row 1, then all columns for row 2, and so on
    - Columnar databases store each column together - all values for `revenue` are packed into one file, all values for `user_id` into another
    - When you run `SELECT sum(revenue) FROM sales`, Snowflake only reads the `revenue` column. It never touches the other 40 columns in that table. A traditional index would buy you nothing here because the expensive part is already gone

- **Micro-partitioning** is Snowflake's substitute for index-based pruning
    - When data is loaded, Snowflake automatically divides it into small, immutable compressed files called micro-partitions (roughly 50-500MB compressed on disk, ~16MB uncompressed)
    - For every micro-partition, Snowflake stores metadata: the min and max value of every column within that partition
    - At query time, Snowflake checks the metadata before reading anything. If you filter `WHERE order_date = '2024-06-01'`, and a micro-partition's metadata says its `order_date` range is `[2023-01-01, 2023-12-31]`, that entire partition is skipped without being read
    - This is called **partition pruning**, and it happens automatically on every query

- **Clustering keys** exist for when pruning isn't aggressive enough
    - By default, data lands in micro-partitions in the order it was loaded. If your data is mostly queried by date and it was loaded in date order, pruning works well naturally
    - If your access pattern doesn't match the load order (say, you always filter by `region` but the data was loaded in random order), micro-partitions will each contain a mix of all regions - metadata min/max won't help much
    - Clustering keys tell Snowflake to keep data with similar key values physically co-located. Snowflake then periodically reorganises the table in the background
    - This is the closest equivalent to an index in Snowflake, and it's optional, coarser, and mostly self-managed

- The reason all of this works without row-level indexes is that Snowflake is built for analytical workloads (OLAP), not transactional ones (OLTP)
    - OLTP queries care about individual rows - look up this customer, update this order. B-tree indexes are perfect for that
    - OLAP queries scan large fractions of a table and aggregate. The bottleneck is the volume of data read, not the lookup of individual rows - columnar storage and partition pruning address that directly

