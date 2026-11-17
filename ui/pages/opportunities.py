from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from config import settings
from core.db import session_scope
from ml.matching import SENIOR, YEARS, _role_family
from ml.roles import ROLES, ROLE_BY_KEY
from nlp.skills import TAXONOMY
from opportunities.directories import career_pages, platform_links
from opportunities.locations import CITIES, matches_city
from repositories import opportunities as orepo
from services.ingestion import adzuna_enabled, sources_health
from ui import match_view
from ui.components import chip, empty_state, esc, fmt_date, md, notice, opportunity_card_html, page_header
from ui.state import get_app

STEP = 20
NO_RESULTS = "No verified opportunities found for your current filters. Try changing your role or location."
WHERE = ["India + remote anywhere", "India only", "Remote (worldwide)", "Anywhere"]
PAY = ["Stipend / pay stated", "Include 'not stated'", "Everything (incl. unpaid)"]


def _region_ok(o, where: str) -> bool:
    if where == "India + remote anywhere":
        return o.is_india or o.work_mode == "remote"
    if where == "India only":
        return o.is_india
    if where == "Remote (worldwide)":
        return o.work_mode == "remote"
    return True


def _pay_ok(o, pay: str) -> bool:
    if pay == PAY[0]:
        return o.is_paid is True
    if pay == PAY[1]:
        return o.is_paid is not False
    return True


def render(user) -> None:
    app = get_app()
    r, profile = app.load(user.id)
    page_header("Opportunities", "Internships and jobs, India first. Remote roles from anywhere. Ranked against your resume.", "Page 2")
    if (m := st.session_state.pop("flash_page", None)):
        notice(m, "success")
    _freshness(app)
    if r is None:
        empty_state("Add your resume first", "Matches are computed from your analysed resume. Open Resume Intelligence and upload it.")
        _more_places("software", True)
        return
    kind = st.segmented_control("Type", ["Internships", "Jobs"], default="Internships", key="opp_kind", label_visibility="collapsed") or "Internships"
    is_int = kind == "Internships"
    c = st.columns([2, 2, 2])
    where = c[0].selectbox("Where", WHERE, key="opp_where")
    cities = []
    if where in ("India + remote anywhere", "India only"):
        cities = c[1].multiselect("Indian cities (empty = all India)", list(CITIES), key="opp_cities")
    pay = c[2].selectbox("Pay", PAY, index=0 if is_int else 1, key=f"opp_pay_{kind}")
    with st.expander("More filters", expanded=False):
        with session_scope(app.factory) as s:
            companies = orepo.companies(s)
        c = st.columns(3)
        role = c[0].selectbox("Career role", ["Any"] + [x.key for x in ROLES], format_func=lambda k: "Any" if k == "Any" else ROLE_BY_KEY[k].title)
        company = c[1].selectbox("Company", ["Any"] + companies)
        loc = c[2].text_input("Location contains", placeholder="e.g. Karnataka, Hybrid")
        c = st.columns(4)
        mode = c[0].selectbox("Work mode", ["Any", "remote", "hybrid", "onsite"], format_func=str.title)
        level = c[1].selectbox("Experience level", ["Any", "Intern / entry level", "Experienced"])
        posted = c[2].selectbox("Posted", ["Any time", "Last 7 days", "Last 30 days", "Last 90 days"])
        min_score = c[3].slider("Minimum match", 0, 100, 0, step=5)
        skills = st.multiselect("Posting must mention skills", sorted(TAXONOMY))
    with st.spinner("Matching listings to your resume…"):
        matches = app.match_all(user.id, r.id, internship=is_int)
    days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}.get(posted)
    with session_scope(app.factory) as s:
        rows = orepo.list_visible(s, internship=is_int, company=None if company == "Any" else company, location=loc or None,
                                  work_mode=None if mode == "Any" else mode, posted_after=(datetime.now(timezone.utc) - timedelta(days=days)) if days else None)
        hidden = orepo.hidden_ids(s, user.id)
        saved = orepo.saved_ids(s, user.id)
    base, hidden_by_pay = [], 0
    for o in rows:
        if o.id in hidden or o.id not in matches or not _region_ok(o, where):
            continue
        if cities and not (any(matches_city(o.location, ci) for ci in cities) or (where == "India + remote anywhere" and o.work_mode == "remote")):
            continue
        if role != "Any" and _role_family(o.title) != role:
            continue
        if skills and not all(sk in (o.required_skills or []) for sk in skills):
            continue
        senior = bool(SENIOR.search(o.title)) or any(int(m_.group(1)) >= 3 for m_ in YEARS.finditer(o.description or ""))
        if (level == "Intern / entry level" and senior and not o.is_internship) or (level == "Experienced" and not senior):
            continue
        if matches[o.id]["score"] < min_score:
            continue
        if not _pay_ok(o, pay):
            hidden_by_pay += 1
            continue
        base.append(o)
    base.sort(key=lambda o: -matches[o.id]["score"])
    top_kw = ROLE_BY_KEY[role].title if role != "Any" else ROLE_BY_KEY[app.roles(user.id, r.id)[0].key].title
    if not base:
        empty_state("Nothing to show here", NO_RESULTS if rows or _has_any(app) else "No listings yet. Tap “Refresh listings” above to load the latest openings.")
        if hidden_by_pay:
            notice(f"{hidden_by_pay} listing(s) match your other filters but don't state a stipend.", "info")
            if st.button("Show listings that don't state a stipend", key="show_unstated"):
                st.session_state[f"opp_pay_{kind}"] = PAY[1]; st.rerun()
        _more_places(top_kw, is_int, expanded=True)
        return
    key = f"{kind}|{where}|{cities}|{pay}|{role}|{company}|{loc}|{mode}|{level}|{posted}|{min_score}|{skills}"
    if st.session_state.get("opp_sig") != key:
        st.session_state["opp_sig"], st.session_state["opp_limit"] = key, STEP
    limit = st.session_state["opp_limit"]
    n_india = sum(1 for o in base if o.is_india)
    st.caption(f"{len(base)} {kind.lower()} · {n_india} in India · best match first" + (f" · {hidden_by_pay} more hidden because they don't state a stipend" if hidden_by_pay else ""))
    for o in base[:limit]:
        _card(app, user, r, o, matches[o.id], saved)
    if len(base) > limit:
        st.caption(f"Showing {limit} of {len(base)}")
        if st.button(f"Show {min(STEP, len(base) - limit)} more", use_container_width=True, type="primary"):
            st.session_state["opp_limit"] = limit + STEP; st.rerun()
    else:
        st.caption("You’ve reached the end of the loaded listings.")
    _more_places(top_kw, is_int, expanded=len(base) < 15, few=len(base) < 15)


