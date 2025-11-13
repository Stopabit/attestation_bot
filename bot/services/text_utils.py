from __future__ import annotations

import re
from bs4 import BeautifulSoup

WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return WHITESPACE_RE.sub(" ", text)
