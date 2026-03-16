from __future__ import annotations

from app.database.models import Post


def test_posts_list_page_renders(app, db):
    client = app.test_client()
    res = client.get("/posts/")
    assert res.status_code == 200
    assert b"Posts" in res.data


def test_posts_detail_page_renders_markdown_safely(app, db):
    with app.app_context():
        post = Post(
            post_slug="hello",
            post_source_path="hello.md",
            post_title="Hello",
            post_body_markdown='Hi<script>alert("x")</script>',
            post_author="Aya",
            post_type="review",
        )
        db.session.add(post)
        db.session.commit()

    client = app.test_client()
    res = client.get("/posts/hello")
    assert res.status_code == 200
    assert b"Hello" in res.data
    assert b"<script" not in res.data.lower()


def test_posts_detail_404(app, db):
    client = app.test_client()
    res = client.get("/posts/does-not-exist")
    assert res.status_code == 404
