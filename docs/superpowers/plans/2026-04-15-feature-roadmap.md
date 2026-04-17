# Feature Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editable submission records, multiple named portfolio support, job URL scraping with keyword suggestions, and Docker containerization to the tailor-your-document Streamlit app.

**Architecture:** Three new support modules (`portfolio_manager.py`, `job_scraper.py`) and one new page (`submission_detail.py`) are added; four existing files are modified. Docker is added via `Dockerfile` + `docker-compose.yml`. All changes are additive — no existing functionality is removed.

**Tech Stack:** Python 3.12, Streamlit 1.45, SQLite (sqlite3), pickle, JSON, LangChain + Groq (`langchain-groq`), BeautifulSoup4, Playwright, xhtml2pdf, requests, pytest, Docker

---

## File Map

### Created
| File | Purpose |
|------|---------|
| `pages/submission_detail.py` | View/edit a single submission's status, notes, job URL; delete submission |
| `support/portfolio_manager.py` | Save/load/list/delete/rename named portfolios; manage active portfolio |
| `support/job_scraper.py` | Scrape job URLs, extract keywords via LLM, generate resume rewrite suggestions |
| `Dockerfile` | Single-container build for Streamlit app |
| `docker-compose.yml` | Local dev orchestration with volume mounts |
| `.dockerignore` | Exclude output/, config.ini, __pycache__ from build context |
| `tests/__init__.py` | Makes tests/ a package for pytest |
| `tests/test_submission_manager.py` | Unit tests for new submission_manager functions |
| `tests/test_portfolio_manager.py` | Unit tests for portfolio_manager |
| `tests/test_job_scraper.py` | Unit tests for job_scraper (mocked LLM + requests) |

### Modified
| File | Change |
|------|--------|
| `support/submission_manager.py` | DB migration for new columns; add `update_submission_metadata()`, `delete_submission()`, `get_submission_metadata()`, `get_all_submissions_with_metadata()` |
| `requirements.txt` | Replace weasyprint with xhtml2pdf; add langchain-groq, beautifulsoup4, playwright, requests |
| `support/settings.py` | Read API keys from env vars before falling back to config.ini |
| `pages/my_submissions.py` | Replace HTML table with Streamlit-native table showing status badge + Edit button per row |
| `pages/portfolio.py` | Add "My Portfolios" panel at top; add portfolio naming after CV processing |
| `pages/new_submission.py` | Portfolio selector dropdown; tabbed JD input (paste/scrape); keywords panel |

---

## Task 1: DB Migration + Submission Manager Enhancements

**Files:**
- Modify: `support/submission_manager.py`
- Create: `tests/__init__.py`
- Create: `tests/test_submission_manager.py`

- [ ] **Step 1: Create the tests directory and write failing tests**

Create `tests/__init__.py` (empty file), then create `tests/test_submission_manager.py`:

```python
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_initialize_db_adds_new_columns(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    # Simulate an old DB without the new columns
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                submission_date TEXT NOT NULL,
                cv_data BLOB NOT NULL,
                cover_letter_data BLOB NOT NULL,
                jd_information_data BLOB NOT NULL
            )
        """)

    from support.submission_manager import initialize_db
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()]

    assert "status" in cols
    assert "notes" in cols
    assert "job_url" in cols


def test_update_and_get_submission_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, update_submission_metadata, get_submission_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TestCorp", "Engineer", "2026-01-01", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    row = get_submission_metadata(1)
    assert row[1] == "TestCorp"
    assert row[4] == "Applied"  # default status via COALESCE

    success = update_submission_metadata(1, "Interviewing", "Called on Monday", "https://example.com/job")
    assert success is True

    row = get_submission_metadata(1)
    assert row[4] == "Interviewing"
    assert row[5] == "Called on Monday"
    assert row[6] == "https://example.com/job"


def test_delete_submission(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, delete_submission, get_submission_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TestCorp", "Engineer", "2026-01-01", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    success = delete_submission(1)
    assert success is True
    assert get_submission_metadata(1) is None


def test_get_all_submissions_with_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, get_all_submissions_with_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Corp A", "Dev", "2026-01-01", b"cv", b"cl", b"jd", "Offer"),
        )
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Corp B", "Manager", "2026-01-02", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    rows = get_all_submissions_with_metadata()
    assert len(rows) == 2
    # Ordered DESC by submission_date — Corp B first
    assert rows[0][1] == "Corp B"
    assert rows[0][4] == "Applied"  # default via COALESCE
    assert rows[1][1] == "Corp A"
    assert rows[1][4] == "Offer"
```

- [ ] **Step 2: Run the tests to confirm they all fail**

