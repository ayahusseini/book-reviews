from __future__ import annotations
from flask import Blueprint, render_template
from app.database.models import Post
from app.extensions import cache
from content.markdown_posts import render_markdown_to_safe_html

poems_bp = Blueprint("poems", __name__)


@poems_bp.route("/", methods=["GET"])
@cache.cached()
def poem_list():
    poems = (
        Post.query.filter_by(post_type="poem")
        .order_by(Post.post_created_at.desc())
        .all()
    )
    return render_template("poems.html", poems=poems)


@poems_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def poem_detail(slug: str):
    from flask import abort

    poem = Post.query.filter_by(post_slug=slug, post_type="poem").first()
    if not poem:
        abort(404)

    parts = poem.post_body_markdown.split("\n---\n", 1)
    poem_html = render_markdown_to_safe_html(parts[0])
    comments_html = (
        render_markdown_to_safe_html(parts[1]) if len(parts) > 1 else None
    )

    return render_template(
        "poem_detail.html",
        poem=poem,
        poem_html=poem_html,
        comments_html=comments_html,
    )
