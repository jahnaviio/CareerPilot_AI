"""Test helpers. EVERYTHING in this file is a TEST FIXTURE: invented companies/people used only to exercise code paths.
None of it is, or can be reached from, production data."""
from __future__ import annotations

import io
import json

from core.llm.base import LLMProvider
from opportunities.http import FetchError, PoliteClient

SAMPLE_RESUME = """Priya Test
priya.test@example.com | +91 98765 43210 | github.com/priyatest | linkedin.com/in/priyatest
SUMMARY
Final-year B.Tech AI student interested in applied machine learning.
EDUCATION
Test Institute of Technology
B.Tech Artificial Intelligence, 2024 - 2028 CGPA: 8.4
SKILLS
Python, SQL, Git, Docker, Excel, PyTorch, Machine Learning
PROJECTS
Document Assistant | RAG
Built a RAG assistant using ChromaDB, sentence transformers and FastAPI that answers questions over PDF notes and was evaluated on 20 questions.
Deployed the service with Docker on Render.
Plant Disease Classifier
Trained a CNN with PyTorch and OpenCV to classify 10 plant diseases and reached 91% accuracy on a held-out test set.
EXPERIENCE
Data Intern - Test Labs, Jun 2025 - Aug 2025
Cleaned and analysed datasets with Pandas and SQL.
CERTIFICATIONS
Azure AI Fundamentals
"""


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(40, y, line[:110]); y -= 14
        if y < 40:
            c.showPage(); y = 800
    c.save()
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    from docx import Document
    d = Document()
    for l in text.splitlines():
        d.add_paragraph(l)
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


def make_scanned_pdf() -> bytes:
    """A PDF with only an image (no text layer)."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(page.rect, pixmap=pix)
    return doc.tobytes()


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self, replies: list[str] | None = None):
        self.replies = list(replies or [])
        self.calls: list[tuple[str, str]] = []

    def complete(self, system, prompt, *, max_tokens=None, temperature=0.2):
        self.calls.append((system, prompt))
        return self.replies.pop(0) if self.replies else "{}"


def ghost_greenhouse(board_jobs: list[dict]) -> dict:
    return {"jobs": board_jobs, "meta": {"total": len(board_jobs)}}


def gh_job(i, title, content="", loc="Bengaluru, India", url_host="job-boards.greenhouse.io", board="acmetest"):
    return {"id": i, "title": title, "location": {"name": loc}, "absolute_url": f"https://{url_host}/{board}/jobs/{i}",
            "updated_at": "2026-11-01T10:00:00-05:00", "first_published": "2026-10-20T10:00:00-05:00", "content": content}


def lever_posting(i, text, commitment="Intern", loc="Remote"):
    return {"id": f"lv-{i}", "text": text, "hostedUrl": f"https://jobs.lever.co/leverco/lv-{i}", "applyUrl": f"https://jobs.lever.co/leverco/lv-{i}/apply",
            "createdAt": 1760000000000, "workplaceType": "remote", "descriptionPlain": "Python and machine learning intern.",
            "categories": {"location": loc, "commitment": commitment, "team": "AI"}, "lists": []}


def ashby_job(i, title, emp="Intern", url="https://jobs.ashbyhq.com/ashbyco/aj-1"):
    return {"id": f"aj-{i}", "title": title, "location": "London", "isRemote": False, "workplaceType": "Hybrid", "employmentType": emp,
            "publishedAt": "2026-11-02T09:00:00+00:00", "jobUrl": url, "applyUrl": url + "/application", "isListed": True,
            "descriptionPlain": "Work on LLM and RAG projects with Python."}


class FakeClient(PoliteClient):
    """Serves canned responses by URL substring; raises FetchError otherwise. No network."""

    def __init__(self, routes: dict[str, object]):
        super().__init__(min_interval=0)
        self.routes = routes
        self.requests: list[str] = []

    def get_json(self, url, retries=3):
        self.requests.append(url)
        for frag, payload in self.routes.items():
            if frag in url:
                if isinstance(payload, Exception):
                    raise payload
                return json.loads(json.dumps(payload))
        raise FetchError("Board not found (404)", 404)

    def check_url(self, url):
        return (False, 404) if "dead" in url else (True, 200)