Run from the project root (`/Users/rohan.dcosta/Documents/personal/tailor-your-document`):
```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
python -m pytest tests/test_submission_manager.py -v
```
Expected: 4 failures — `ImportError` or `AttributeError` (functions don't exist yet).

- [ ] **Step 3: Install pytest**

```bash
pip install pytest
```

- [ ] **Step 4: Implement the changes to `support/submission_manager.py`**

Replace the `initialize_db()` function and add four new functions. The full updated file (`support/submission_manager.py`):

```python
import sqlite3
import pickle
import tempfile
import os
from datetime import datetime
from support.settings import dest_dir
from support.html_builder import CVBuilder, CoverLetterBuilder
from xhtml2pdf import pisa

DB_PATH = f"{dest_dir}/cv_submissions.db"


def initialize_db():
    """Initialize the database and create tables if they don't exist.
    Also runs safe ALTER TABLE migrations for new columns."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                submission_date TEXT NOT NULL,
                cv_data BLOB NOT NULL,
                cover_letter_data BLOB NOT NULL,
                jd_information_data BLOB NOT NULL
            )
        """)
        # Safe migration: add new columns only if they don't already exist
        for column_def in [
            "status TEXT DEFAULT 'Applied'",
            "notes TEXT",
            "job_url TEXT",
        ]:
            col_name = column_def.split()[0]
            try:
                conn.execute(f"ALTER TABLE submissions ADD COLUMN {column_def}")
            except sqlite3.OperationalError:
                pass  # column already exists — safe to ignore
        conn.commit()


def save_submission(company, position, cv_object, cover_letter_object, jd_information_object):
    """Save a submission with structured objects to the database"""
    initialize_db()

    with sqlite3.connect(DB_PATH) as conn:
        cv_blob = pickle.dumps(cv_object)
        cover_letter_blob = pickle.dumps(cover_letter_object)
        jd_info_blob = pickle.dumps(jd_information_object)

        conn.execute("""
            INSERT INTO submissions (company, position, submission_date,
            cv_data, cover_letter_data, jd_information_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company, position, datetime.now().isoformat(),
              cv_blob, cover_letter_blob, jd_info_blob))
        conn.commit()


def update_submission(submission_id, cv_object, cover_letter_object, jd_information_object):
    """Update an existing submission with new structured objects"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cv_blob = pickle.dumps(cv_object)
            cover_letter_blob = pickle.dumps(cover_letter_object)
            jd_info_blob = pickle.dumps(jd_information_object)

            conn.execute("""
                UPDATE submissions
                SET cv_data = ?, cover_letter_data = ?, jd_information_data = ?
                WHERE id = ?
            """, (cv_blob, cover_letter_blob, jd_info_blob, submission_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating submission: {e}")
        return False


def update_submission_metadata(submission_id, status, notes, job_url):
    """Update the editable metadata fields of a submission."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE submissions SET status = ?, notes = ?, job_url = ? WHERE id = ?",
                (status, notes, job_url, submission_id),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating submission metadata: {e}")
        return False


def delete_submission(submission_id):
    """Permanently delete a submission by ID."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error deleting submission: {e}")
        return False


def get_submission_metadata(submission_id):
    """Return (id, company, position, submission_date, status, notes, job_url) for one row."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date, "
                "COALESCE(status, 'Applied') as status, notes, job_url "
                "FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
    except Exception as e:
        print(f"Error getting submission metadata: {e}")
        return None


def get_all_submissions():
    """Get all submissions (id, company, position, submission_date). Preserved for backward compat."""
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date FROM submissions"
            ).fetchall()
    except Exception as e:
        print(f"Error getting submissions: {e}")
        return []


def get_all_submissions_with_metadata():
    """Return all submissions with all metadata columns, newest first.

    Each row: (id, company, position, submission_date, status, notes, job_url)
    """
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date, "
                "COALESCE(status, 'Applied') as status, notes, job_url "
                "FROM submissions ORDER BY submission_date DESC"
            ).fetchall()
    except Exception as e:
        print(f"Error getting submissions with metadata: {e}")
        return []


def get_submission_objects(submission_id):
    """Get structured objects for a specific submission"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute(
                "SELECT cv_data, cover_letter_data, jd_information_data FROM submissions WHERE id = ?",
                (submission_id,)
            ).fetchone()

            if result:
                cv_object = pickle.loads(result[0])
                cover_letter_object = pickle.loads(result[1])
                jd_info_object = pickle.loads(result[2])
                return cv_object, cover_letter_object, jd_info_object
            return None, None, None
    except Exception as e:
        print(f"Error getting submission objects: {e}")
        return None, None, None


def generate_pdf_from_submission(submission_id, template_id="1"):
    """Generate PDFs from stored structured objects and return file paths"""
    try:
        cv_object, cover_letter_object, jd_info_object = get_submission_objects(submission_id)

        if not all([cv_object, cover_letter_object, jd_info_object]):
            raise ValueError("Could not retrieve submission objects")

        temp_dir = tempfile.mkdtemp(prefix="cv_builder_")

        cv_builder = CVBuilder()
        cv_html = cv_builder.build_html_from_cv(cv_object, template_id, temp_dir)
        cv_pdf_path = f"{temp_dir}/cv_{submission_id}.pdf"
        with open(cv_pdf_path, "wb") as f:
            pisa.CreatePDF(cv_html, dest=f)

        cover_letter_builder = CoverLetterBuilder()
        cl_html = cover_letter_builder.build_html_from_cover_letter(cover_letter_object, template_id, temp_dir)
        cl_pdf_path = f"{temp_dir}/cover_letter_{submission_id}.pdf"
        with open(cl_pdf_path, "wb") as f:
            pisa.CreatePDF(cl_html, dest=f)

        return cv_pdf_path, cl_pdf_path, temp_dir

    except Exception as e:
        print(f"Error generating PDFs: {e}")
        return None, None, None


def cleanup_temp_files(temp_dir):
    """Clean up temporary files and directory"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temp files: {e}")


def has_submissions():
    """Check if there are any submissions in the database"""
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
            return result[0] > 0 if result else False
    except Exception as e:
        print(f"Error checking submissions: {e}")
        return False
```

- [ ] **Step 5: Run tests to confirm they all pass**

```bash
python -m pytest tests/test_submission_manager.py -v
```
Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
git add support/submission_manager.py tests/__init__.py tests/test_submission_manager.py
git commit -m "feat: add DB migration and submission metadata functions with tests"
```

---

## Task 2: Submission Detail Page

**Files:**
- Create: `pages/submission_detail.py`

- [ ] **Step 1: Create `pages/submission_detail.py`**

```python
import streamlit as st
from support.submission_manager import (
    get_submission_metadata,
    update_submission_metadata,
    delete_submission,
)

st.set_page_config(page_title="Submission Detail", layout="wide")

STATUSES = ["Applied", "Interviewing", "Technical Assessment", "Offer", "Rejected", "Withdrawn"]

# --- Load submission ID from URL params ---
raw_id = st.query_params.get("id")

if not raw_id:
    st.error("No submission ID provided.")
    st.page_link("pages/my_submissions.py", label="← Back to Submissions")
    st.stop()

try:
    submission_id = int(raw_id)
except (ValueError, TypeError):
    st.error("Invalid submission ID.")
    st.page_link("pages/my_submissions.py", label="← Back to Submissions")
    st.stop()

row = get_submission_metadata(submission_id)

if not row:
    st.error(f"Submission #{submission_id} not found.")
    st.page_link("pages/my_submissions.py", label="← Back to Submissions")
    st.stop()

_, company, position, submission_date, status, notes, job_url = row

# --- Page title ---
st.title(f"📄 {company} — {position}")
st.caption(f"Submitted: {submission_date.split('T')[0]}")
st.markdown("---")

# --- Read-only fields ---
col1, col2 = st.columns(2)
with col1:
    st.text_input("Company", value=company, disabled=True)
with col2:
    st.text_input("Position", value=position, disabled=True)

st.text_input("Submission Date", value=submission_date.split("T")[0], disabled=True)

# --- Editable fields ---
st.markdown("### Edit Details")

status_index = STATUSES.index(status) if status in STATUSES else 0
new_status = st.selectbox("Status", options=STATUSES, index=status_index)
new_job_url = st.text_input("Job URL", value=job_url or "")
new_notes = st.text_area("Notes", value=notes or "", height=150,
                          placeholder="Add notes about this application...")

st.markdown("---")

# --- Actions ---
col1, col2, col3 = st.columns([1, 1.5, 1])

with col1:
    if st.button("💾 Save Changes", type="primary"):
        if update_submission_metadata(submission_id, new_status, new_notes, new_job_url):
            st.toast("✅ Changes saved!")
        else:
            st.error("❌ Failed to save changes.")

with col2:
    confirm_delete = st.checkbox("Confirm deletion")
    delete_clicked = st.button("🗑️ Delete Submission", disabled=not confirm_delete)
    if delete_clicked:
        if delete_submission(submission_id):
            st.switch_page("pages/my_submissions.py")
        else:
            st.error("❌ Failed to delete submission.")

with col3:
    if st.button("← Back to Submissions"):
        st.switch_page("pages/my_submissions.py")
```

- [ ] **Step 2: Manual smoke test**

Start the app:
```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
streamlit run home.py
```
Navigate to My Submissions. Because the Edit button isn't wired yet (Task 3), manually test by visiting:
`http://localhost:8501/submission_detail?id=1`

Verify:
- Company/Position/Date fields are read-only
- Status, Job URL, Notes are editable
- "Save Changes" shows a toast
- "← Back to Submissions" navigates back

- [ ] **Step 3: Commit**

```bash
git add pages/submission_detail.py
git commit -m "feat: add submission detail page for editing status, notes, and job URL"
```

---

## Task 3: My Submissions — Status Badge + Edit Button

**Files:**
- Modify: `pages/my_submissions.py`

- [ ] **Step 1: Rewrite `pages/my_submissions.py` with status badges and Edit button**

Replace the entire file contents with:

```python
import streamlit as st
from support.submission_manager import (
    get_all_submissions_with_metadata,
    generate_pdf_from_submission,
    cleanup_temp_files,
)
import os

st.set_page_config(page_title="My Submissions", layout="wide")

st.title("📁 My Submissions")

STATUS_BADGE = {
    "Applied": "🔵",
    "Interviewing": "🟡",
    "Technical Assessment": "🟠",
    "Offer": "🟢",
    "Rejected": "🔴",
    "Withdrawn": "⚪",
}

submissions = get_all_submissions_with_metadata()
# Each row: (id, company, position, submission_date, status, notes, job_url)

if not submissions:
    st.info("No applications yet. Once you generate CVs and cover letters, they will appear here.")
    st.stop()

# Search filter
search_query = st.text_input("🔍 Search by company or job title")
if search_query:
    submissions = [
        s for s in submissions
        if search_query.lower() in s[1].lower() or search_query.lower() in s[2].lower()
    ]

# --- Submissions table ---
st.markdown("---")
header = st.columns([2, 2, 1.8, 1.8, 0.8])
header[0].markdown("**Company**")
header[1].markdown("**Position**")
header[2].markdown("**Date**")
header[3].markdown("**Status**")
header[4].markdown("")

for sub in submissions:
    sub_id, company, position, date, status = sub[0], sub[1], sub[2], sub[3], sub[4]
    date_str = date.split("T")[0]
    badge = STATUS_BADGE.get(status, "🔵")

    row = st.columns([2, 2, 1.8, 1.8, 0.8])
    row[0].markdown(company)
    row[1].markdown(position)
    row[2].markdown(date_str)
    row[3].markdown(f"{badge} {status}")
    if row[4].button("✏️", key=f"edit_{sub_id}", help="Edit submission"):
        st.query_params["id"] = str(sub_id)
        st.switch_page("pages/submission_detail.py")

st.markdown("---")

# --- Download section (unchanged logic, updated to handle 7-column tuples) ---
st.subheader("⬇️ Download Documents")
st.info("Select a submission from the dropdown below to download your documents.")

if "download_cv_id" not in st.session_state:
    st.session_state.download_cv_id = None
if "download_cl_id" not in st.session_state:
    st.session_state.download_cl_id = None

submission_options = ["Select a submission..."]
for sub in submissions:
    sub_id, company, position, date = sub[0], sub[1], sub[2], sub[3]
    date_str = date.split("T")[0]
    submission_options.append(f"{company} - {position} ({date_str})")

selected_label = st.selectbox("Choose a submission to download:", options=submission_options,
                               key="submission_selector")

if selected_label != "Select a submission...":
    selected_index = submission_options.index(selected_label) - 1
    selected = submissions[selected_index]
    sub_id, company, position = selected[0], selected[1], selected[2]

    st.success(f"✅ Selected: {company} - {position}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Download CV", key=f"cv_download_{sub_id}"):
            st.session_state.download_cv_id = sub_id
            st.rerun()
    with col2:
        if st.button("📄 Download Cover Letter", key=f"cl_download_{sub_id}"):
            st.session_state.download_cl_id = sub_id
            st.rerun()

if st.session_state.download_cv_id:
    submission_id = st.session_state.download_cv_id
    with st.spinner("Generating CV PDF..."):
        try:
            cv_path, cl_path, temp_dir = generate_pdf_from_submission(submission_id)
            if cv_path and os.path.exists(cv_path):
                sub_details = next((s for s in submissions if s[0] == submission_id), None)
                company = sub_details[1] if sub_details else "CV"
                position = sub_details[2] if sub_details else ""
                with open(cv_path, "rb") as f:
                    st.download_button(
                        label="📥 Download CV PDF",
                        data=f.read(),
                        file_name=f"CV_{company}_{position}.pdf",
                        mime="application/pdf",
                    )
                cleanup_temp_files(temp_dir)
                st.success("✅ CV PDF ready for download!")
            else:
                st.error("❌ Failed to generate CV PDF")
        except Exception as e:
            st.error(f"❌ Error generating CV: {e}")
    st.session_state.download_cv_id = None

if st.session_state.download_cl_id:
    submission_id = st.session_state.download_cl_id
    with st.spinner("Generating Cover Letter PDF..."):
        try:
            cv_path, cl_path, temp_dir = generate_pdf_from_submission(submission_id)
            if cl_path and os.path.exists(cl_path):
                sub_details = next((s for s in submissions if s[0] == submission_id), None)
                company = sub_details[1] if sub_details else "Cover_Letter"
                position = sub_details[2] if sub_details else ""
                with open(cl_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Cover Letter PDF",
                        data=f.read(),
                        file_name=f"Cover_Letter_{company}_{position}.pdf",
                        mime="application/pdf",
                    )
                cleanup_temp_files(temp_dir)
                st.success("✅ Cover Letter PDF ready for download!")
            else:
                st.error("❌ Failed to generate Cover Letter PDF")
        except Exception as e:
            st.error(f"❌ Error generating Cover Letter: {e}")
    st.session_state.download_cl_id = None

# Navigation
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("home.py", label="⬅️ Back to Home", icon="🏠")
with col2:
    st.page_link("pages/portfolio.py", label="Portfolio", icon="📁")
with col3:
    st.page_link("pages/new_submission.py", label="New Submission", icon="📝")
```

- [ ] **Step 2: Manual smoke test**

Start the app and navigate to My Submissions. Verify:
- Table shows Company, Position, Date, Status columns
- Each row has a `🔵 Applied` (or appropriate) status badge
- Clicking ✏️ navigates to `/submission_detail?id=<N>`
- Download section still works

- [ ] **Step 3: Commit**

```bash
git add pages/my_submissions.py
git commit -m "feat: add status badge and edit button to My Submissions table"
```

---

## Task 4: Portfolio Manager Module

**Files:**
- Create: `support/portfolio_manager.py`
- Create: `tests/test_portfolio_manager.py`

- [ ] **Step 1: Write failing tests in `tests/test_portfolio_manager.py`**

```python
import os
import sys
import json
import pickle
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeCVObject:
    def __init__(self, name):
        self.name = name


def _patch_dirs(monkeypatch, tmp_path):
    portfolios_dir = str(tmp_path / "portfolios")
    index_file = os.path.join(portfolios_dir, "portfolios.json")
    monkeypatch.setattr("support.portfolio_manager.PORTFOLIOS_DIR", portfolios_dir)
    monkeypatch.setattr("support.portfolio_manager.INDEX_FILE", index_file)
    return portfolios_dir, index_file


def test_save_and_load_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, load_portfolio

    cv = FakeCVObject("Alice")
    save_portfolio("Work", cv)

    loaded = load_portfolio("Work")
    assert loaded.name == "Alice"


def test_save_creates_index_entry(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    entries = list_portfolios()

    assert len(entries) == 1
    assert entries[0]["name"] == "Work"
    assert entries[0]["is_active"] is True  # first portfolio is auto-active


def test_second_portfolio_not_auto_active(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))

    entries = list_portfolios()
    active = [e for e in entries if e["is_active"]]
    assert len(active) == 1
    assert active[0]["name"] == "Work"


def test_set_and_get_active_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, get_active_portfolio

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Side")

    active = get_active_portfolio()
    assert active.name == "Bob"


def test_delete_active_sets_next_active(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, delete_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Work")
    delete_portfolio("Work")

    entries = list_portfolios()
    assert len(entries) == 1
    assert entries[0]["name"] == "Side"
    assert entries[0]["is_active"] is True


def test_delete_nonactive_leaves_active_unchanged(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, delete_portfolio, get_active_portfolio_name

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Work")
    delete_portfolio("Side")

    assert get_active_portfolio_name() == "Work"


def test_rename_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, rename_portfolio, load_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    rename_portfolio("Work", "Career")

    loaded = load_portfolio("Career")
    assert loaded.name == "Alice"
    names = [e["name"] for e in list_portfolios()]
    assert "Career" in names
    assert "Work" not in names


def test_migrate_legacy_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    legacy_path = str(tmp_path / "structured_cv.pkl")
    monkeypatch.setattr("support.portfolio_manager.dest_dir", str(tmp_path))

    cv = FakeCVObject("Legacy")
    with open(legacy_path, "wb") as f:
        pickle.dump(cv, f)

    from support.portfolio_manager import migrate_legacy_portfolio, list_portfolios, get_active_portfolio_name

    migrate_legacy_portfolio()

    entries = list_portfolios()
    assert len(entries) == 1
    assert entries[0]["name"] == "Default"
    assert get_active_portfolio_name() == "Default"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_portfolio_manager.py -v
```
Expected: 8 failures — `ModuleNotFoundError: No module named 'support.portfolio_manager'`.

- [ ] **Step 3: Create `support/portfolio_manager.py`**

```python
import os
import json
import pickle
from datetime import datetime
from support.settings import dest_dir

PORTFOLIOS_DIR = os.path.join(dest_dir, "portfolios")
INDEX_FILE = os.path.join(PORTFOLIOS_DIR, "portfolios.json")


def _ensure_portfolios_dir():
    os.makedirs(PORTFOLIOS_DIR, exist_ok=True)


def _read_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r") as f:
        return json.load(f)


def _write_index(entries):
    _ensure_portfolios_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def save_portfolio(name: str, cv_object) -> None:
    """Serialise cv_object to output/portfolios/<name>.pkl and update the index."""
    _ensure_portfolios_dir()
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    with open(file_path, "wb") as f:
        pickle.dump(cv_object, f)

    entries = _read_index()
    now = datetime.now().isoformat()

    for entry in entries:
        if entry["name"] == name:
            entry["last_modified"] = now
            _write_index(entries)
            return

    entries.append({
        "name": name,
        "created_date": now,
        "last_modified": now,
        "is_active": len(entries) == 0,  # first portfolio becomes active automatically
    })
    _write_index(entries)


def load_portfolio(name: str):
    """Deserialise and return a cv_object, or None if not found."""
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        return pickle.load(f)


def list_portfolios():
    """Return list of index entries: [{name, created_date, last_modified, is_active}]."""
    return _read_index()


def set_active_portfolio(name: str) -> None:
    """Mark one portfolio as active and clear the flag on all others."""
    entries = _read_index()
    for entry in entries:
        entry["is_active"] = entry["name"] == name
    _write_index(entries)


def get_active_portfolio():
    """Load and return the currently active cv_object, or None if no portfolios exist."""
    entries = _read_index()
    for entry in entries:
        if entry["is_active"]:
            return load_portfolio(entry["name"])
    # Fallback: return the first portfolio if none is explicitly active
    if entries:
        return load_portfolio(entries[0]["name"])
    return None


def get_active_portfolio_name() -> str | None:
    """Return the name of the active portfolio, or None."""
    entries = _read_index()
    for entry in entries:
        if entry["is_active"]:
            return entry["name"]
    if entries:
        return entries[0]["name"]
    return None


def delete_portfolio(name: str) -> None:
    """Remove a portfolio file and its index entry.

    If the deleted portfolio was the active one and others remain,
    the most recently modified becomes the new active.
    """
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    if os.path.exists(file_path):
        os.remove(file_path)

    entries = _read_index()
    was_active = any(e["name"] == name and e["is_active"] for e in entries)
    entries = [e for e in entries if e["name"] != name]

    if was_active and entries:
        entries.sort(key=lambda e: e["last_modified"], reverse=True)
        entries[0]["is_active"] = True

    _write_index(entries)


def rename_portfolio(old_name: str, new_name: str) -> None:
    """Rename the .pkl file and update the index entry."""
    old_path = os.path.join(PORTFOLIOS_DIR, f"{old_name}.pkl")
    new_path = os.path.join(PORTFOLIOS_DIR, f"{new_name}.pkl")
    if os.path.exists(old_path):
        os.rename(old_path, new_path)

    entries = _read_index()
    for entry in entries:
        if entry["name"] == old_name:
            entry["name"] = new_name
            entry["last_modified"] = datetime.now().isoformat()
            break
    _write_index(entries)


def migrate_legacy_portfolio() -> None:
    """One-time migration: copy output/structured_cv.pkl → portfolios/Default.pkl.

    Only runs if no portfolios exist yet and the legacy file is present.
    """
    legacy_path = os.path.join(dest_dir, "structured_cv.pkl")
    if not os.path.exists(legacy_path):
        return
    if list_portfolios():
        return  # already migrated

    with open(legacy_path, "rb") as f:
        cv_object = pickle.load(f)

    save_portfolio("Default", cv_object)
    set_active_portfolio("Default")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_portfolio_manager.py -v
```
Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add support/portfolio_manager.py tests/test_portfolio_manager.py
git commit -m "feat: add portfolio manager module with named portfolio support and tests"
```

---

## Task 5: Portfolio Page — My Portfolios Section

**Files:**
- Modify: `pages/portfolio.py`

- [ ] **Step 1: Add the My Portfolios section at the top of `pages/portfolio.py`**

Insert the following block immediately after the `st.title` and `st.markdown` lines (before the `file_manager = FileManager()` line) and also add the portfolio naming prompt in the upload flow. Replace the full file with:

```python
import os
import streamlit as st
from support.extractor import InformationExtractor
from support.manage_ingestion import process_file
from support.load_models import load_openAI_model, load_gemini_model
from support.file_manager import FileManager
from support.portfolio_manager import (
    migrate_legacy_portfolio,
    list_portfolios,
    load_portfolio,
    save_portfolio,
    set_active_portfolio,
    delete_portfolio,
    get_active_portfolio_name,
)

st.set_page_config(page_title="Portfolio", layout="wide")

# Run one-time migration from legacy structured_cv.pkl if needed
migrate_legacy_portfolio()

st.title("📁 Portfolio Management")
st.markdown("Manage your CV data and uploaded files.")

# Initialize file manager
file_manager = FileManager()

# ──────────────────────────────────────────────
# MY PORTFOLIOS SECTION
# ──────────────────────────────────────────────
st.subheader("🗂️ My Portfolios")

portfolios = list_portfolios()
active_name = get_active_portfolio_name()

if active_name:
    st.info(f"⭐ Active portfolio: **{active_name}**")

if portfolios:
    header = st.columns([3, 2.5, 1, 1, 1])
    header[0].markdown("**Name**")
    header[1].markdown("**Last Modified**")
    header[2].markdown("")
    header[3].markdown("")
    header[4].markdown("")

    for entry in portfolios:
        name = entry["name"]
        last_mod = entry["last_modified"].split("T")[0]
        is_active = entry["is_active"]

        row = st.columns([3, 2.5, 1, 1, 1])
        row[0].markdown(f"{'⭐ ' if is_active else ''}{name}")
        row[1].markdown(last_mod)

        if row[2].button("📂 Load", key=f"load_{name}"):
            cv_obj = load_portfolio(name)
            if cv_obj:
                st.session_state.structured_cv = cv_obj
                st.session_state.final_cv = cv_obj
                st.session_state.exps = cv_obj.experiences or []
                st.session_state.projs = cv_obj.projects or []
                st.session_state.edus = cv_obj.education or []
                st.toast(f"✅ Portfolio '{name}' loaded!")
                st.rerun()

        if row[3].button("⭐", key=f"activate_{name}", help="Set as active",
                         disabled=is_active):
            set_active_portfolio(name)
            st.rerun()

        if row[4].button("🗑️", key=f"delete_{name}", help="Delete portfolio"):
            delete_portfolio(name)
            if name in st.session_state.get("structured_cv_portfolio_name", ""):
                st.session_state.pop("structured_cv", None)
            st.rerun()
else:
    st.info("No portfolios yet. Upload a CV below to create your first portfolio.")

st.markdown("---")

# ──────────────────────────────────────────────
# REST OF PAGE (unchanged logic)
# ──────────────────────────────────────────────

# Check if API keys are configured
if "selected_model" not in st.session_state:
    st.warning("⚠️ Please configure your API keys in 'Manage Settings' first.")
    st.page_link("pages/manage_settings.py", label="Go to Manage Settings", icon="🔑")
    st.stop()

openai_api_key = st.session_state.get("openai_api_key", "")
gemini_api_key = st.session_state.get("gemini_api_key", "")
selected_model = st.session_state.get("selected_model", "openai")

if openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key
if gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = gemini_api_key

# Auto-load active portfolio if session has no CV yet
if not st.session_state.get("structured_cv"):
    active_cv = None
    if active_name:
        active_cv = load_portfolio(active_name)
    if active_cv:
        st.session_state.structured_cv = active_cv
        st.session_state.final_cv = active_cv
        st.session_state.exps = active_cv.experiences or []
        st.session_state.projs = active_cv.projects or []
        st.session_state.edus = active_cv.education or []

# Portfolio Status Section
st.subheader("📊 Portfolio Status")
col1, col2, col3 = st.columns(3)

with col1:
    if "structured_cv" in st.session_state:
        st.success("✅ Portfolio Ready")
        if active_name:
            st.markdown(f"**Active:** {active_name}")
    else:
        st.warning("⚠️ No Portfolio")
        st.markdown("*Upload a CV to get started*")

with col2:
    uploaded_files = file_manager.get_uploaded_files()
    st.info(f"📁 {len(uploaded_files)} Uploaded Files")
    if uploaded_files:
        st.markdown(f"**Latest:** {uploaded_files[0]['original_name']}")

with col3:
    if "structured_cv" in st.session_state:
        exp_count = len(st.session_state.structured_cv.experiences or [])
        proj_count = len(st.session_state.structured_cv.projects or [])
        edu_count = len(st.session_state.structured_cv.education or [])
        st.metric("Total Entries", exp_count + proj_count + edu_count)

st.markdown("---")

# Main Content Tabs
tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "✏️ Edit Portfolio", "📁 File Management"])

