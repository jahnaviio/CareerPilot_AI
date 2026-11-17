"""Turns raw ATS payloads into a common NormalizedOpportunity. No values are invented: missing fields stay empty/None."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nlp.skills import find_skills_in_text
from opportunities.locations import is_india
from opportunities.stipend import extract_stipend

_TAG = re.compile(r"<[^>]+>")
INTERN_TITLE = re.compile(r"\b(intern(ship)?s?|trainee|apprentice|co-?op|working student|werkstudent|student (researcher|programme|program)|summer (analyst|associate)|graduate programme)\b", re.I)


@dataclass
class NormalizedOpportunity:
    source_key: str
    external_id: str
    company: str
    title: str
    description: str
    location: str
    work_mode: str            # remote|hybrid|onsite|unknown
    employment_type: str      # internship|full_time|part_time|contract|unknown
    posting_url: str
    apply_url: str
    posted_at: datetime | None = None
    deadline: datetime | None = None
    from_ats_api: bool = True
    raw_employment: str = ""
    required_skills: list[str] = field(default_factory=list)
    link_kind: str = "official"          # official | aggregator
    stipend_text: str = ""
    is_paid: bool | None = None
    is_india: bool = False
    structured_pay: str = ""            # pay as given by the source's structured fields, if any

    @property
    def is_internship(self) -> bool:
        return self.employment_type == "internship"


def html_to_text(raw: str) -> str:
    raw = html.unescape(raw or "")           # Greenhouse returns HTML-escaped HTML
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", raw)
    raw = re.sub(r"(?i)<li[^>]*>", "• ", raw)
    text = html.unescape(_TAG.sub("", raw))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def detect_employment(title: str, hint: str = "") -> str:
    h = hint.lower()
    if "intern" in h or INTERN_TITLE.search(title):
        return "internship"
    if "part" in h:
        return "part_time"
    if "contract" in h or "temporary" in h or "freelance" in h:
        return "contract"
    if "full" in h or "permanent" in h:
        return "full_time"
    return "full_time" if h == "" and title else "unknown"


def detect_work_mode(location: str, hint: str = "", is_remote: bool | None = None) -> str:
    h = (hint or "").lower().replace("-", "").replace(" ", "")
    if h in ("remote", "hybrid", "onsite"):
        return h
    if is_remote:
        return "remote"
    loc = location.lower()
    if "hybrid" in loc:
        return "hybrid"
    if "remote" in loc:
        return "remote"
    return "unknown"


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def from_epoch_ms(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def extract_deadline(text: str) -> datetime | None:
    """Only returns a deadline when the posting explicitly states one ('apply by / deadline / closes on <date>')."""
    m = re.search(r"(?:application deadline|apply by|deadline|closing date|closes? on|applications close)[:\s-]*"
                  r"(\d{1,2}[ /-](?:[A-Za-z]{3,9}|\d{1,2})[ /,-]*\d{4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", text, re.I)
    if not m:
        return None
    raw = m.group(1).strip().replace(",", "")
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def dedupe_key(company: str, title: str, location: str) -> str:
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return hashlib.sha1(f"{norm(company)}|{norm(title)}|{norm(location)}".encode()).hexdigest()


def finish(o: NormalizedOpportunity) -> NormalizedOpportunity:
    o.required_skills = find_skills_in_text(f"{o.title}\n{o.description}")
    if o.deadline is None:
        o.deadline = extract_deadline(o.description)
    o.stipend_text, o.is_paid = extract_stipend(o.description, o.structured_pay)
    o.is_india = is_india(o.location)
    return o
