"""Translate a page's text with Google Translate in the browser (Round 15).

No API key, nothing stored: the text goes in the address of
https://translate.google.com/?sl=auto&tl=en&text=...&op=translate. Long text is cut at a
sentence break so the address stays short enough for the browser.
"""
import re
from urllib.parse import quote

BASE = "https://translate.google.com/"
LIMIT = 4500


def cut_at_sentence(text, limit=LIMIT):
    """(text up to `limit` characters ending at a sentence break, cut?)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    head = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?][\"')\]]*(?=\s)", head)]
    if ends and ends[-1] >= limit // 2:
        return head[:ends[-1]].rstrip(), True
    space = head.rfind(" ")
    return (head[:space] if space > limit // 2 else head).rstrip(), True


def translate_url(text, limit=LIMIT):
    """(url, cut): source language auto, target English; cut is True when only the first
    part of the text is in the address."""
    sent, cut = cut_at_sentence(text, limit)
    return f"{BASE}?sl=auto&tl=en&text={quote(sent, safe='')}&op=translate", cut