with tab1:
    st.subheader("📤 Upload New CV File")

    if "structured_cv" in st.session_state:
        st.info("💡 You already have a portfolio. Uploading a new file will create an additional portfolio.")

    uploaded_file = st.file_uploader(
        "Choose a CV file",
        type=["pdf", "txt", "docx", "md"],
        help="Supported formats: PDF, TXT, DOCX, MD"
    )

    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**File:** {uploaded_file.name}")
            st.markdown(f"**Size:** {uploaded_file.size} bytes")
        with col2:
            st.markdown(f"**Type:** {uploaded_file.type}")

        if st.button("🔄 Process CV", type="primary"):
            with st.spinner("Processing your CV..."):
                try:
                    file_path, safe_filename = file_manager.save_uploaded_file(
                        uploaded_file, uploaded_file.name
                    )
                    markdown_cv = process_file(uploaded_file)

                    if markdown_cv:
                        if "information_extractor" not in st.session_state:
                            st.session_state.information_extractor = InformationExtractor()

                        if selected_model == "gemini" and gemini_api_key:
                            st.session_state.information_extractor.MODEL = load_gemini_model()
                        elif selected_model == "openai" and openai_api_key:
                            st.session_state.information_extractor.MODEL = load_openAI_model()
                        else:
                            st.error("❌ No valid API key found for the selected model")
                            st.stop()

                        structured_cv = st.session_state.information_extractor.extract_data(
                            markdown_cv=markdown_cv, is_new_cv=True
                        )

                        st.session_state.structured_cv = structured_cv
                        st.session_state.final_cv = structured_cv
                        st.session_state.exps = structured_cv.experiences or []
                        st.session_state.projs = structured_cv.projects or []
                        st.session_state.edus = structured_cv.education or []
                        st.session_state.pending_save_cv = structured_cv
                        st.success("✅ CV processed! Choose a name to save it as a portfolio.")
                        st.rerun()
                    else:
                        st.error("❌ Failed to process file. Please check the file format.")

                except Exception as e:
                    st.error(f"❌ Error processing CV: {str(e)}")

    # Portfolio naming prompt (shown after processing)
    if "pending_save_cv" in st.session_state:
        existing_names = [e["name"] for e in list_portfolios()]
        default_name = f"Portfolio {len(existing_names) + 1}"
        portfolio_name = st.text_input("Portfolio name", value=default_name, key="new_portfolio_name")
        col_save, col_skip = st.columns(2)
        with col_save:
            if st.button("💾 Save Portfolio", type="primary"):
                if portfolio_name.strip():
                    save_portfolio(portfolio_name.strip(), st.session_state.pending_save_cv)
                    # Also maintain backward-compat legacy file
                    file_manager.save_portfolio_data(st.session_state.pending_save_cv)
                    del st.session_state.pending_save_cv
                    st.toast(f"✅ Saved as '{portfolio_name}'!")
                    st.rerun()
                else:
                    st.error("Please enter a portfolio name.")
        with col_skip:
            if st.button("Skip (don't save to portfolios)"):
                del st.session_state.pending_save_cv
                st.rerun()

