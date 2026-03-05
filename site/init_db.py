"""
Initialise the database
Running this script will create the database and the tables
if they do not exist.
"""

import duckdb

SCHEMA_PATH = "database/schema.sql"


def get_connection():
    return duckdb.connect(database="site.db")


if __name__ == "__main__":
    with get_connection() as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.execute(f.read())
