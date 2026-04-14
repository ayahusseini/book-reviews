"""Routes for /design."""

from __future__ import annotations

from flask import Blueprint, render_template

from app.backend.models import Post
from app.extensions import cache

design_bp = Blueprint("design", __name__)


@design_bp.route("/all", methods=["GET"])
@cache.cached()
def design_doc_list():
    posts = (
        Post.query.filter_by(post_type="designdoc")
        .order_by(Post.post_created_at.desc())
        .all()
    )
    return render_template("designdocs.html", docs=posts)
