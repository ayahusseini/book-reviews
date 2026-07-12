"""Tests for site/content/extract_quotes.py."""

from app.backend.extract_quotes import (
    ExtractedQuote,
    extract_ad_quotes,
    replace_ad_quotes_with_blockquotes,
)


class TestExtractAdQuotes:
    def test_finds_single_quote(self):
        body = "Before.\n```ad-quote\nA passage.\n```\nAfter."
        quotes = extract_ad_quotes(body)
        assert len(quotes) == 1
        assert quotes[0].quote_text == "A passage."

    def test_finds_multiple_quotes(self):
        body = "```ad-quote\nFirst.\n```\nMiddle.\n```ad-quote\nSecond.\n```"
        quotes = extract_ad_quotes(body)
        assert len(quotes) == 2
        assert quotes[0].quote_text == "First."
        assert quotes[1].quote_text == "Second."

    def test_no_quotes_returns_empty(self):
        assert extract_ad_quotes("Just plain text.") == []

    def test_multiline_quote_captured(self):
        body = "```ad-quote\nLine one.\nLine two.\n```"
        quotes = extract_ad_quotes(body)
        assert "Line one." in quotes[0].quote_text
        assert "Line two." in quotes[0].quote_text

    def test_quote_text_is_stripped(self):
        body = "```ad-quote\n\n  A padded passage.  \n\n```"
        quotes = extract_ad_quotes(body)
        assert quotes[0].quote_text == "A padded passage."


class TestReplaceAdQuotesWithBlockquotes:
    def test_replaces_block_with_blockquote_syntax(self):
        body = "```ad-quote\nA quote.\n```"
        result = replace_ad_quotes_with_blockquotes(body)
        assert "```ad-quote" not in result
        assert "> A quote." in result

    def test_multiline_quote_each_line_prefixed(self):
        body = "```ad-quote\nLine one.\nLine two.\n```"
        result = replace_ad_quotes_with_blockquotes(body)
        assert "> Line one." in result
        assert "> Line two." in result

    def test_text_outside_blocks_preserved(self):
        body = "Before.\n```ad-quote\nExtractedQuote.\n```\nAfter."
        result = replace_ad_quotes_with_blockquotes(body)
        assert "Before." in result
        assert "After." in result

    def test_no_blocks_returns_body_unchanged(self):
        text = "No ad-quote blocks here."
        assert replace_ad_quotes_with_blockquotes(text) == text


class TestQuoteSlug:
    def test_slug_has_quote_prefix(self):
        q = ExtractedQuote(quote_text="Some text.")
        assert q.quote_slug.startswith("quote-")

    def test_slug_is_deterministic(self):
        q1 = ExtractedQuote(quote_text="Same text.")
        q2 = ExtractedQuote(quote_text="Same text.")
        assert q1.quote_slug == q2.quote_slug

    def test_different_text_different_slug(self):
        assert (
            ExtractedQuote(quote_text="Text A.").quote_slug
            != ExtractedQuote(quote_text="Text B.").quote_slug
        )

    def test_slug_uses_only_first_100_chars(self):
        short_text = "A" * 50
        long_text = "A" * 50 + "B" * 200
        # Both start the same 50 chars, but long_text goes beyond 100 chars
        # with unique content after 100 — same first 100 → same slug
        same_prefix = "A" * 100
        different_suffix_1 = same_prefix + "X"
        different_suffix_2 = same_prefix + "Y"
        assert (
            ExtractedQuote(quote_text=different_suffix_1).quote_slug
            == ExtractedQuote(quote_text=different_suffix_2).quote_slug
        )
