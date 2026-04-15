# Feature Roadmap Design
**Date:** 2026-04-15
**App:** tailor-your-document (AI-Powered Job-Tailored Resume Generator)
**Approach:** Approach B — New focused pages per feature

---

## Overview

Three features and Docker containerization are being added to the existing Streamlit multi-page app:

1. **Editable Submission Records** — edit status, notes, and job URL per submission; delete submissions
2. **Multiple Portfolio Support** — save, name, and switch between multiple base CVs
3. **Job URL Scraping + Keyword Detection + Suggestions** — scrape job pages, extract keywords, suggest resume rewrites
4. **Docker Containerization** — single-container setup for local dev and deployment anywhere

All changes are additive. No existing modules are deleted.

---

## Overall Architecture

### New Pages
| File | Purpose |
|------|---------|
| `pages/submission_detail.py` | View and edit a single submission's status, notes, job URL; delete submission |

### Modified Pages
| File | Change |
|------|--------|
| `pages/my_submissions.py` | Add status badge column, "✏️ Edit" button per row linking to submission detail |
| `pages/portfolio.py` | Add named portfolio manager panel (create, rename, set active, delete) |
| `pages/new_submission.py` | Job description input becomes two tabs (paste / scrape); add keyword panel; add portfolio selector |

### New Support Modules
| File | Purpose |
|------|---------|
| `support/job_scraper.py` | Scrape job URLs, extract keywords via LLM, generate resume rewrite suggestions |
| `support/portfolio_manager.py` | Save/load/list/delete named portfolios; manage active portfolio |

### Modified Support Modules
| File | Change |
|------|--------|
| `support/submission_manager.py` | DB migration for new columns; new `update_submission_metadata()` and `delete_submission()` functions |

### Database Changes
- Migrate `submissions` table on startup: add `status TEXT DEFAULT 'Applied'`, `notes TEXT`, `job_url TEXT`
- Migration is safe — uses `ALTER TABLE ... ADD COLUMN` only if column does not exist

### Portfolio Storage
- File-based: `output/portfolios/<name>.pkl` per portfolio
- `output/portfolios/portfolios.json` index tracks name, created date, last modified, active flag
- On first run after this change: existing portfolio auto-migrated to `output/portfolios/Default.pkl`, set as active

### New Dependencies
- `beautifulsoup4` — HTML parsing for job scraping
- `playwright` — headless browser fallback for JS-rendered job pages (LinkedIn, Greenhouse, etc.)

---

## Feature 1: Editable Submission Records

### DB Migration (`support/submission_manager.py`)
- `initialize_db()` runs `ALTER TABLE submissions ADD COLUMN` for each new column if not exists:
  - `status TEXT DEFAULT 'Applied'`
  - `notes TEXT`
  - `job_url TEXT`
- New function: `update_submission_metadata(submission_id, status, notes, job_url)`
- New function: `delete_submission(submission_id)`

### Status Options (fixed list)
```
Applied → Interviewing → Technical Assessment → Offer → Rejected → Withdrawn
```

### `pages/submission_detail.py`
- Accessed via `st.query_params` with `?id=<submission_id>` set by Edit button in My Submissions
- **Read-only fields:** Company, Position, Submission Date
- **Editable fields:**
  - `Status` — selectbox with fixed status list
  - `Job URL` — text input
  - `Notes` — text area (free text, no limit)
- **Actions:**
  - "💾 Save Changes" — calls `update_submission_metadata()`; shows success toast
  - "🗑️ Delete Submission" — requires confirmation checkbox before executing `delete_submission()`; navigates back to My Submissions after delete
  - "← Back to Submissions" — navigation link

### `pages/my_submissions.py` Changes
- Status column added to submissions table with colour badge:
  - 🟢 Offer, 🔴 Rejected, 🔵 Applied, 🟡 Interviewing, 🟠 Technical Assessment, ⚪ Withdrawn
- Each row gains an "✏️ Edit" button that sets `st.query_params` and navigates to `submission_detail`

---

## Feature 3: Multiple Portfolio Support

### `support/portfolio_manager.py`
**Functions:**
- `save_portfolio(name, cv_object)` — serialises cv_object to `output/portfolios/<name>.pkl`; updates index
- `load_portfolio(name)` — deserialises and returns cv_object
- `list_portfolios()` — returns list of `{name, created_date, last_modified, is_active}`
- `set_active_portfolio(name)` — updates `is_active` flag in index
- `get_active_portfolio()` — loads and returns the currently active cv_object
- `delete_portfolio(name)` — removes `.pkl` file and index entry; if deleted portfolio was active, sets most recently modified as new active
- `rename_portfolio(old_name, new_name)` — renames file and updates index

### `pages/portfolio.py` Changes
- New **"My Portfolios"** section at the top of the page (above upload):
  - Lists all saved portfolios in a table: Name, Last Modified, Active (⭐)
  - Per-row buttons: "📂 Load", "⭐ Set Active", "🗑️ Delete"
  - "➕ New Portfolio" button — clears current session state, proceeds to upload flow
- After processing a CV, user is prompted to name the portfolio before saving (default: `"Portfolio 1"`, `"Portfolio 2"`, etc.)
- Active portfolio name shown in a persistent info banner

