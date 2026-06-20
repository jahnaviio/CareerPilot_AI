# CareerPilot AI

An AI-powered internship discovery and application assistant for students — production-quality Streamlit app with a real database, persisted job discovery, personalized matching, and a full application pipeline.

## What's new in this rebuild

The original codebase had a non-functional `app.py` (syntax error — the app could not start), Ollama as a hard dependency, no job persistence, duplicate/dead files, and a single flat `applications` table. This version is a layered rewrite that keeps every original feature while fixing the architecture underneath:

- **Pluggable AI**: works with Claude API, local Ollama, or zero AI configuration (rule-based fallback) — controlled by one env var.
- **Real database**: 7 tables (`users`, `resumes`, `jobs`, `applications`, `saved_jobs`, `notifications`, `job_matches`) with foreign keys and indexes.
- **Persisted job discovery**: jobs from the Remotive API and the seed CSV are saved to the database and de-duplicated, not thrown away after each render.
- **Layered architecture**: `repositories/` (SQL only) → `services/` (business logic) → `agents/` (AI-facing logic) → `ui/` (Streamlit pages). `app.py` is just routing.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env: set LLM_PROVIDER and ANTHROPIC_API_KEY (or leave LLM_PROVIDER=none)

# 3. Run the app
streamlit run app.py
```

The app creates `data/careerpilot.db` automatically on first run. No manual schema setup needed.

### If you have data in the old version

```bash
python scripts/migrate_old_db.py /path/to/old/applications.db
```

Safe to re-run — duplicate rows are skipped automatically.

## Configuring AI (optional but recommended)

Set `LLM_PROVIDER` in `.env` to one of:

| Value | Requires | Used for |
|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` | Best quality; works anywhere you deploy |
| `ollama` | `ollama serve` running locally | Free, local dev only — won't work once deployed |
| `none` | nothing | App still runs; match scoring uses rule-based skill overlap, resume tailoring/cover letters use templates |

Resume Matcher and the dashboard's match scores work in **all three modes**. Resume Tailor requires `claude` or `ollama` (rewriting prose isn't something rule-based logic can do).

## Project structure

```
app.py                      # Thin entry point — routing only
config.py                   # All environment-driven settings

core/
  database.py                # Schema + connection management
  models.py                  # Typed dataclasses
  llm_provider.py             # Pluggable Claude/Ollama/none abstraction

repositories/                # Only place that touches SQL
  user_repository.py
  resume_repository.py
  job_repository.py
  application_repository.py
  saved_job_repository.py
  notification_repository.py
  job_match_repository.py

services/                    # Business logic, orchestrates repositories
  ingestion_service.py         # Pulls + persists jobs (CSV seed + Remotive)
  matching_service.py          # Computes + persists match scores
  notification_service.py      # New job / high match alerts
  stats_service.py             # Dashboard aggregates

agents/                      # AI-facing logic
  resume_parser.py
  resume_matcher.py
  resume_tailor.py
  cover_letter_generator.py
  resume_section_editor.py
  skill_matcher.py             # Shared skill vocabulary + rule-based scoring

ui/
  theme.py / sidebar.py
  components/cards.py          # Stat cards, job cards, match rings
  pages/                       # One file per page

scripts/
  refresh_data.py              # Cron-friendly job refresh (no Streamlit)
  migrate_old_db.py            # One-time import from the old schema

tests/test_smoke.py          # pytest suite (run: pytest tests/ -v)
```

## Scheduled job refresh (recommended)

Run this daily (cron, GitHub Actions, etc.) so jobs and notifications are fresh before students open the app:

```bash
python scripts/refresh_data.py
```

This is independent of the Streamlit UI — it ingests jobs, recomputes matches, and generates notifications in one pass.

## Deployment notes

- **Streamlit Community Cloud**: add `ANTHROPIC_API_KEY` and `LLM_PROVIDER=claude` (or omit for rule-based mode) in the app's Secrets. `OLLAMA_*` settings are irrelevant there since there's no local Ollama server to reach.
- **Self-hosted**: any host that can run `streamlit run app.py` and persist `data/careerpilot.db` to disk between restarts works. For multi-instance deployments, move SQLite to a shared Postgres later — the repository layer is the only code that would need to change.
- **Single-user mode**: v1 ships with one implicit user (`app_config.default_user_id`). The schema is already fully multi-user (every table is keyed by `user_id` with foreign keys), so adding real login is a UI-layer change, not a data-model change.
