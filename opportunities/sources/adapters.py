"""Adapters for public ATS job-board APIs (documented, keyless, read-only GET endpoints):

  Greenhouse  GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
  Lever       GET https://api.lever.co/v0/postings/{site}?mode=json   (EU: api.eu.lever.co)
  Ashby       GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true

Parsing is defensive: a missing field becomes empty, never a made-up value."""
from __future__ import annotations

from typing import Any, Callable

from opportunities.stipend import money_range
from opportunities.normalize import (NormalizedOpportunity, detect_employment, detect_work_mode, finish,
                                     from_epoch_ms, html_to_text, parse_iso)


def greenhouse_url(board: str, **_) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


def lever_url(board: str, region: str = "", **_) -> str:
    host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
    return f"https://{host}/v0/postings/{board}?mode=json"


def ashby_url(board: str, **_) -> str:
    return f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"


def parse_greenhouse(data: Any, entry: dict) -> list[NormalizedOpportunity]:
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if jobs is None:
        raise ValueError("Unexpected Greenhouse payload (no 'jobs')")
    out = []
    key = f"greenhouse:{entry['board']}"
    for j in jobs:
        url = j.get("absolute_url") or ""
        if not (j.get("id") and j.get("title") and url):
            continue
        loc = (j.get("location") or {}).get("name", "") or ""
        out.append(finish(NormalizedOpportunity(
            source_key=key, external_id=str(j["id"]), company=entry["company"], title=j["title"].strip(),
            description=html_to_text(j.get("content", "")), location=loc,
            work_mode=detect_work_mode(loc), employment_type=detect_employment(j["title"]),
            posting_url=url, apply_url=url,   # the hosted posting page contains the application form
            posted_at=parse_iso(j.get("first_published") or j.get("updated_at")))))
    return out


def _lever_pay(sr) -> str:
    if not isinstance(sr, dict):
        return ""
    return money_range(sr.get("min"), sr.get("max"), sr.get("currency", ""), str(sr.get("interval", "")).replace("per-", "").replace("ly", "") if sr.get("interval") else "")


def parse_lever(data: Any, entry: dict) -> list[NormalizedOpportunity]:
    if not isinstance(data, list):
        raise ValueError("Unexpected Lever payload (expected a list)")
    out = []
    key = f"lever:{entry['board']}"
    for j in data:
        hosted = j.get("hostedUrl") or ""
        apply_url = j.get("applyUrl") or hosted
        if not (j.get("id") and j.get("text") and hosted):
            continue
        cats = j.get("categories") or {}
        loc = cats.get("location") or ", ".join(cats.get("allLocations") or []) or ""
        commitment = cats.get("commitment") or ""
        out.append(finish(NormalizedOpportunity(
            source_key=key, external_id=str(j["id"]), company=entry["company"], title=j["text"].strip(),
            description=(j.get("descriptionPlain") or html_to_text(j.get("description", ""))) + "\n" + "\n".join(
                f"{l.get('text','')}\n{html_to_text(l.get('content',''))}" for l in (j.get("lists") or [])),
            location=loc, work_mode=detect_work_mode(loc, j.get("workplaceType", "")),
            employment_type=detect_employment(j["text"], commitment), raw_employment=commitment,
            posting_url=hosted, apply_url=apply_url, posted_at=from_epoch_ms(j.get("createdAt")),
            structured_pay=_lever_pay(j.get("salaryRange")))))
    return out


def _ashby_pay(c) -> str:
    if isinstance(c, dict):
        return str(c.get("compensationTierSummary") or c.get("scrapeableCompensationSalarySummary") or "")[:200]
    return ""


_ASHBY_EMP = {"fulltime": "full_time", "parttime": "part_time", "intern": "internship", "contract": "contract", "temporary": "contract"}


def parse_ashby(data: Any, entry: dict) -> list[NormalizedOpportunity]:
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if jobs is None:
        raise ValueError("Unexpected Ashby payload (no 'jobs')")
    out = []
    key = f"ashby:{entry['board']}"
    for j in jobs:
        if j.get("isListed") is False:
            continue
        url = j.get("jobUrl") or ""
        if not (j.get("id") and j.get("title") and url):
            continue
        raw_emp = str(j.get("employmentType") or "")
        emp = _ASHBY_EMP.get(raw_emp.lower())
        if not emp or emp == "full_time":
            emp = "internship" if detect_employment(j["title"]) == "internship" else (emp or "unknown")
        loc = j.get("location") or ""
        out.append(finish(NormalizedOpportunity(
            source_key=key, external_id=str(j["id"]), company=entry["company"], title=j["title"].strip(),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")), location=loc,
            work_mode=detect_work_mode(loc, j.get("workplaceType", ""), j.get("isRemote")),
            employment_type=emp, raw_employment=raw_emp, posting_url=url, apply_url=j.get("applyUrl") or url,
            posted_at=parse_iso(j.get("publishedAt")), structured_pay=_ashby_pay(j.get("compensation")))))
    return out


ADAPTERS: dict[str, tuple[Callable[..., str], Callable[[Any, dict], list[NormalizedOpportunity]]]] = {
    "greenhouse": (greenhouse_url, parse_greenhouse),
    "lever": (lever_url, parse_lever),
    "ashby": (ashby_url, parse_ashby),
}


# ---------------------------------------------------------------------------------------------
# Adzuna (licensed job-search API with an India index; needs a free key from developer.adzuna.com).
# These listings come through an aggregator, so they are labelled "via Adzuna" and are NEVER shown as employer-official.
# GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?app_id=..&app_key=..&what=..&results_per_page=..
# ---------------------------------------------------------------------------------------------
def adzuna_url(app_id: str, app_key: str, what: str, page: int = 1, country: str = "in", where: str = "", per_page: int = 50) -> str:
    from urllib.parse import urlencode
    q = {"app_id": app_id, "app_key": app_key, "results_per_page": per_page, "what": what, "content-type": "application/json"}
    if where:
        q["where"] = where
    return f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?{urlencode(q)}"


def parse_adzuna(data: Any, country: str = "in") -> list[NormalizedOpportunity]:
    results = data.get("results") if isinstance(data, dict) else None
    if results is None:
        raise ValueError("Unexpected Adzuna payload (no 'results')")
    out = []
    for j in results:
        url = j.get("redirect_url") or ""
        title = (j.get("title") or "").strip()
        if not (j.get("id") and title and url):
            continue
        loc = (j.get("location") or {}).get("display_name", "") or ""
        pay = ""
        if str(j.get("salary_is_predicted", "0")) != "1":      # never present a predicted salary as stated pay
            cur = "INR" if country == "in" else ""
            pay = money_range(j.get("salary_min"), j.get("salary_max"), cur, "year")
        desc = html_to_text(j.get("description", ""))
        out.append(finish(NormalizedOpportunity(
            source_key=f"adzuna:{country}", external_id=str(j["id"]), company=((j.get("company") or {}).get("display_name") or "Company not stated"),
            title=title, description=desc, location=loc, work_mode=detect_work_mode(loc + " " + title),
            employment_type=detect_employment(title, j.get("contract_time", "") or ""), posting_url=url, apply_url=url,
            posted_at=parse_iso(j.get("created")), from_ats_api=False, link_kind="aggregator", structured_pay=pay)))
    return out