with tab2:
    if "structured_cv" in st.session_state:
        st.subheader("✏️ Edit Your Portfolio")

        if "final_cv" not in st.session_state:
            st.session_state.final_cv = st.session_state.structured_cv

        if "exps" not in st.session_state:
            st.session_state.exps = st.session_state.final_cv.experiences or []
        if "projs" not in st.session_state:
            st.session_state.projs = st.session_state.final_cv.projects or []
        if "edus" not in st.session_state:
            st.session_state.edus = st.session_state.final_cv.education or []

        def add_entry(entry_type):
            if entry_type == "exp":
                if st.session_state.exps:
                    st.session_state.exps.append(type(st.session_state.exps[0])())
                else:
                    from support.supportClasses import Experience
                    st.session_state.exps.append(Experience())
            elif entry_type == "proj":
                if st.session_state.projs:
                    st.session_state.projs.append(type(st.session_state.projs[0])())
                else:
                    from support.supportClasses import Experience
                    st.session_state.projs.append(Experience())
            elif entry_type == "edu":
                if st.session_state.edus:
                    st.session_state.edus.append(type(st.session_state.edus[0])())
                else:
                    from support.supportClasses import EducationExperience
                    st.session_state.edus.append(EducationExperience())

        def delete_entry(entry_type, idx):
            if entry_type == "exp":
                st.session_state.exps.pop(idx)
            elif entry_type == "proj":
                st.session_state.projs.pop(idx)
            elif entry_type == "edu":
                st.session_state.edus.pop(idx)

        col1, col2 = st.columns([0.6, 0.4])

        with col1:
            with st.expander("👤 Personal Information", expanded=True):
                st.session_state.final_cv.personality.name = st.text_input(
                    "Name", value=st.session_state.final_cv.personality.name or "", key="portfolio_name")
                st.session_state.final_cv.personality.surname = st.text_input(
                    "Surname", value=st.session_state.final_cv.personality.surname or "", key="portfolio_surname")
                st.session_state.final_cv.personality.job_title = st.text_input(
                    "Current Job Title", value=st.session_state.final_cv.personality.job_title or "", key="portfolio_job_title")
                st.session_state.final_cv.personality.e_mail = st.text_input(
                    "Email", value=st.session_state.final_cv.personality.e_mail or "", key="portfolio_email")
                st.session_state.final_cv.personality.telephone = st.text_input(
                    "Telephone", value=st.session_state.final_cv.personality.telephone or "", key="portfolio_phone")
                st.session_state.final_cv.personality.linkedin_link = st.text_input(
                    "LinkedIn", value=st.session_state.final_cv.personality.linkedin_link or "", key="portfolio_linkedin")
                st.session_state.final_cv.personality.address = st.text_input(
                    "Address", value=st.session_state.final_cv.personality.address or "", key="portfolio_address")

            with st.expander("📝 Summary", expanded=True):
                st.session_state.final_cv.summary = st.text_area(
                    "Professional Summary", value=st.session_state.final_cv.summary or "",
                    height=100, key="portfolio_summary")

            with st.expander("🧩 Skills", expanded=True):
                hard_skills_input = st.text_area(
                    "Hard Skills (comma-separated)",
                    value=", ".join(st.session_state.final_cv.hard_skills or []),
                    key="portfolio_hard_skills")
                soft_skills_input = st.text_area(
                    "Soft Skills (comma-separated)",
                    value=", ".join(st.session_state.final_cv.soft_skills or []),
                    key="portfolio_soft_skills")

        with col2:
            with st.expander("💼 Work Experience", expanded=True):
                for i, exp in enumerate(st.session_state.exps):
                    with st.container():
                        st.markdown(f"**Experience #{i+1}**")
                        exp.title = st.text_input("Title", exp.title or "", key=f"portfolio_exp_title_{i}")
                        exp.company = st.text_input("Company", exp.company or "", key=f"portfolio_exp_company_{i}")
                        exp.start_date = st.text_input("Start Date", exp.start_date or "", key=f"portfolio_exp_start_{i}")
                        exp.end_date = st.text_input("End Date", exp.end_date or "", key=f"portfolio_exp_end_{i}")
                        exp.description = st.text_area("Description", exp.description or "", key=f"portfolio_exp_desc_{i}", height=80)
                        st.button("❌ Remove", key=f"portfolio_del_exp_{i}", on_click=delete_entry, args=("exp", i))
                        st.markdown("---")
                st.button("➕ Add Experience", on_click=add_entry, args=("exp",), key="portfolio_add_exp_btn")

            with st.expander("🛠️ Projects", expanded=True):
                for i, proj in enumerate(st.session_state.projs):
                    with st.container():
                        st.markdown(f"**Project #{i+1}**")
                        proj.title = st.text_input("Title", proj.title or "", key=f"portfolio_proj_title_{i}")
                        proj.company = st.text_input("Company/Organization", proj.company or "", key=f"portfolio_proj_company_{i}")
                        proj.start_date = st.text_input("Start Date", proj.start_date or "", key=f"portfolio_proj_start_{i}")
                        proj.end_date = st.text_input("End Date", proj.end_date or "", key=f"portfolio_proj_end_{i}")
                        proj.description = st.text_area("Description", proj.description or "", key=f"portfolio_proj_desc_{i}", height=80)
                        st.button("❌ Remove", key=f"portfolio_del_proj_{i}", on_click=delete_entry, args=("proj", i))
                        st.markdown("---")
                st.button("➕ Add Project", on_click=add_entry, args=("proj",))

            with st.expander("🎓 Education", expanded=True):
                for i, edu in enumerate(st.session_state.edus):
                    with st.container():
                        st.markdown(f"**Education #{i+1}**")
                        edu.title = st.text_input("Degree/Title", edu.title or "", key=f"portfolio_edu_title_{i}")
                        edu.school_name = st.text_input("School/University", edu.school_name or "", key=f"portfolio_edu_school_{i}")
                        edu.start_date = st.text_input("Start Date", edu.start_date or "", key=f"portfolio_edu_start_{i}")
                        edu.end_date = st.text_input("End Date", edu.end_date or "", key=f"portfolio_edu_end_{i}")
                        edu.description = st.text_area("Description", edu.description or "", key=f"portfolio_edu_desc_{i}", height=80)
                        st.button("❌ Remove", key=f"portfolio_del_edu_{i}", on_click=delete_entry, args=("edu", i))
                        st.markdown("---")
                st.button("➕ Add Education", on_click=add_entry, args=("edu",))

        if st.button("💾 Save Portfolio", type="primary"):
            st.session_state.final_cv.hard_skills = [s.strip() for s in hard_skills_input.split(",") if s.strip()]
            st.session_state.final_cv.soft_skills = [s.strip() for s in soft_skills_input.split(",") if s.strip()]
            st.session_state.final_cv.experiences = st.session_state.exps
            st.session_state.final_cv.projects = st.session_state.projs
            st.session_state.final_cv.education = st.session_state.edus

            file_manager.save_portfolio_data(st.session_state.final_cv)
            if active_name:
                save_portfolio(active_name, st.session_state.final_cv)

            st.success("✅ Portfolio saved successfully!")
            st.session_state.structured_cv = st.session_state.final_cv
    else:
        st.info("📁 No portfolio found. Please upload a CV file first.")

