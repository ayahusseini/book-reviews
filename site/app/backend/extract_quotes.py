"""Logic to handle quote-extraction from a markdown body"""

import hashlib
import re

from dataclasses import dataclass

# non-greedy match of ```ad-quote ... ``` blocks
AD_QUOTE_RE = re.compile(
    r"```ad-quote\n(.*?)```",
    re.DOTALL,
)


@dataclass
class Quote:
    quote_text: str

    @staticmethod
    def quote_hash(text: str) -> str:
        """Return an 8-char hex hash of the first min(100, len)
        chars of text.
        """
        sample = text[: min(100, len(text))]
        return hashlib.sha1(sample.encode("utf-8")).hexdigest()[:8]

    @property
    def quote_slug(self) -> str:
        """Return a slug for a quote post."""
        return f"quote-{self.quote_hash(self.quote_text)}"


def extract_ad_quotes(body: str) -> list[Quote]:
    """Return the text content of every ```ad-quote block in body."""
    return [
        Quote(quote_text=m.group(1).strip())
        for m in AD_QUOTE_RE.finditer(body)
    ]


def re_match_to_blockquote(m: re.Match) -> str:
    """
    Prefix all lines in a re.Match object with '>' such that it
    is treated as a blockquote
    """
    text = m.group(1).strip()
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    return quoted


def replace_ad_quotes_with_blockquotes(body: str) -> str:
    """Replace ```ad-quote blocks with Markdown blockquote syntax."""
    return AD_QUOTE_RE.sub(re_match_to_blockquote, body)
