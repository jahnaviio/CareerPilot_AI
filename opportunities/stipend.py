"""Pay extraction. Only reports what the posting or the source's structured data actually states; never estimates.
Returns (text, is_paid): is_paid True = pay stated, False = explicitly unpaid, None = not stated."""
from __future__ import annotations

import re

_UNPAID = re.compile(r"\b(unpaid|no stipend|without (a )?stipend|volunteer(ing)? (position|role|internship)|stipend[: ]+(nil|none|not provided))\b", re.I)
_AMOUNT = re.compile(
    r"(?:(?:stipend|salary|compensation|pay|remuneration|ctc|package)[^.\n]{0,50}?)?"
    r"((?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)\s?\d[\d,]*(?:\.\d+)?\s?(?:k|lakhs?|lpa|l)?"
    r"(?:\s?(?:-|–|—|to)\s?(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s?\d[\d,]*(?:\.\d+)?\s?(?:k|lakhs?|lpa|l)?)?"
    r"(?:\s?(?:/|per|a|each)\s?(?:month|mo|hour|hr|year|yr|annum|week))?(?:\s?(?:p\.?m\.?|p\.?a\.?|monthly|annually))?)", re.I)
_PAID_WORDS = re.compile(r"\b(paid internship|paid intern|stipend (is )?(provided|offered|included)|competitive (stipend|pay|compensation)|"
                         r"(monthly|performance[- ]based)? ?stipend|receive a stipend|stipend of|we offer a stipend)\b", re.I)


def extract_stipend(text: str, structured: str = "") -> tuple[str, bool | None]:
    if structured:
        return structured.strip()[:200], True
    t = text or ""
    if _UNPAID.search(t):
        return "Unpaid", False
    for m in _AMOUNT.finditer(t):
        amount = m.group(1).strip()
        ctx = t[max(0, m.start() - 80): m.end() + 40].lower()
        if re.search(r"stipend|salary|compensation|pay|ctc|package|remuneration|per month|/month|per hour|/hour|lpa|annum|a year|per year", ctx):
            return amount[:120], True
    if _PAID_WORDS.search(t):
        return "Paid (amount not stated)", True
    return "", None


def money_range(lo, hi, currency: str = "", interval: str = "") -> str:
    """Format structured salary data from a source (Lever/Ashby/Adzuna) exactly as given."""
    if not lo and not hi:
        return ""
    cur = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get((currency or "").upper(), (currency + " ") if currency else "")
    fmt = lambda v: f"{cur}{int(v):,}"
    rng = f"{fmt(lo)} – {fmt(hi)}" if lo and hi and lo != hi else fmt(lo or hi)
    return f"{rng} per {interval}" if interval else rng