with tab3:
    st.subheader("📁 File Management")

    st.markdown("**📤 Uploaded CV Files**")
    uploaded_files_list = file_manager.get_uploaded_files()

    if uploaded_files_list:
        for file_info in uploaded_files_list:
            col1, col2, col3, col4 = st.columns([0.4, 0.2, 0.2, 0.2])
            with col1:
                st.markdown(f"**{file_info['original_name']}**")
                st.caption(f"Uploaded: {file_info['modified'].strftime('%Y-%m-%d %H:%M')}")
            with col2:
                st.markdown(f"{file_info['size']:,} bytes")
            with col3:
                if st.button("🗑️", key=f"del_{file_info['filename']}", help="Delete file"):
                    if file_manager.delete_uploaded_file(file_info['filename']):
                        st.success("File deleted!")
                        st.rerun()
            with col4:
                if st.button("📥", key=f"download_{file_info['filename']}", help="Download file"):
                    with open(file_info['path'], 'rb') as f:
                        st.download_button(
                            label="Download",
                            data=f.read(),
                            file_name=file_info['original_name'],
                            mime="application/octet-stream",
                        )
            st.markdown("---")
    else:
        st.info("No uploaded files yet.")

# Navigation
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("home.py", label="Back to Home", icon="🏠")
with col2:
    st.page_link("pages/manage_settings.py", label="Manage Settings", icon="⚙️")
with col3:
    st.page_link("pages/new_submission.py", label="New Submission", icon="📝")
```

- [ ] **Step 2: Manual smoke test**

Start the app. Navigate to Portfolio. Verify:
- "My Portfolios" section appears at the top
- If `output/structured_cv.pkl` exists, it auto-migrates to `output/portfolios/Default.pkl` and shows in the list
- "📂 Load", "⭐ Set Active", "🗑️ Delete" buttons are clickable per row
- After uploading + processing a CV, a name input and "Save Portfolio" button appear
- Active portfolio name shown in info banner

- [ ] **Step 3: Commit**

```bash
git add pages/portfolio.py support/portfolio_manager.py
git commit -m "feat: add My Portfolios panel to Portfolio page with load/activate/delete"
```

---

## Task 6: New Submission — Portfolio Selector

**Files:**
- Modify: `pages/new_submission.py`

- [ ] **Step 1: Update the portfolio loading block at the top of `pages/new_submission.py`**

Replace the existing "Check if portfolio exists" block (lines 26–35 in the original) with the following. Also add the import at the top and the portfolio selector widget before the job description input. Full updated file:

```python
import os
import copy
import pickle
import time
import streamlit as st
from support.extractor import InformationExtractor
from support.load_models import load_openAI_model, load_gemini_model
from support.html_builder import render_editable_cv, render_editable_cover_letter
from support.file_manager import FileManager
from support.settings import TESTING
from support.portfolio_manager import (
    list_portfolios,
    load_portfolio,
    get_active_portfolio_name,
    migrate_legacy_portfolio,
)

st.set_page_config(page_title="New Submission", layout="wide")

st.title("📝 New Job Submission")
st.markdown("Create tailored CV and cover letter for a specific job application.")

file_manager = FileManager()

# Ensure legacy portfolio is migrated on first run
migrate_legacy_portfolio()

if "current_submission_id" not in st.session_state:
    st.session_state.current_submission_id = None
if "is_new_submission" not in st.session_state:
    st.session_state.is_new_submission = True

# ── Portfolio selector ──────────────────────────────────────────────────────
portfolios = list_portfolios()

if not portfolios:
    st.warning("⚠️ No portfolios found. Please create one in the Portfolio page first.")
    st.page_link("pages/portfolio.py", label="Go to Portfolio", icon="📁")
    st.stop()

portfolio_names = [e["name"] for e in portfolios]
active_name = get_active_portfolio_name() or portfolio_names[0]
default_index = portfolio_names.index(active_name) if active_name in portfolio_names else 0

selected_portfolio = st.selectbox(
    "🗂️ Generating with portfolio:",
    options=portfolio_names,
    index=default_index,
    key="selected_portfolio_name",
)

# Load the selected portfolio into session state whenever the selection changes
if st.session_state.get("_last_selected_portfolio") != selected_portfolio:
    cv_obj = load_portfolio(selected_portfolio)
    if cv_obj:
        st.session_state.structured_cv = cv_obj
        st.session_state._last_selected_portfolio = selected_portfolio

# Fallback: try loading from file_manager if still missing
if "structured_cv" not in st.session_state:
    fallback = file_manager.load_portfolio_data()
    if fallback:
        st.session_state.structured_cv = fallback
    else:
        st.warning("⚠️ Could not load portfolio data. Please visit the Portfolio page.")
        st.page_link("pages/portfolio.py", label="Go to Portfolio", icon="📁")
        st.stop()

# ── API key check ────────────────────────────────────────────────────────────
if "selected_model" not in st.session_state:
    st.warning("⚠️ Please configure your API keys in 'Manage Settings' first.")
    st.page_link("pages/manage_settings.py", label="Go to Manage Settings", icon="🔑")
    st.stop()

openai_api_key = st.session_state.get("openai_api_key", "")
gemini_api_key = st.session_state.get("gemini_api_key", "")
selected_model = st.session_state.get("selected_model", "openai")

if openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key
if gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = gemini_api_key

# ── Job Description Input ────────────────────────────────────────────────────
st.subheader("📋 Job Description")
job_description = st.text_area(
    "Paste the job description here",
    height=200,
    placeholder="Paste the complete job description including requirements, responsibilities, and company information...",
)

# ── Generate Button ──────────────────────────────────────────────────────────
if st.button("🪄 Generate Tailored Documents", type="primary"):
    if not job_description:
        st.error("Please provide a job description.")
    else:
        st.session_state.is_new_submission = True
        st.session_state.current_submission_id = None

        with st.spinner("Generating your tailored CV and cover letter..."):
            try:
                if "information_extractor" not in st.session_state:
                    st.session_state.information_extractor = InformationExtractor()

                if selected_model == "gemini" and gemini_api_key:
                    st.session_state.information_extractor.MODEL = load_gemini_model()
                elif selected_model == "openai" and openai_api_key:
                    st.session_state.information_extractor.MODEL = load_openAI_model()
                else:
                    st.error("❌ No valid API key found for the selected model")
                    st.stop()

                st.session_state.information_extractor.structured_cv = st.session_state.structured_cv

                st.info(f"🔍 Debug Info: Using {selected_model.upper()} model")
                st.info(f"🔍 Debug Info: Structured CV loaded: {st.session_state.structured_cv is not None}")

                if not TESTING:
                    st.info("🔄 Generating new CV...")
                    new_cv = st.session_state.information_extractor.create_new_cv(
                        structured_curriculum=st.session_state.structured_cv,
                        job_description=job_description,
                    )
                    st.info("🔄 Generating cover letter...")
                    cover_letter = st.session_state.information_extractor.create_new_cover_letter(
                        structured_curriculum=st.session_state.structured_cv,
                        job_description=job_description,
                    )
                else:
                    with open(st.session_state.information_extractor.new_cv_path, "rb") as file:
                        new_cv = pickle.load(file)
                    with open(st.session_state.information_extractor.cover_letter_path, "rb") as file:
                        cover_letter = pickle.load(file)
                    with open(st.session_state.information_extractor.jd_information_path, "rb") as file:
                        jd_information = pickle.load(file)
                    st.session_state.information_extractor.new_cv = new_cv
                    st.session_state.information_extractor.cover_letter = cover_letter
                    st.session_state.information_extractor.jd_information = jd_information

                st.info("🔄 Building final CV...")
                generated_html = st.session_state.information_extractor.build_final_cv()
                st.info("🔄 Building final cover letter...")
                generated_html_cover_letter = st.session_state.information_extractor.build_final_cover_letter()

                st.session_state.final_cv_content = st.session_state.information_extractor.final_cv
                st.session_state.generated_html = generated_html
                st.session_state.final_cover_letter_content = st.session_state.information_extractor.final_cover_letter
                st.session_state.generated_html_cover_letter = generated_html_cover_letter

                st.success("✅ Tailored documents generated successfully!")

            except Exception as e:
                st.error(f"❌ Failed to process the CV with the model: {e}")
                import traceback
                st.error("📋 Full error traceback:")
                st.code(traceback.format_exc())

