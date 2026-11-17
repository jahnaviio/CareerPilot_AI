"""Reusable UI building blocks. Every dynamic string goes through esc(): posting text comes from third parties."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from ui.theme import TOKENS


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def md(h: str) -> None:
    st.markdown(h, unsafe_allow_html=True)


def page_header(title: str, lead: str = "", eyebrow: str = "") -> None:
    md((f'<div class="cp-eyebrow">{esc(eyebrow)}</div>' if eyebrow else "") + f"<h1>{esc(title)}</h1>" + (f'<p class="cp-lead">{esc(lead)}</p>' if lead else ""))


def chip(label: str, kind: str = "neutral") -> str:
    return f'<span class="cp-chip {kind}">{esc(label)}</span>'


def chips(labels, kind: str = "neutral", limit: int | None = None) -> str:
    labels = list(labels)
    shown = labels[:limit] if limit else labels
    out = "".join(chip(l, kind) for l in shown)
    if limit and len(labels) > limit:
        out += chip(f"+{len(labels) - limit}", "neutral")
    return out


def notice(text: str, kind: str = "info") -> None:
    md(f'<div class="cp-notice {kind}" role="status">{esc(text)}</div>')


def empty_state(title: str, body: str) -> None:
    md(f'<div class="cp-empty"><div class="t">{esc(title)}</div><div class="d">{esc(body)}</div></div>')


def bar(pct: float, label: str = "", right: str = "") -> None:
    pct = max(0, min(100, pct))
    head = f'<div class="cp-kv"><span>{esc(label)}</span><span>{esc(right)}</span></div>' if label else ""
    md(f'{head}<div class="cp-bar" role="progressbar" aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100"><i style="width:{pct:.0f}%"></i></div>')


def score_ring(score: float, size: int = 64, label: str = "") -> str:
    r = (size - 8) / 2
    c = 2 * 3.14159265 * r
    off = c * (1 - max(0, min(100, score)) / 100)
    mid = size / 2
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{esc(label)} {score:.0f} out of 100">'
            f'<circle cx="{mid}" cy="{mid}" r="{r}" fill="none" stroke="#ECEEF6" stroke-width="6"/>'
            f'<circle cx="{mid}" cy="{mid}" r="{r}" fill="none" stroke="{TOKENS["accent"]}" stroke-width="6" stroke-linecap="round" '
            f'stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 {mid} {mid})"/>'
            f'<text x="{mid}" y="{mid + 5}" text-anchor="middle" font-size="{size * 0.27:.0f}" font-weight="700" fill="{TOKENS["ink"]}">{score:.0f}</text></svg>')


def stat(n, label: str) -> str:
    return f'<div class="cp-stat"><div class="n">{esc(n)}</div><div class="l">{esc(label)}</div></div>'


def fmt_date(d: datetime | None) -> str:
    return d.strftime("%d %b %Y") if d else ""


def opportunity_card_html(o, match: dict | None) -> str:
    ring = score_ring(match["score"], 60, "Match score") if match else ""
    badges = chip("Internship", "accent") if o.is_internship else chip(o.employment_type.replace("_", " ").title(), "blue")
    if o.is_paid is True:
        badges += chip("Stipend: " + o.stipend_text, "good")
    elif o.is_paid is False:
        badges += chip("Unpaid", "bad")
    else:
        badges += chip("Stipend not stated", "neutral")
    if o.link_kind == "aggregator":
        badges += chip("Listed on Adzuna", "warn")
    if o.status != "open":
        badges += chip("No longer listed by its source" if o.status == "unavailable" else "Not recently re-verified", "warn")
    meta = [esc(o.company)]
    if o.location:
        meta.append(esc(o.location))
    if o.work_mode != "unknown":
        meta.append(esc(o.work_mode.title()))
    meta.append("Posted " + fmt_date(o.posted_at) if o.posted_at else "Posting date not published")
    if o.deadline:
        meta.append("Deadline " + fmt_date(o.deadline))
    req = set(x.lower() for x in (o.required_skills or []))
    matched = [s for s in (match or {}).get("matched_skills", [])]
    missing = [s for s in (match or {}).get("missing_skills", [])]
    skills_html = ""
    if o.required_skills:
        skills_html = ('<div class="cp-section-label">Skills in the posting</div>' + chips(matched, "good") + chips(missing, "warn")
                       + ("" if match else chips(o.required_skills, "neutral", 10)))
    else:
        skills_html = '<div class="cp-sub">No specific skills could be read from this posting.</div>'
    full = (o.description or "").strip().replace("\n", " ")
    desc = esc(full if len(full) <= 260 else full[:260].rsplit(" ", 1)[0] + "…")
    src = "Found on Adzuna" if o.link_kind == "aggregator" else f"Listed by {o.company}"
    ver = "Verified " + fmt_date(o.last_verified_at)
    return (f'<div class="cp-card"><div class="cp-row"><div style="min-width:0"><div class="cp-title">{esc(o.title)}</div>'
            f'<div class="cp-meta">{" · ".join(meta)}</div>{badges}</div><div>{ring}</div></div>'
            f'{skills_html}<p class="cp-sub" style="margin:10px 0 6px">{desc}</p>'
            f'<div class="cp-sub" style="font-size:.76rem">{esc(src)} · {esc(ver.replace("Verified", "checked"))}</div></div>')
