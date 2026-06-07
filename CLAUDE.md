# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (run from `backend/`)

```bash
# Setup (first time)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head

# Dev server
uvicorn app.main:app --reload

# Tests
pytest                                      # all tests
pytest tests/test_auth.py                   # single file
pytest tests/test_auth.py::test_login_ok    # single test

# Lint / format
ruff check .
ruff format .
```

### Frontend (run from `frontend/`)

```bash
pnpm install
pnpm dev        # dev server on :3000
pnpm test       # unit tests (vitest)
pnpm build
pnpm lint
```

### Infrastructure

```bash
# Start required services (run from repo root)
docker compose up -d postgres redis minio minio-init

# Full Docker stack (no local Python/Node needed)
docker compose build backend
docker compose up -d postgres redis minio minio-init backend
docker compose --profile full up -d frontend      # optional frontend container
docker compose --profile workers up -d worker     # only if SYNC_TASKS=false
```

## Architecture

### Request flow

```
Browser → Next.js (3000) → FastAPI (8000) → PostgreSQL / MinIO / Redis
                                           → Celery worker (optional)
```

### Backend layer structure

- **`app/api/v1/`** — Route handlers: `auth`, `users`, `resumes`, `jobs`, `analyses`. Thin: validate input, call service, return response.
- **`app/services/`** — Business logic coordinating DB + domain + workers: `analysis_service`, `resume_service`, `job_service`, `auth_service`, `user_service`.
- **`app/domain/`** — Pure Python, zero FastAPI imports. This is where the core ATS logic lives:
  - `extraction/` — PDF (PyMuPDF) and DOCX text extraction
  - `parsing/` — CV and job offer parsers (section detection, skills/contact/language extraction)
  - `matching/` — keyword matching with synonyms, fuzzy matching (rapidfuzz), language comparison
  - `scoring/engine.py` — Computes the 0–100 score across 6 categories (parseability 20 + structure 15 + contact 10 + keywords 20 + job_match 20 + writing 10, minus penalties up to 5)
  - `ats/rules_engine.py` — ATS issue detection rules (tables, multi-column, OCR, missing sections, etc.)
  - `recommendations/generator.py` — AI-powered suggestions
- **`app/workers/`** — Celery tasks: `parse_resume`, `parse_job`, `run_analysis`, `generate_recommendations`, `index_embeddings`. `dispatch.py` routes tasks inline or to Celery based on `SYNC_TASKS`.
- **`app/integrations/`** — External system adapters: `storage/s3_client.py` (MinIO), `llm/factory.py`, `embeddings/local.py`, `reports/pdf_export.py` (WeasyPrint).
- **`app/schemas/`** — Pydantic request/response models. `schemas/parsed.py` contains `ParsedResume`, `AnalysisResult`, `ScoreCategories`.
- **`app/core/`** — `security.py` (JWT + bcrypt), `exceptions.py` (typed `AppException`), `cookies.py` (cookie name constants).

### SYNC_TASKS flag

`SYNC_TASKS=true` (default in dev and tests) runs Celery tasks synchronously inline — no worker process needed. `SYNC_TASKS=false` sends tasks to Redis/Celery. Tests in `conftest.py` force `SYNC_TASKS=true` and use SQLite (aiosqlite).

### Auth

Dual-mode: httpOnly cookie (`access_token`) **or** `Authorization: Bearer` header. `app/api/deps.py:get_current_user` checks cookie first, then header.

### Frontend structure

- `src/app/` — Next.js App Router pages. `(protected)/` route group wraps all authenticated views.
- `src/components/` — Organized by domain: `analysis/`, `analyze/`, `auth/`, `dashboard/`, `marketing/`, `resumes/`, `ui/` (shadcn).
- `src/lib/api/` — Typed API clients (`client.ts` wraps fetch with credentials).
- `src/types/` — Shared TypeScript types mirroring backend schemas.

### Data files

`backend/data/skills_es_en.json` and `synonyms.json` are static lookup tables used by the matching domain layer. Edit these to add skill synonyms or cross-language skill mappings.

### Config

All settings live in `backend/app/config.py` (Pydantic `BaseSettings`). The `.env` at the repo root is the primary source; `backend/.env` is a fallback. Key env vars: `DATABASE_URL`, `SYNC_TASKS`, `SECRET_KEY`, `LLM_PROVIDER`, `S3_*`, `CORS_ORIGINS`.