# ── Document Editor and Preview ──────────────────────────────────────────────
if "generated_html" in st.session_state and "generated_html_cover_letter" in st.session_state:
    st.subheader("✏️ Edit & Preview Documents")

    tab1, tab2 = st.tabs(["📄 CV Editor & Preview", "✉️ Cover Letter Editor & Preview"])

    with tab1:
        col1, col2 = st.columns([0.4, 0.6], gap="large")
        with col1:
            st.markdown("**📝 Edit Your CV**")
            render_editable_cv(st.session_state.final_cv_content)
        with col2:
            st.markdown("**👀 CV Preview**")
            st.components.v1.html(st.session_state.generated_html, height=1300, scrolling=True)

    with tab2:
        col1, col2 = st.columns([0.4, 0.6], gap="large")
        with col1:
            st.markdown("**📝 Edit Your Cover Letter**")
            render_editable_cover_letter(st.session_state.final_cover_letter_content)
        with col2:
            st.markdown("**👀 Cover Letter Preview**")
            st.components.v1.html(st.session_state.generated_html_cover_letter, height=1300, scrolling=True)

    st.subheader("💾 Save & Download")

    submission_exists = (
        "information_extractor" in st.session_state
        and hasattr(st.session_state.information_extractor, "jd_information")
        and st.session_state.information_extractor.jd_information
    )

    if submission_exists:
        st.success("✅ Submission is ready for database")
        jd_info = st.session_state.information_extractor.jd_information
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Company:** {jd_info.company_name}")
            st.info(f"**Position:** {jd_info.job_title}")
        with col2:
            st.info("**CV Generated:** ✅")
            st.info("**Cover Letter Generated:** ✅")
    else:
        st.warning("⚠️ Documents need to be generated before saving")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Save to Database", type="primary"):
            try:
                if not st.session_state.information_extractor.jd_information:
                    st.error("❌ Job description information is missing. Please regenerate the documents.")
                elif not st.session_state.information_extractor.jd_information.company_name:
                    st.error("❌ Company name is missing.")
                elif not st.session_state.information_extractor.jd_information.job_title:
                    st.error("❌ Job title is missing.")
                else:
                    if st.session_state.is_new_submission:
                        st.session_state.information_extractor.create_pdf()
                        st.session_state.is_new_submission = False
                        st.session_state.current_submission_id = "new"
                        st.success("✅ New submission created in database!")
                    else:
                        from support.submission_manager import update_submission, get_all_submissions
                        all_submissions = get_all_submissions()
                        if all_submissions:
                            latest_submission_id = all_submissions[-1][0]
                            update_submission(
                                latest_submission_id,
                                st.session_state.information_extractor.final_cv,
                                st.session_state.information_extractor.final_cover_letter,
                                st.session_state.information_extractor.jd_information,
                            )
                            st.session_state.current_submission_id = latest_submission_id
                            st.success("✅ Existing submission updated in database!")
                        else:
                            st.error("❌ No existing submission found to update")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving to database: {e}")
                if "NOT NULL constraint failed" in str(e):
                    st.error("💡 Job description information may be missing.")

    with col2:
        if submission_exists:
            if st.button("⬇️ Download PDFs"):
                st.session_state.show_downloads = True
                st.session_state.download_generated = False
                st.rerun()
        else:
            st.button("⬇️ Download PDFs", disabled=True, help="Generate documents first")

# ── PDF Download handling (unchanged) ────────────────────────────────────────
if "show_downloads" not in st.session_state:
    st.session_state.show_downloads = False
if "download_generated" not in st.session_state:
    st.session_state.download_generated = False

if st.session_state.show_downloads and not st.session_state.download_generated:
    st.subheader("⬇️ Download Documents")

    if st.button("🔄 Generate PDFs for Download"):
        try:
            submission_id_to_use = None
            if st.session_state.current_submission_id and st.session_state.current_submission_id != "new":
                submission_id_to_use = st.session_state.current_submission_id
            else:
                from support.submission_manager import get_all_submissions
                all_submissions = get_all_submissions()
                if all_submissions:
                    submission_id_to_use = all_submissions[-1][0]
                    st.session_state.current_submission_id = submission_id_to_use

            if submission_id_to_use:
                from support.submission_manager import generate_pdf_from_submission, cleanup_temp_files
                cv_path, cl_path, temp_dir = generate_pdf_from_submission(submission_id_to_use)
                if cv_path and cl_path and os.path.exists(cv_path) and os.path.exists(cl_path):
                    st.session_state.cv_path = cv_path
                    st.session_state.cl_path = cl_path
                    st.session_state.temp_dir = temp_dir
                    st.session_state.download_generated = True
                    st.rerun()
                else:
                    st.error("❌ Failed to generate PDFs")
            else:
                st.error("❌ No submission found to generate PDFs from")
        except Exception as e:
            st.error(f"❌ Error generating PDFs: {e}")

if st.session_state.download_generated and "cv_path" in st.session_state:
    st.success("✅ PDFs generated and ready for download!")
    col1, col2 = st.columns(2)
    with col1:
        with open(st.session_state.cv_path, "rb") as f:
            st.download_button(label="📥 Download CV PDF", data=f.read(),
                               file_name="CV.pdf", mime="application/pdf")
    with col2:
        with open(st.session_state.cl_path, "rb") as f:
            st.download_button(label="📥 Download Cover Letter PDF", data=f.read(),
                               file_name="Cover_Letter.pdf", mime="application/pdf")

    if st.button("🧹 Clean Up Temporary Files"):
        from support.submission_manager import cleanup_temp_files
        cleanup_temp_files(st.session_state.temp_dir)
        st.session_state.show_downloads = False
        st.session_state.download_generated = False
        for key in ["cv_path", "cl_path", "temp_dir", "download_timestamp"]:
            st.session_state.pop(key, None)
        st.success("✅ Temporary files cleaned up!")
        st.rerun()

    if "download_timestamp" not in st.session_state:
        st.session_state.download_timestamp = time.time()
    if time.time() - st.session_state.download_timestamp > 300:
        from support.submission_manager import cleanup_temp_files
        cleanup_temp_files(st.session_state.temp_dir)
        st.session_state.show_downloads = False
        st.session_state.download_generated = False
        for key in ["cv_path", "cl_path", "temp_dir", "download_timestamp"]:
            st.session_state.pop(key, None)
        st.info("⏰ Temporary files automatically cleaned up.")
        st.rerun()

# Navigation
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("home.py", label="Back to Home", icon="🏠")
with col2:
    st.page_link("pages/portfolio.py", label="Portfolio", icon="📁")
with col3:
    st.page_link("pages/my_submissions.py", label="My Submissions", icon="📁")
```

- [ ] **Step 2: Manual smoke test**

Start the app and go to New Submission. Verify:
- Portfolio selector dropdown shows portfolio names
- Selecting a different portfolio reloads `structured_cv` in session state
- If no portfolios exist, the page redirects with an explanation

- [ ] **Step 3: Commit**

```bash
git add pages/new_submission.py
git commit -m "feat: add portfolio selector to New Submission page"
```

---

## Task 7: Add Dependencies + Job Scraper Module

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `support/job_scraper.py`
- Create: `tests/test_job_scraper.py`

- [ ] **Step 1: Update `pyproject.toml` to add new dependencies**

Replace the `dependencies` list in `pyproject.toml`:

```toml
[project]
name = "tailor-your-cv"
version = "0.2.0"
description = "An AI tool that helps users craft customized Curriculum Vitae, based on job descriptions, highlighting relevant experiences using LLMs."
readme = "README.md"
requires-python = ">=3.12,<4.0"
dependencies = [
    "langchain-google-genai==2.1.8",
    "langchain-openai==0.3.18",
    "langchain-groq>=0.3.0",
    "markitdown[all]==0.1.2",
    "pydantic==2.11.5",
    "streamlit==1.45.1",
    "xhtml2pdf>=0.2.16",
    "beautifulsoup4>=4.12.0",
    "playwright>=1.44.0",
    "requests>=2.31.0",
    "pytest>=8.0.0",
]
```

- [ ] **Step 2: Update `requirements.txt` to match**

```
langchain-google-genai==2.1.8
langchain-openai==0.3.18
langchain-groq>=0.3.0
markitdown[all]==0.1.2
pydantic==2.11.5
streamlit==1.45.1
xhtml2pdf>=0.2.16
beautifulsoup4>=4.12.0
playwright>=1.44.0
requests>=2.31.0
```

- [ ] **Step 3: Install new dependencies and Playwright browser**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
pip install beautifulsoup4 playwright requests xhtml2pdf langchain-groq pytest
playwright install chromium
```

Expected: All packages install successfully. `playwright install chromium` downloads ~200MB Chromium binary.

- [ ] **Step 4: Write failing tests in `tests/test_job_scraper.py`**

```python
import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeExperience:
    def __init__(self, title, company, description):
        self.title = title
        self.company = company
        self.description = description


class FakeCVObject:
    def __init__(self):
        self.experiences = [
            FakeExperience(
                "Senior Engineer",
                "Acme Corp",
                "- Built REST APIs using Python and Flask\n- Deployed services using Docker and GitLab CI/CD",
            )
        ]
        self.projects = [
            FakeExperience(
                "Open Source Contrib",
                None,
                "- Contributed Kubernetes operator for automated scaling",
            )
        ]


def test_extract_keywords_parses_llm_response():
    from support.job_scraper import extract_keywords

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = json.dumps({
        "Technical Skills": ["Python", "Docker"],
        "Soft Skills": ["communication"],
        "Tools": ["JIRA"],
        "Domain Knowledge": ["microservices"],
    })
    fake_llm.invoke.return_value = fake_response

    result = extract_keywords("We need Python and Docker skills.", fake_llm)

    assert "Technical Skills" in result
    assert "Python" in result["Technical Skills"]
    assert "Docker" in result["Technical Skills"]
    assert "communication" in result["Soft Skills"]


def test_extract_keywords_returns_empty_on_bad_json():
    from support.job_scraper import extract_keywords

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = "not valid json at all"
    fake_llm.invoke.return_value = fake_response

    result = extract_keywords("some job", fake_llm)
    assert result == {}


def test_generate_keyword_suggestions_returns_suggestion():
    from support.job_scraper import generate_keyword_suggestions

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = json.dumps({
        "keyword": "Kubernetes",
        "original_bullet": "Deployed services using Docker and GitLab CI/CD",
        "suggested_rewrite": "Deployed and orchestrated services using Docker, Kubernetes, and GitLab CI/CD",
        "location": "Experience — Acme Corp, Senior Engineer",
        "source_type": "experience",
        "source_index": 0,
    })
    fake_llm.invoke.return_value = fake_response

    cv = FakeCVObject()
    result = generate_keyword_suggestions("Kubernetes", cv, fake_llm)

    assert result["keyword"] == "Kubernetes"
    assert "Kubernetes" in result["suggested_rewrite"]
    assert result["source_type"] == "experience"
    assert result["source_index"] == 0


def test_generate_keyword_suggestions_returns_none_for_empty_cv():
    from support.job_scraper import generate_keyword_suggestions

    fake_llm = MagicMock()

    class EmptyCVObject:
        experiences = []
        projects = []

    result = generate_keyword_suggestions("Kubernetes", EmptyCVObject(), fake_llm)
    assert result is None


@patch("support.job_scraper.requests.get")
def test_scrape_job_description_returns_text(mock_get):
    from support.job_scraper import scrape_job_description

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <html><body>
    <main>
        <h1>Software Engineer</h1>
        <p>We are looking for a Python developer with 3+ years of experience building REST APIs.
        You will work with Docker, Kubernetes, and CI/CD pipelines to deploy microservices at scale.
        Strong communication skills required. Experience with JIRA and GitLab preferred.</p>
    </main>
    </body></html>
    """
    mock_get.return_value = mock_response

    result = scrape_job_description("https://example.com/job/123")

    assert "Python" in result
    assert "REST APIs" in result
    assert len(result) >= 200
```

