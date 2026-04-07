"""Tests for the import-code CLI command.

Uses tmp_path to create real temporary code files so the importer runs
exactly as it does in production.
"""

import pytest

from app.cli import import_code_command
from app.database.models import Post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(app, tmp_path, author="aya"):
    runner = app.test_cli_runner()
    return runner.invoke(
        import_code_command,
        ["--path", str(tmp_path), "--author", author],
    )


# ---------------------------------------------------------------------------
# Error / empty cases
# ---------------------------------------------------------------------------


class TestImportCodeErrors:
    def test_nonexistent_directory_exits_with_error(self, app, db):
        runner = app.test_cli_runner()
        result = runner.invoke(
            import_code_command,
            ["--path", "/no/such/directory", "--author", "aya"],
        )
        assert result.exit_code != 0

    def test_empty_directory_reports_no_files(self, app, db, tmp_path):
        result = invoke(app, tmp_path)
        assert "No supported code files found" in result.output
        assert result.exit_code == 0

    def test_unsupported_extension_skipped(self, app, db, tmp_path):
        (tmp_path / "notes.txt").write_text("some notes", encoding="utf-8")
        (tmp_path / "README").write_text("readme", encoding="utf-8")
        result = invoke(app, tmp_path)
        assert "No supported code files found" in result.output
        assert Post.query.count() == 0


# ---------------------------------------------------------------------------
# Post content and metadata
# ---------------------------------------------------------------------------


class TestImportCodeContent:
    def test_sql_file_creates_post(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="demo.sql").first() is not None

    def test_slug_is_full_filename_not_stem(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="demo.sql").first() is not None
        assert Post.query.filter_by(post_slug="demo").first() is None

    def test_post_type_is_code(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="demo.sql").first()
        assert post.post_type == "code"

    def test_author_set_from_cli_arg(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path, author="testauthor")
        post = Post.query.filter_by(post_slug="demo.sql").first()
        assert post.post_author == "testauthor"

    def test_body_wrapped_in_sql_fence(self, app, db, tmp_path):
        (tmp_path / "query.sql").write_text(
            "SELECT * FROM foo;", encoding="utf-8"
        )
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="query.sql").first()
        assert post.post_body_markdown.startswith("```sql\n")
        assert "SELECT * FROM foo;" in post.post_body_markdown
        assert post.post_body_markdown.endswith("\n```")

    def test_python_file_uses_python_language_tag(self, app, db, tmp_path):
        (tmp_path / "script.py").write_text("print('hello')", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="script.py").first()
        assert post.post_body_markdown.startswith("```python\n")

    def test_title_is_full_filename(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="demo.sql").first()
        assert post.post_title == "demo.sql"

    def test_post_has_no_book(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="demo.sql").first()
        assert post.book is None


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    @pytest.mark.parametrize(
        "filename, expected_lang",
        [
            ("query.sql", "sql"),
            ("script.py", "python"),
            ("app.js", "javascript"),
            ("types.ts", "typescript"),
            ("run.sh", "bash"),
            ("config.json", "json"),
            ("conf.yaml", "yaml"),
            ("conf.yml", "yaml"),
        ],
    )
    def test_correct_language_tag_for_extension(
        self, app, db, tmp_path, filename, expected_lang
    ):
        (tmp_path / filename).write_text("code", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug=filename).first()
        assert post is not None
        assert post.post_body_markdown.startswith(f"```{expected_lang}\n")


# ---------------------------------------------------------------------------
# Re-import behaviour
# ---------------------------------------------------------------------------


class TestReimport:
    def test_reimport_does_not_duplicate(self, app, db, tmp_path):
        (tmp_path / "demo.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="demo.sql").count() == 1

    def test_reimport_updates_body_when_content_changes(
        self, app, db, tmp_path
    ):
        f = tmp_path / "demo.sql"
        f.write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        f.write_text("SELECT 2;", encoding="utf-8")
        invoke(app, tmp_path)
        post = Post.query.filter_by(post_slug="demo.sql").first()
        assert "SELECT 2;" in post.post_body_markdown
        assert "SELECT 1;" not in post.post_body_markdown


# ---------------------------------------------------------------------------
# Multi-file and directory traversal
# ---------------------------------------------------------------------------


class TestMultipleFiles:
    def test_multiple_files_all_imported(self, app, db, tmp_path):
        (tmp_path / "query.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "script.py").write_text("x = 1", encoding="utf-8")
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="query.sql").first() is not None
        assert Post.query.filter_by(post_slug="script.py").first() is not None

    def test_mixed_extensions_only_supported_imported(self, app, db, tmp_path):
        (tmp_path / "query.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="query.sql").first() is not None
        assert Post.query.filter_by(post_slug="notes.txt").first() is None

    def test_file_in_subdirectory_is_found(self, app, db, tmp_path):
        sub = tmp_path / "examples"
        sub.mkdir()
        (sub / "nested.sql").write_text("SELECT 1;", encoding="utf-8")
        invoke(app, tmp_path)
        assert Post.query.filter_by(post_slug="nested.sql").first() is not None
