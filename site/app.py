from flask import Flask, render_template
import duckdb

app = Flask(__name__)

DB_PATH = "database/site.db"


def get_db_connection():
    return duckdb.connect(DB_PATH)


@app.route("/")
def index():
    con = get_db_connection()
    books = con.execute("SELECT * FROM books ORDER BY book_title").fetchall()
    print(books)
    authors = con.execute(
        "SELECT * FROM authors ORDER BY author_name"
    ).fetchall()
    return render_template("index.html", books=books, authors=authors)


if __name__ == "__main__":
    app.run(debug=True)
