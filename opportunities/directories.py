"""Link directories (NOT job listings): search pages on the big platforms and official careers pages of well-known companies.
Nothing here is scraped. These are plain links the user opens in their own browser; each platform shows its own current listings.
URL patterns follow each site's public search pages; they were not click-tested from the build sandbox."""
from __future__ import annotations

import re
from urllib.parse import quote, quote_plus


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def platform_links(keyword: str, internship: bool = True, remote: bool = False) -> list[dict]:
    """Search links for the user's role keyword, e.g. 'machine learning'."""
    kw = keyword.strip() or "software"
    slug = _slug(kw)
    q = quote_plus(f"{kw} intern" if internship else kw)
    links = []
    if internship:
        links.append({"name": "Internshala", "url": f"https://internshala.com/internships/{'work-from-home-' if remote else ''}{slug}-internship/",
                      "note": "Shows stipend on every card; filter by stipend on the site."})
        links.append({"name": "Unstop", "url": f"https://unstop.com/internships?searchTerm={quote(kw)}", "note": "Internships and competitions."})
    links += [
        {"name": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={q}&location=India" + ("&f_JT=I" if internship else "") + ("&f_WT=2" if remote else ""), "note": "Needs your LinkedIn login to apply."},
        {"name": "Naukri", "url": f"https://www.naukri.com/{slug}-{'intern' if internship else ''}{'-' if internship else ''}jobs-in-india".replace("--", "-"), "note": "Large India job board."},
        {"name": "foundit", "url": f"https://www.foundit.in/srp/results?query={q}&locations=India", "note": "Formerly Monster India."},
        {"name": "Indeed India", "url": f"https://in.indeed.com/jobs?q={q}&l=India" + ("&sc=0kf%3Aattr%28DSQF7%29%3B" if remote else ""), "note": "Aggregates employer postings."},
        {"name": "Wellfound", "url": "https://wellfound.com/jobs", "note": "Startup jobs; search on the site."},
        {"name": "Work at a Startup (Y Combinator)", "url": "https://www.workatastartup.com/jobs", "note": "YC-backed startups, many remote."},
    ]
    return links


# (company, category, careers URL)
CAREER_PAGES: list[tuple[str, str, str]] = [
    ("Google", "Big tech", "https://www.google.com/about/careers/applications/jobs/results/?location=India&q=intern"),
    ("Microsoft", "Big tech", "https://jobs.careers.microsoft.com/global/en/search?q=intern&lc=India"),
    ("Amazon", "Big tech", "https://www.amazon.jobs/en/search?base_query=intern&loc_query=India"),
    ("Adobe", "Big tech", "https://careers.adobe.com/"), ("Salesforce", "Big tech", "https://careers.salesforce.com/"),
    ("Oracle", "Big tech", "https://careers.oracle.com/"), ("SAP", "Big tech", "https://jobs.sap.com/"), ("Cisco", "Big tech", "https://jobs.cisco.com/"),
    ("IBM", "Big tech", "https://www.ibm.com/in-en/careers"), ("Intuit", "Big tech", "https://jobs.intuit.com/"),
    ("NVIDIA", "Big tech", "https://www.nvidia.com/en-in/about-nvidia/careers/"), ("PayPal", "Fintech", "https://careers.pypl.com/home/"),
    ("Flipkart", "E-commerce", "https://www.flipkartcareers.com/"), ("Myntra", "E-commerce", "https://careers.myntra.com/"),
    ("Meesho", "E-commerce", "https://www.meesho.io/jobs"), ("Swiggy", "Consumer app", "https://careers.swiggy.com/"),
    ("Zomato", "Consumer app", "https://www.zomato.com/careers"), ("PhonePe", "Fintech", "https://www.phonepe.com/careers/"),
    ("Razorpay", "Fintech", "https://razorpay.com/jobs/"), ("Paytm", "Fintech", "https://paytm.com/careers/"),
    ("Zoho", "Product company", "https://www.zoho.com/careers/"), ("Freshworks", "Product company", "https://www.freshworks.com/company/careers/"),
    ("TCS", "IT services", "https://www.tcs.com/careers"), ("Infosys", "IT services", "https://www.infosys.com/careers/"),
    ("Wipro", "IT services", "https://careers.wipro.com/"), ("Accenture", "IT services", "https://www.accenture.com/in-en/careers"),
    ("Capgemini", "IT services", "https://www.capgemini.com/in-en/careers/"), ("Deloitte", "Consulting", "https://www.deloitte.com/in/en/careers.html"),
    ("EY", "Consulting", "https://www.ey.com/en_in/careers"),
]


def career_pages(query: str = "") -> list[dict]:
    q = query.strip().lower()
    return [{"company": c, "category": cat, "url": u} for c, cat, u in CAREER_PAGES if not q or q in c.lower() or q in cat.lower()]