- [ ] **Step 5: Run tests to confirm they fail**

```bash
python -m pytest tests/test_job_scraper.py -v
```
Expected: Failures — `ModuleNotFoundError: No module named 'support.job_scraper'`.

- [ ] **Step 6: Create `support/job_scraper.py`**

```python
import json
import requests
from bs4 import BeautifulSoup


def scrape_job_description(url: str) -> str:
    """Fetch and clean job description text from a URL.

    Attempt 1: requests + BeautifulSoup.
    Attempt 2 (fallback): Playwright headless Chromium for JS-rendered pages.
    Returns cleaned plain-text job description.
    """
    text = _scrape_with_requests(url)
    if len(text) >= 200:
        return text
    return _scrape_with_playwright(url)


def _scrape_with_requests(url: str) -> str:
    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JobScraper/1.0)"
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise elements
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        # Prefer semantic content containers
        for selector in ["main", "article", '[role="main"]']:
            container = soup.select_one(selector)
            if container:
                return _clean_text(container.get_text(separator="\n"))

        # Fallback: largest div block
        divs = soup.find_all("div")
        if divs:
            largest = max(divs, key=lambda d: len(d.get_text()))
            return _clean_text(largest.get_text(separator="\n"))

        return _clean_text(soup.get_text(separator="\n"))
    except Exception:
        return ""


def _scrape_with_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        for selector in ["main", "article", '[role="main"]']:
            container = soup.select_one(selector)
            if container:
                return _clean_text(container.get_text(separator="\n"))

        return _clean_text(soup.get_text(separator="\n"))
    except Exception:
        return ""


def _clean_text(text: str) -> str:
    """Collapse blank lines and strip leading/trailing whitespace."""
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return "\n".join(cleaned).strip()


def extract_keywords(job_description: str, llm) -> dict:
    """Send job description to LLM and return keywords grouped by category.

    Returns:
        {
            "Technical Skills": ["Python", "Docker", ...],
            "Soft Skills": ["communication", ...],
            "Tools": ["JIRA", ...],
            "Domain Knowledge": ["microservices", ...]
        }
    Returns {} on parse failure.
    """
    prompt = f"""Extract keywords from the following job description and group them by category.
Return ONLY a JSON object with these exact keys:
- "Technical Skills": list of programming languages, frameworks, platforms
- "Soft Skills": list of interpersonal/non-technical skills
- "Tools": list of specific tools, software, platforms (JIRA, Splunk, etc.)
- "Domain Knowledge": list of domain/industry concepts

Return ONLY the JSON object, no explanation.

Job Description:
{job_description}"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, Exception):
        return {}


def generate_keyword_suggestions(keyword: str, cv_object, llm) -> dict | None:
    """Find the most relevant existing bullet point for a keyword and suggest a rewrite.

    Returns:
        {
            "keyword": str,
            "original_bullet": str,
            "suggested_rewrite": str,
            "location": str,
            "source_type": "experience" | "project",
            "source_index": int
        }
    Returns None if the cv_object has no bullets to work with.
    """
    # Collect all bullets with their source metadata
    all_bullets = []
    for i, exp in enumerate(cv_object.experiences or []):
        if exp.description:
            for line in exp.description.splitlines():
                bullet = line.strip().lstrip("-•*").strip()
                if bullet:
                    all_bullets.append({
                        "bullet": bullet,
                        "location": f"Experience — {exp.company or exp.title}",
                        "source_type": "experience",
                        "source_index": i,
                    })
    for i, proj in enumerate(cv_object.projects or []):
        if proj.description:
            for line in proj.description.splitlines():
                bullet = line.strip().lstrip("-•*").strip()
                if bullet:
                    all_bullets.append({
                        "bullet": bullet,
                        "location": f"Project — {proj.title or proj.company}",
                        "source_type": "project",
                        "source_index": i,
                    })

    if not all_bullets:
        return None

    bullets_text = "\n".join(
        f"[{i}] ({b['location']}) {b['bullet']}"
        for i, b in enumerate(all_bullets)
    )

    prompt = f"""Given the keyword "{keyword}", find the most relevant bullet point from this CV and suggest a rewrite that naturally incorporates the keyword.

Bullet points (indexed):
{bullets_text}

Return ONLY a JSON object with these keys:
- "keyword": the keyword
- "original_bullet": the exact original bullet text (copy exactly from above)
- "suggested_rewrite": improved version that naturally includes the keyword
- "location": the location label from the bullet list
- "source_type": "experience" or "project"
- "source_index": the integer index from the bracket at the start of the chosen bullet

Return ONLY the JSON object, no explanation."""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, Exception):
        return None
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
python -m pytest tests/test_job_scraper.py -v
```
Expected: 5 PASSED.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml requirements.txt support/job_scraper.py tests/test_job_scraper.py
git commit -m "feat: add job scraper module with keyword extraction and rewrite suggestions"
```

---

## Task 8: New Submission — Scrape Tabs + Keywords Panel

**Files:**
- Modify: `pages/new_submission.py`

This task modifies the Job Description input section, adds the keywords panel, and updates the generate flow to apply accepted rewrites before calling the LLM.

- [ ] **Step 1: Add helper function and new session state keys at the top of `pages/new_submission.py`**

Add these imports after the existing import block:

```python
from support.job_scraper import scrape_job_description, extract_keywords, generate_keyword_suggestions
```

Immediately after the `migrate_legacy_portfolio()` call, add session state initialisation:

```python
# Session state for job scraping and keywords
for key in [
    "scraped_job_url",
    "extracted_keywords",      # dict: {category: [keywords]}
    "removed_keywords",        # set: keywords the user dismissed
    "custom_keywords",         # list: user-added keywords
    "keyword_suggestions",     # dict: {keyword: suggestion_dict}
    "accepted_rewrites",       # list: [{keyword, original_bullet, suggested_rewrite, source_type, source_index}]
]:
    if key not in st.session_state:
        st.session_state[key] = (set() if key == "removed_keywords" else
                                  [] if key in ("custom_keywords", "accepted_rewrites") else
                                  {} if key in ("extracted_keywords", "keyword_suggestions") else
                                  None)
```

- [ ] **Step 2: Replace the Job Description text area with a tabbed input**

Replace the `st.subheader("📋 Job Description")` block and `job_description = st.text_area(...)` with:

```python
st.subheader("📋 Job Description")

paste_tab, scrape_tab = st.tabs(["✍️ Paste Manually", "🔗 Scrape from URL"])

with scrape_tab:
    scrape_url = st.text_input("Job posting URL", placeholder="https://company.com/careers/role-123")
    if st.button("🔍 Fetch Job"):
        if not scrape_url.strip():
            st.error("Please enter a URL.")
        else:
            with st.spinner("Fetching job description..."):
                scraped_text = scrape_job_description(scrape_url.strip())
            if scraped_text and len(scraped_text) >= 200:
                st.session_state.scraped_jd_text = scraped_text
                st.session_state.scraped_job_url = scrape_url.strip()
                st.toast("✅ Job description fetched!")
                st.rerun()
            else:
                st.error("❌ Could not extract enough text from that URL. Try pasting manually.")

    if st.session_state.get("scraped_jd_text"):
        st.session_state.scraped_jd_text = st.text_area(
            "Fetched job description (editable)",
            value=st.session_state.scraped_jd_text,
            height=200,
            key="scrape_jd_area",
        )

with paste_tab:
    if "paste_jd_text" not in st.session_state:
        st.session_state.paste_jd_text = ""
    st.session_state.paste_jd_text = st.text_area(
        "Paste the job description here",
        value=st.session_state.paste_jd_text,
        height=200,
        placeholder="Paste the complete job description including requirements, responsibilities, and company information...",
        key="paste_jd_area",
    )

