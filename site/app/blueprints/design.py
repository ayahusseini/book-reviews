"""Blueprint for the design/ endpoint, which shows the design documents"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.database.models import Post

from app.extensions import cache

design_bp = Blueprint("design", __name__)


@design_bp.route("/all", methods=["GET"])
@cache.cached()
def design_doc_list():
    posts = (
        Post.query.filter(
            Post.book_id.is_(None),
            Post.post_type.in_({"designdoc"}),
        )
        .order_by(Post.post_created_at.desc())
        .all()
    )
    return render_template("designdocs.html", docs=posts)


@design_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def design_doc_detail():
    posts = (
        Post.query.filter(
            Post.book_id.is_(None),
            Post.post_type.in_({"designdoc"}),
        )
        .order_by(Post.post_created_at.desc())
        .all()
    )
    return render_template("designdocs.html", docs=posts)
