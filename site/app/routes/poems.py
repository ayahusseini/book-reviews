"""Routes for /poems."""

from __future__ import annotations

from flask import Blueprint, abort, render_template

from app.backend.models import Poem
from app.backend.markdown import render_markdown_to_safe_html
from app.extensions import cache
from app.routes.helper import recently_created_poem_ids

poems_bp = Blueprint("poems", __name__)


@poems_bp.route("/", methods=["GET"])
@cache.cached()
def poem_list():
    poems = Poem.query.order_by(Poem.poem_updated_at.desc()).all()
    return render_template(
        "poems.html", poems=poems, new_poem_ids=recently_created_poem_ids()
    )


@poems_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def poem_detail(slug: str):
    poem = Poem.query.filter_by(poem_slug=slug).first()
    if not poem:
        abort(404)

    parts = poem.poem_body_markdown.split("\n---\n", 1)
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