### `pages/new_submission.py` Changes
- Portfolio selector dropdown shown before job description input: `"Generating with: <active_portfolio_name> ▼"`
- Changing selection updates `st.session_state.structured_cv` with the selected portfolio's cv_object on selectbox change
- If no portfolios exist, redirects to Portfolio page with explanation

### Backward Compatibility
- On first startup after this change, `file_manager.load_portfolio_data()` result is auto-migrated to `output/portfolios/Default.pkl` and set as active
- No user action required; existing workflow is unaffected

---

## Feature 7: Job URL Scraping + Keyword Detection + Suggestions

### `support/job_scraper.py`

**`scrape_job_description(url: str) -> str`**
1. Attempt fetch with `requests` + `BeautifulSoup` — parse `<main>`, `<article>`, or largest `<div>` block
2. If result is empty or too short (<200 chars), fall back to `playwright` headless Chromium
3. Strip navigation, footer, cookie banners, and ads
4. Return cleaned plain-text job description

**`extract_keywords(job_description: str, llm) -> dict`**
- Sends job description to LLM with structured output prompt
- Returns keywords grouped by category:
  ```json
  {
    "Technical Skills": ["Python", "REST API", "Docker"],
    "Soft Skills": ["communication", "cross-functional collaboration"],
    "Tools": ["JIRA", "Splunk", "GitLab CI/CD"],
    "Domain Knowledge": ["microservices", "subscription billing"]
  }
  ```

**`generate_keyword_suggestions(keyword: str, cv_object, llm) -> dict`**
- Finds the most relevant existing bullet point in the cv_object for the given keyword
- Returns:
  ```json
  {
    "keyword": "Kubernetes",
    "original_bullet": "Deployed services using Docker and GitLab CI/CD...",
    "suggested_rewrite": "Deployed and orchestrated services using Docker, Kubernetes, and GitLab CI/CD...",
    "location": "Experience — Plusgrade, bullet 3"
  }
  ```

### `pages/new_submission.py` Changes

**Job Description Input (tabbed):**
- Tab 1: "✍️ Paste Manually" — existing text area, no change
- Tab 2: "🔗 Scrape from URL":
  - URL text input + "🔍 Fetch Job" button
  - On fetch: calls `scrape_job_description()`, auto-fills editable text area below
  - Job URL is stored in session state for pre-filling the `job_url` field when saving

**Keywords Panel (appears after job description is populated):**
- Two-column layout:
  - **Left column — Keywords:**
    - Keywords grouped by category, each as a removable chip (click ❌ to remove)
    - Text input + "➕ Add" button for custom keywords
  - **Right column — Suggestions:**
    - For each selected keyword: shows `location`, `original_bullet`, `suggested_rewrite`
    - "✅ Accept" applies the rewrite to the cv_object in session state
    - "➖ Ignore" dismisses the suggestion without applying
- Suggestions are generated lazily (only for keywords that are currently selected)

**Generate Button:**
- "🚀 Generate Tailored CV" button appears below the keywords panel
- Accepted rewrites are already applied to cv_object before generation begins
- Job URL from scrape tab (if used) is passed through to submission save

---

## Docker Containerization

### Goal
Single-container setup that works for both local development and deployment on any container hosting platform.

### `Dockerfile`
- Base image: `python:3.12-slim` (Debian-based — required for Playwright browser binaries)
- Build steps:
  1. Install system dependencies for Playwright (Chromium and its libs)
  2. Run `playwright install chromium` — adds ~200MB but required for Feature 7 JS fallback
  3. Install Python dependencies via `pip` from `requirements.txt` (exported from Poetry: `poetry export --without-hashes -f requirements.txt`)
  4. Copy app source
  5. Expose port `8501`
- Entrypoint: `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`

### `docker-compose.yml` (local development)
```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./output:/app/output        # persists SQLite DB, portfolios, generated PDFs
      - ./config.ini:/app/config.ini:ro  # API keys (read-only, never baked into image)
    restart: unless-stopped
```

### API Key Handling
- **Local dev:** `config.ini` is volume-mounted — existing flow unchanged, no code changes needed
- **Deployment:** Pass `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY` as environment variables via the hosting platform's settings UI
- `support/settings.py` updated to check `os.environ` before falling back to `config.ini`:
  ```python
  groq_api_key_value = os.environ.get("GROQ_API_KEY", "")
  # ... fall back to config.ini if empty
  ```

### Volume Strategy
- `./output:/app/output` — single mount covers all persistent data:
  - `output/cv_submissions.db` (SQLite)
  - `output/portfolios/` (named portfolio `.pkl` files + index)
  - `output/` generated PDFs (ephemeral — overwritten per generation, acceptable)
- `config.ini` mounted read-only for local dev; omitted entirely on deployment (env vars used instead)

### `.dockerignore`
Excludes: `output/`, `config.ini`, `__pycache__`, `.git`, `**/*.pyc`, `test/`

### Dependency Export
A `requirements.txt` is generated and committed from Poetry for use in the Docker build:
```
poetry export --without-hashes -f requirements.txt -o requirements.txt
```
This file is committed to the repo so the Docker build has no Poetry dependency.

---

## Out of Scope (deferred)

The following features were identified but are not included in this spec:
- Cover letter live preview (explicitly excluded by user)
- Model/API key persistence across sessions (deferred)
- Job application status analytics/charts (deferred)