# Active job description — whichever tab has content
job_description = (
    st.session_state.get("scraped_jd_text") or
    st.session_state.get("paste_jd_text") or
    ""
)
```

- [ ] **Step 3: Add the Keywords Panel (appears when job_description is populated)**

Insert the following block between the job description section and the Generate button:

```python
# ── Keywords Panel ───────────────────────────────────────────────────────────
if job_description.strip():
    st.markdown("---")
    st.subheader("🔑 Keywords")

    # Extract keywords button
    if st.button("🔑 Extract Keywords from Job Description"):
        with st.spinner("Extracting keywords..."):
            if "information_extractor" not in st.session_state:
                st.session_state.information_extractor = InformationExtractor()
            if selected_model == "gemini" and gemini_api_key:
                st.session_state.information_extractor.MODEL = load_gemini_model()
            elif selected_model == "openai" and openai_api_key:
                st.session_state.information_extractor.MODEL = load_openAI_model()

            llm = st.session_state.information_extractor.MODEL
            keywords = extract_keywords(job_description, llm)
            if keywords:
                st.session_state.extracted_keywords = keywords
                st.session_state.removed_keywords = set()
                st.session_state.keyword_suggestions = {}
                st.rerun()
            else:
                st.error("❌ Could not extract keywords. Try again or add them manually.")

    if st.session_state.extracted_keywords or st.session_state.custom_keywords:
        kw_col, sug_col = st.columns([1, 1.5])

        with kw_col:
            st.markdown("**Keywords**")

            # Render keywords by category
            for category, kws in st.session_state.extracted_keywords.items():
                active_kws = [k for k in kws if k not in st.session_state.removed_keywords]
                if active_kws:
                    st.markdown(f"*{category}*")
                    for kw in active_kws:
                        c1, c2 = st.columns([0.85, 0.15])
                        c1.markdown(f"• {kw}")
                        if c2.button("❌", key=f"rm_{kw}", help=f"Remove {kw}"):
                            st.session_state.removed_keywords.add(kw)
                            st.session_state.keyword_suggestions.pop(kw, None)
                            st.rerun()

            # Custom keywords
            if st.session_state.custom_keywords:
                st.markdown("*Custom*")
                for kw in list(st.session_state.custom_keywords):
                    c1, c2 = st.columns([0.85, 0.15])
                    c1.markdown(f"• {kw}")
                    if c2.button("❌", key=f"rm_custom_{kw}"):
                        st.session_state.custom_keywords.remove(kw)
                        st.session_state.keyword_suggestions.pop(kw, None)
                        st.rerun()

            # Add custom keyword
            new_kw = st.text_input("Add keyword", key="custom_kw_input",
                                    placeholder="e.g. Kubernetes")
            if st.button("➕ Add"):
                kw = new_kw.strip()
                if kw and kw not in st.session_state.custom_keywords:
                    st.session_state.custom_keywords.append(kw)
                    st.rerun()

        with sug_col:
            st.markdown("**Suggestions**")

            # Collect all active keywords
            all_active = [
                k for cat_kws in st.session_state.extracted_keywords.values()
                for k in cat_kws if k not in st.session_state.removed_keywords
            ] + st.session_state.custom_keywords

            if st.button("💡 Generate Suggestions"):
                if "information_extractor" not in st.session_state:
                    st.session_state.information_extractor = InformationExtractor()
                if selected_model == "gemini" and gemini_api_key:
                    st.session_state.information_extractor.MODEL = load_gemini_model()
                elif selected_model == "openai" and openai_api_key:
                    st.session_state.information_extractor.MODEL = load_openAI_model()

                llm = st.session_state.information_extractor.MODEL
                with st.spinner("Generating suggestions..."):
                    for kw in all_active:
                        if kw not in st.session_state.keyword_suggestions:
                            suggestion = generate_keyword_suggestions(
                                kw, st.session_state.structured_cv, llm
                            )
                            if suggestion:
                                st.session_state.keyword_suggestions[kw] = suggestion
                st.rerun()

            for kw, sug in st.session_state.keyword_suggestions.items():
                if kw in st.session_state.removed_keywords:
                    continue
                already_accepted = any(r["keyword"] == kw for r in st.session_state.accepted_rewrites)
                with st.expander(f"{'✅ ' if already_accepted else ''}**{kw}**",
                                  expanded=not already_accepted):
                    st.markdown(f"📍 *{sug.get('location', '')}*")
                    st.markdown("**Original:**")
                    st.code(sug.get("original_bullet", ""), language=None)
                    st.markdown("**Suggested rewrite:**")
                    st.code(sug.get("suggested_rewrite", ""), language=None)
                    if not already_accepted:
                        a_col, i_col = st.columns(2)
                        if a_col.button("✅ Accept", key=f"accept_{kw}"):
                            st.session_state.accepted_rewrites.append(sug)
                            st.rerun()
                        if i_col.button("➖ Ignore", key=f"ignore_{kw}"):
                            st.session_state.keyword_suggestions.pop(kw, None)
                            st.rerun()
                    else:
                        if st.button("↩️ Undo Accept", key=f"undo_{kw}"):
                            st.session_state.accepted_rewrites = [
                                r for r in st.session_state.accepted_rewrites if r["keyword"] != kw
                            ]
                            st.rerun()

    if st.session_state.accepted_rewrites:
        st.success(f"✅ {len(st.session_state.accepted_rewrites)} rewrite(s) accepted — will be applied before generation.")

    st.markdown("---")
```

- [ ] **Step 4: Add `_apply_accepted_rewrites()` helper and update the Generate button**

Add this helper function near the top of the file (after imports, before `st.set_page_config`):

```python
def _apply_accepted_rewrites(cv_object, accepted_rewrites: list):
    """Return a deep copy of cv_object with accepted rewrites applied."""
    import copy
    cv = copy.deepcopy(cv_object)
    for rewrite in accepted_rewrites:
        source_type = rewrite.get("source_type")
        source_index = rewrite.get("source_index", -1)
        original = rewrite.get("original_bullet", "")
        replacement = rewrite.get("suggested_rewrite", "")

        if source_type == "experience" and cv.experiences and source_index < len(cv.experiences):
            exp = cv.experiences[source_index]
            if exp.description and original in exp.description:
                exp.description = exp.description.replace(original, replacement, 1)
        elif source_type == "project" and cv.projects and source_index < len(cv.projects):
            proj = cv.projects[source_index]
            if proj.description and original in proj.description:
                proj.description = proj.description.replace(original, replacement, 1)
    return cv
```

Update the Generate button to apply rewrites before calling the LLM. Replace:
```python
st.session_state.information_extractor.structured_cv = st.session_state.structured_cv
```
With:
```python
# Apply any accepted keyword rewrites to a working copy before generation
working_cv = _apply_accepted_rewrites(
    st.session_state.structured_cv,
    st.session_state.get("accepted_rewrites", []),
)
st.session_state.information_extractor.structured_cv = working_cv
```

Also update `create_new_cv` and `create_new_cover_letter` calls to use `working_cv` instead of `st.session_state.structured_cv`:
```python
new_cv = st.session_state.information_extractor.create_new_cv(
    structured_curriculum=working_cv,
    job_description=job_description,
)
cover_letter = st.session_state.information_extractor.create_new_cover_letter(
    structured_curriculum=working_cv,
    job_description=job_description,
)
```

After a successful `create_pdf()` call, pre-fill the job URL in the DB if scraping was used:
```python
st.session_state.information_extractor.create_pdf()
st.session_state.is_new_submission = False
st.session_state.current_submission_id = "new"
# Pre-fill job URL if scraped
if st.session_state.get("scraped_job_url"):
    from support.submission_manager import get_all_submissions, update_submission_metadata
    all_subs = get_all_submissions()
    if all_subs:
        latest_id = all_subs[-1][0]
        update_submission_metadata(latest_id, "Applied", "", st.session_state.scraped_job_url)
st.success("✅ New submission created in database!")
```

- [ ] **Step 5: Manual smoke test**

Start the app and go to New Submission. Verify:
- Two tabs appear: "✍️ Paste Manually" and "🔗 Scrape from URL"
- Pasting a job description and clicking "🔑 Extract Keywords" shows a two-column panel
- Keywords appear as chips with ❌ buttons
- Custom keywords can be added
- "💡 Generate Suggestions" shows original + rewrite for each keyword
- "✅ Accept" marks a rewrite as accepted; counter updates above Generate button
- "🪄 Generate Tailored Documents" works end-to-end with accepted rewrites applied
- Scraping a URL populates the text area

- [ ] **Step 6: Commit**

```bash
git add pages/new_submission.py
git commit -m "feat: add job URL scraping, keyword extraction, and rewrite suggestions to New Submission"
```

---

## Task 9: Docker Setup

**Files:**
- Modify: `support/settings.py`
- Modify: `requirements.txt`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Update `support/settings.py` to check environment variables before `config.ini`**

Replace the entire file with:

```python
import configparser
import os

# When set to True, the application will use provided test files and enable a "testing environment".
# Set to False for "production" use.

TESTING = False
if TESTING:
    openai_api_key_value = "fake-api-key"
    gemini_api_key_value = "fake-api-key"
    groq_api_key_value = "fake-api-key"
    dest_dir = "test"
else:
    dest_dir = "output"

    # Env vars take precedence (used in Docker / cloud deployments).
    # Fall back to config.ini for local dev.
    openai_api_key_value = os.environ.get("OPENAI_API_KEY", "")
    gemini_api_key_value = os.environ.get("GEMINI_API_KEY", "")
    groq_api_key_value = os.environ.get("GROQ_API_KEY", "")

    if os.path.exists("config.ini"):
        config = configparser.ConfigParser()
        config.read("config.ini")
        if not openai_api_key_value and "OPENAI" in config and "API_KEY" in config["OPENAI"]:
            openai_api_key_value = config.get("OPENAI", "API_KEY")
        if not gemini_api_key_value and "GEMINI" in config and "API_KEY" in config["GEMINI"]:
            gemini_api_key_value = config.get("GEMINI", "API_KEY")
        if not groq_api_key_value and "GROQ" in config and "API_KEY" in config["GROQ"]:
            groq_api_key_value = config.get("GROQ", "API_KEY")

if not os.path.exists(dest_dir):
    os.makedirs(dest_dir)
```

- [ ] **Step 2: Verify `requirements.txt` is up to date**

`requirements.txt` should contain (from Task 7 Step 2):
```
langchain-google-genai==2.1.8
langchain-openai==0.3.18
langchain-groq>=0.3.0
markitdown[all]==0.1.2
pydantic==2.11.5
streamlit==1.45.1
xhtml2pdf>=0.2.16
beautifulsoup4>=4.12.0
playwright>=1.44.0
requests>=2.31.0
```

- [ ] **Step 3: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium binary
RUN playwright install chromium

# Copy application source
COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "home.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./output:/app/output          # persists SQLite DB, portfolios, generated PDFs
      - ./config.ini:/app/config.ini:ro  # API keys (read-only; omit on deployment)
    restart: unless-stopped
    environment:
      # Uncomment and set these for deployment (they take precedence over config.ini):
      # - GROQ_API_KEY=your_key_here
      # - OPENAI_API_KEY=your_key_here
      # - GEMINI_API_KEY=your_key_here
```

- [ ] **Step 5: Create `.dockerignore`**

```
output/
config.ini
__pycache__/
**/__pycache__/
*.pyc
*.pyo
.git/
.gitignore
venv/
.venv/
test/
docs/
*.md
uv.lock
```

- [ ] **Step 6: Test the Docker build**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
docker build -t tailor-your-document .
```
Expected: Build succeeds. The `playwright install chromium` step will take ~2 minutes on first build.

- [ ] **Step 7: Test running via docker-compose**

```bash
docker compose up
```
Open `http://localhost:8501` in browser. Verify:
- App loads correctly
- `output/` directory is created on the host
- Portfolios and DB persist across container restarts (`docker compose down && docker compose up`)

- [ ] **Step 8: Commit**

```bash
git add support/settings.py requirements.txt Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Docker containerization with volume mount persistence and env var API key support"
```

---

## Full Test Run

After all tasks are complete, run the full test suite:

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
python -m pytest tests/ -v
```

Expected: All tests in `test_submission_manager.py`, `test_portfolio_manager.py`, and `test_job_scraper.py` pass.