def _more_places(keyword: str, internship: bool, expanded: bool = False, few: bool = False) -> None:
    with st.expander("Find more on Internshala, Unstop, LinkedIn, Naukri and company careers pages", expanded=expanded):
        if few:
            notice("Only a few listings are loaded from employer boards. These platforms hold many more India openings.", "info")
        st.caption(f"Search links for “{keyword}”. They open each site’s own search in a new tab; CareerPilot does not copy their listings.")
        links = platform_links(keyword, internship, False)
        cols = st.columns(3)
        for i, l in enumerate(links):
            with cols[i % 3]:
                st.link_button(l["name"] + " ↗", l["url"], use_container_width=True, help=l["note"])
        if internship:
            wfh = platform_links(keyword, True, True)[0]
            st.link_button("Internshala: work-from-home " + keyword + " ↗", wfh["url"])
        st.divider()
        q = st.text_input("Company careers pages", placeholder="Type a company or category, e.g. Flipkart, fintech, IT services", key="career_q")
        pages = career_pages(q)
        cols = st.columns(3)
        for i, p in enumerate(pages):
            with cols[i % 3]:
                st.link_button(f"{p['company']} · {p['category']}", p["url"], use_container_width=True)
        if not pages:
            st.caption("No company matches that search.")
        st.caption("Links were not click-tested from the build environment; if one has moved, use the site’s own search.")


def _has_any(app) -> bool:
    with session_scope(app.factory) as s:
        return orepo.freshness(s)["open_listings"] > 0


def _card(app, user, r, o, m, saved: set[int]) -> None:
    md(opportunity_card_html(o, m))
    c = st.columns([2, 1, 1, 1])
    with c[0]:
        match_view.apply_button(o)
    with c[1]:
        if o.id in saved:
            st.button("Saved ✓", key=f"sv_{o.id}", disabled=True, use_container_width=True)
        elif st.button("Save", key=f"sv_{o.id}", use_container_width=True):
            with session_scope(app.factory) as s:
                orepo.save(s, user.id, o.id)
            st.rerun()
    with c[2]:
        if st.button("I applied…", key=f"ap_{o.id}", use_container_width=True, help="Confirm after you finish applying on the employer’s site."):
            match_view.confirm_applied_dialog(app, user.id, o.id)
    with c[3]:
        match_view.ai_assist(app, user, r.id, o)
    with st.expander("View match explanation"):
        match_view.match_details(m)
        st.divider()
        match_view.explanation(app, user, r.id, o, "opp")
    with st.expander("Job description"):
        st.text(o.description[:6000] or "No description was published.")
        st.markdown(f"[Original posting ↗]({o.posting_url})")
    if o.id not in saved and st.button("Not interested", key=f"ni_{o.id}", type="tertiary"):
        with session_scope(app.factory) as s:
            orepo.set_not_interested(s, user.id, o.id)
        st.rerun()


def _freshness(app) -> None:
    with session_scope(app.factory) as s:
        f = orepo.freshness(s)
    last = f["last_success_at"]
    c = st.columns([3, 1], vertical_alignment="center")
    with c[0]:
        if last:
            hrs = int((datetime.now(timezone.utc) - last).total_seconds() // 3600)
            md(f'<div class="cp-sub">{f["open_listings"]} open listings loaded · {f["sources_ok"]} of {f["sources_total"]} career sites checked · '
               f'last refresh {fmt_date(last)} ({hrs}h ago){chip(" stale — refresh recommended", "warn") if hrs > 72 else ""}</div>')
        else:
            md('<div class="cp-sub">No listings loaded yet.</div>')
    with c[1]:
        cooling = bool(last and (datetime.now(timezone.utc) - last) < timedelta(minutes=15))
        if st.button("Refresh listings", disabled=cooling, use_container_width=True, help="Fetches current postings. Available every 15 minutes."):
            with st.spinner("Checking company career sites for new openings…"):
                summary = app.refresh_opportunities()
            st.session_state["flash_page"] = f"{summary.ok} of {len(summary.results)} sources responded; {sum(x.new for x in summary.results)} new listing(s)."
            st.rerun()
    with st.expander("Where these listings come from"):
        rows = sources_health(app.factory)
        ok = [x for x in rows if x.last_status == "ok"]
        st.caption(f"Listings are read from the career pages of {len(ok)} companies" + (" and from Adzuna." if adzuna_enabled() else ".") + " Each card links to the original posting.")
        for src in ok:
            if src.jobs_seen:
                st.caption(f"**{src.company}** — {src.jobs_seen} openings")
