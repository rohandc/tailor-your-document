# LaTeX Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all CV rendering to LaTeX (pdflatex + pdf2image), retire the HTML CV pipeline, unify the CV editor into a reusable component, improve my_submissions + submission_detail UX, and keep the Resume Library (latex_resume.py) wired into the rest of the app.

**Architecture:** A shared `cv_editor_component.py` renders a structured `st.form` that returns a `FinalCurriculum`. Every page that shows a CV preview calls `show_pdf_pages(pdf_bytes)` from `pdf_preview.py`. Cover letters stay on the HTML→xhtml2pdf path and are not touched. The submissions DB gets two new columns (`template_name`, `cv_pdf_cache`) so the detail page loads a cached PDF instantly.

**Tech Stack:** Python 3.12, Streamlit 1.45, Jinja2 (latex templates), pdflatex (Docker), pdf2image + poppler-utils, sqlite3, xhtml2pdf (cover letter only), pickle.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `support/cv_editor_component.py` | Shared structured CV editing form |
| **Modify** | `support/submission_manager.py` | Add template_name + cv_pdf_cache cols; add compile/cache/CL-only functions |
| **Rewrite** | `pages/latex_resume.py` | Resume Library — uses shared component, keeps save/load manager |
| **Modify** | `pages/new_submission.py` | Replace HTML CV editor+preview with shared component + LaTeX preview |
| **Rewrite** | `pages/submission_detail.py` | Structured CV editor + cached LaTeX preview; CL HTML tab unchanged |
| **Rewrite** | `pages/my_submissions.py` | Status filter + per-row CV/CL downloads; kill dropdown section |
| **Modify** | `pages/home.py` | Replace render_submissions_html iframe with plain submissions table |
| **Modify** | `support/html_builder.py` | Delete CVBuilder, render_editable_cv, render_editable_cover_letter, inject_iframe_reset, render_submissions_html; keep CoverLetterBuilder |

---

## Task 1: Create `support/cv_editor_component.py`

**Files:**
- Create: `support/cv_editor_component.py`

- [ ] **Step 1: Create the file with the full shared editor**

```python
# support/cv_editor_component.py
"""
Shared structured CV editing form.

Usage:
    submitted, final_cv = render_cv_editor(initial_cv=some_cv, key_prefix="my_page")
    if submitted and final_cv:
        # compile, save, etc.
"""
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from support.supportClasses import (
    Education,
    EducationExperience,
    Experience,
    FinalCurriculum,
    Personality,
)


def render_cv_editor(
    initial_cv: Optional[FinalCurriculum] = None,
    key_prefix: str = "cv_editor",
    submit_label: str = "Compile & Preview",
) -> Tuple[bool, Optional[FinalCurriculum]]:
    """
    Render a structured CV editing form wrapped in st.form.

    Parameters
    ----------
    initial_cv : FinalCurriculum | None
        Pre-fill form with this data.  Pass None for a blank form.
    key_prefix : str
        Unique prefix for all widget keys — required when the component is
        rendered on the same page more than once.
    submit_label : str
        Label for the form's submit button.

    Returns
    -------
    (submitted, final_cv)
        submitted  — True only on the render cycle when the button was clicked.
        final_cv   — Populated FinalCurriculum when submitted=True, else None.
    """

    def _cv_val(attr: str, default: str = "") -> str:
        if initial_cv is None:
            return default
        return getattr(initial_cv, attr, default) or default

    def _p_val(attr: str, default: str = "") -> str:
        if initial_cv is None or initial_cv.personality is None:
            return default
        return getattr(initial_cv.personality, attr, default) or default

    with st.form(f"{key_prefix}_form"):
        # ── Personal Info ──────────────────────────────────────────────────
        st.subheader("Personal Info")
        fi_c1, fi_c2 = st.columns(2)
        with fi_c1:
            first_name = st.text_input("First Name", value=_p_val("name"),
                                       key=f"{key_prefix}_first_name")
            job_title_input = st.text_input(
                "Job Title",
                value=_cv_val("job_title") or _p_val("job_title"),
                key=f"{key_prefix}_job_title",
            )
            email_input = st.text_input("Email", value=_p_val("e_mail"),
                                        key=f"{key_prefix}_email")
        with fi_c2:
            last_name = st.text_input("Last Name", value=_p_val("surname"),
                                      key=f"{key_prefix}_last_name")
            phone_input = st.text_input("Phone", value=_p_val("telephone"),
                                        key=f"{key_prefix}_phone")
            linkedin_input = st.text_input("LinkedIn URL",
                                           value=_p_val("linkedin_link"),
                                           key=f"{key_prefix}_linkedin")
        address_input = st.text_input("Address", value=_p_val("address"),
                                      key=f"{key_prefix}_address")

        st.divider()

        # ── Summary ────────────────────────────────────────────────────────
        st.subheader("Summary")
        summary_input = st.text_area(
            "Professional Summary (2-3 sentences)",
            value=_cv_val("summary"),
            height=90,
            key=f"{key_prefix}_summary",
        )

        st.divider()

        # ── Work Experience ────────────────────────────────────────────────
        st.subheader("Work Experience")
        existing_exp: list = list(initial_cv.experiences or []) if initial_cv else []
        if not existing_exp:
            existing_exp = [Experience()]

        exp_data = []
        for i, exp in enumerate(existing_exp):
            with st.expander(f"Experience {i + 1}: {exp.title or 'New'}",
                             expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    t = st.text_input("Title", value=exp.title or "",
                                      key=f"{key_prefix}_exp_title_{i}")
                    sd = st.text_input("Start Date", value=exp.start_date or "",
                                       key=f"{key_prefix}_exp_sd_{i}")
                with ec2:
                    c = st.text_input("Company", value=exp.company or "",
                                      key=f"{key_prefix}_exp_company_{i}")
                    ed = st.text_input("End Date", value=exp.end_date or "",
                                       key=f"{key_prefix}_exp_ed_{i}")
                desc = st.text_area(
                    "Bullets (one per line, start with •, -, or *)",
                    value=exp.description or "",
                    height=100,
                    key=f"{key_prefix}_exp_desc_{i}",
                )
                exp_data.append((t, c, sd, ed, desc))

        st.divider()

        # ── Education ──────────────────────────────────────────────────────
        st.subheader("Education")
        existing_edu: list = list(initial_cv.education or []) if initial_cv else []
        if not existing_edu:
            existing_edu = [EducationExperience()]

        edu_data = []
        for i, edu in enumerate(existing_edu):
            with st.expander(f"Education {i + 1}: {edu.title or 'New'}",
                             expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    t = st.text_input("Degree / Title", value=edu.title or "",
                                      key=f"{key_prefix}_edu_title_{i}")
                    sd = st.text_input("Start Date", value=edu.start_date or "",
                                       key=f"{key_prefix}_edu_sd_{i}")
                with ec2:
                    s = st.text_input("School / University",
                                      value=edu.school_name or "",
                                      key=f"{key_prefix}_edu_school_{i}")
                    ed = st.text_input("End Date", value=edu.end_date or "",
                                       key=f"{key_prefix}_edu_ed_{i}")
                desc = st.text_area("Description", value=edu.description or "",
                                    height=80,
                                    key=f"{key_prefix}_edu_desc_{i}")
                edu_data.append((t, s, sd, ed, desc))

        st.divider()

        # ── Projects ───────────────────────────────────────────────────────
        st.subheader("Projects")
        existing_proj: list = list(initial_cv.projects or []) if initial_cv else []

        proj_data = []
        for i, proj in enumerate(existing_proj):
            with st.expander(f"Project {i + 1}: {proj.title or 'New'}",
                             expanded=(i == 0)):
                pc1, pc2 = st.columns(2)
                with pc1:
                    t = st.text_input("Project Title", value=proj.title or "",
                                      key=f"{key_prefix}_proj_title_{i}")
                    sd = st.text_input("Start Date", value=proj.start_date or "",
                                       key=f"{key_prefix}_proj_sd_{i}")
                with pc2:
                    c = st.text_input("Organisation / Context",
                                      value=proj.company or "",
                                      key=f"{key_prefix}_proj_company_{i}")
                    ed = st.text_input("End Date", value=proj.end_date or "",
                                       key=f"{key_prefix}_proj_ed_{i}")
                desc = st.text_area("Bullets", value=proj.description or "",
                                    height=100,
                                    key=f"{key_prefix}_proj_desc_{i}")
                proj_data.append((t, c, sd, ed, desc))

        st.divider()

        # ── Skills ─────────────────────────────────────────────────────────
        st.subheader("Skills")
        _hard_seed = pd.DataFrame({
            "Skill": pd.Series(
                (initial_cv.hard_skills or []) if initial_cv else [],
                dtype="string",
            )
        })
        _soft_seed = pd.DataFrame({
            "Skill": pd.Series(
                (initial_cv.soft_skills or []) if initial_cv else [],
                dtype="string",
            )
        })

        with st.expander("🛠️ Technical Skills", expanded=True):
            hard_skills_df = st.data_editor(
                _hard_seed,
                num_rows="dynamic",
                use_container_width=True,
                key=f"{key_prefix}_hard_skills",
                column_config={
                    "Skill": st.column_config.TextColumn("Skill", required=False)
                },
            )

        with st.expander("🤝 Soft Skills", expanded=False):
            soft_skills_df = st.data_editor(
                _soft_seed,
                num_rows="dynamic",
                use_container_width=True,
                key=f"{key_prefix}_soft_skills",
                column_config={
                    "Skill": st.column_config.TextColumn("Skill", required=False)
                },
            )

        submitted = st.form_submit_button(submit_label, type="primary")

    if not submitted:
        return False, None

    # ── Build FinalCurriculum ──────────────────────────────────────────────
    personality = Personality(
        name=first_name or None,
        surname=last_name or None,
        e_mail=email_input or None,
        telephone=phone_input or None,
        linkedin_link=linkedin_input or None,
        address=address_input or None,
        job_title=job_title_input or None,
    )
    experiences = [
        Experience(
            title=t or None, company=c or None,
            start_date=sd or None, end_date=ed or None, description=desc or None,
        )
        for t, c, sd, ed, desc in exp_data
        if any([t, c, sd, ed, desc])
    ]
    education = [
        EducationExperience(
            title=t or None, school_name=s or None,
            start_date=sd or None, end_date=ed or None, description=desc or None,
        )
        for t, s, sd, ed, desc in edu_data
        if any([t, s, sd, ed, desc])
    ]
    projects = [
        Experience(
            title=t or None, company=c or None,
            start_date=sd or None, end_date=ed or None, description=desc or None,
        )
        for t, c, sd, ed, desc in proj_data
        if any([t, c, sd, ed, desc])
    ]
    hard_skills = [
        str(s).strip() for s in hard_skills_df["Skill"].tolist()
        if s is not None and str(s).strip()
    ]
    soft_skills = [
        str(s).strip() for s in soft_skills_df["Skill"].tolist()
        if s is not None and str(s).strip()
    ]

    final_cv = FinalCurriculum(
        personality=personality,
        job_title=job_title_input or None,
        summary=summary_input or None,
        experiences=experiences,
        projects=projects,
        education=education,
        hard_skills=hard_skills,
        soft_skills=soft_skills,
    )
    return True, final_cv
```

- [ ] **Step 2: Verify the import chain is correct**

Check that `EducationExperience` and `Experience` are both exported from `support/supportClasses.py`:

```bash
grep -n "class EducationExperience\|class Experience\|class FinalCurriculum\|class Personality" \
  /Users/rohan.dcosta/Documents/personal/tailor-your-document/support/supportClasses.py
```

Expected: four lines with class definitions. If `EducationExperience` is named differently (e.g. `Education`), update the import in `cv_editor_component.py` to match.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
git add support/cv_editor_component.py
git commit -m "feat: add shared cv_editor_component with render_cv_editor()"
```

---

## Task 2: Extend `support/submission_manager.py`

**Files:**
- Modify: `support/submission_manager.py`

Add two DB columns (`template_name`, `cv_pdf_cache`) and three new functions. Do not touch existing functions yet — that happens in Task 8.

- [ ] **Step 1: Add the two new columns to the `initialize_db` migration block**

Find the existing migration block (around line 31):

```python
        for column_def in [
            "status TEXT DEFAULT 'Applied'",
            "notes TEXT",
            "job_url TEXT",
        ]:
```

Replace it with:

```python
        for column_def in [
            "status TEXT DEFAULT 'Applied'",
            "notes TEXT",
            "job_url TEXT",
            "template_name TEXT DEFAULT 'rohans_format'",
            "cv_pdf_cache BLOB",
        ]:
```

- [ ] **Step 2: Add three new functions at the bottom of the file**

Append after the last function in `submission_manager.py`:

```python
def compile_cv_for_submission(submission_id: int, template_name: str) -> bytes:
    """Compile a LaTeX CV for the given submission, cache it in the DB, and return PDF bytes."""
    from support.latex_builder import render_latex, compile_latex

    cv_object, _, _ = get_submission_objects(submission_id)
    if cv_object is None:
        raise ValueError(f"Submission {submission_id} not found or has no CV data.")

    latex_source = render_latex(cv_object, template_name=template_name)
    pdf_bytes = compile_latex(latex_source)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE submissions SET cv_pdf_cache = ?, template_name = ? WHERE id = ?",
            (pdf_bytes, template_name, submission_id),
        )
        conn.commit()

    return pdf_bytes


def get_cv_pdf_bytes(submission_id: int) -> tuple:
    """
    Return (cached_pdf_bytes, template_name) for a submission.
    cached_pdf_bytes is None if the CV has never been compiled.
    """
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT cv_pdf_cache, COALESCE(template_name, 'rohans_format') "
                "FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
        if row:
            return row[0], row[1]
        return None, "rohans_format"
    except Exception as e:
        print(f"Error getting CV PDF bytes: {e}")
        return None, "rohans_format"


def generate_cl_pdf_from_submission(submission_id: int) -> tuple:
    """
    Generate a cover-letter PDF only (HTML → xhtml2pdf path).
    Returns (cl_pdf_path, temp_dir) on success, or (None, None) on failure.
    """
    try:
        _, cover_letter_object, _ = get_submission_objects(submission_id)
        if cover_letter_object is None:
            return None, None

        temp_dir = tempfile.mkdtemp(prefix="cv_builder_")
        cover_letter_builder = CoverLetterBuilder()
        cl_html = cover_letter_builder.build_html_from_cover_letter(
            cover_letter_object, "1", temp_dir
        )
        cl_pdf_path = os.path.join(temp_dir, f"cover_letter_{submission_id}.pdf")
        with open(cl_pdf_path, "wb") as f:
            pisa.CreatePDF(cl_html, dest=f)

        return cl_pdf_path, temp_dir
    except Exception as e:
        print(f"Error generating CL PDF: {e}")
        return None, None
```

- [ ] **Step 3: Commit**

```bash
git add support/submission_manager.py
git commit -m "feat: add template_name + cv_pdf_cache columns and compile/cache/CL-only functions"
```

---

## Task 3: Rebuild `pages/latex_resume.py` (Resume Library)

**Files:**
- Modify: `pages/latex_resume.py`

Replace the entire file. Uses `render_cv_editor` from Task 1. Keeps `latex_resume_manager` for save/load/delete. Removes all manual form widget code.

- [ ] **Step 1: Replace the full file**

```python
# pages/latex_resume.py
from pathlib import Path

import streamlit as st

from support.cv_editor_component import render_cv_editor
from support.latex_builder import compile_latex, render_latex
from support.latex_resume_manager import (
    delete_resume,
    list_resumes,
    load_resume,
    save_resume,
)
from support.pdf_preview import show_pdf_pages
from support.supportClasses import FinalCurriculum

st.set_page_config(page_title="Resume Library", layout="wide")
st.title("📚 Resume Library")
st.markdown(
    "Build, save, and manage named LaTeX resume drafts independent of job applications."
)

# ── Load / Delete saved resumes ───────────────────────────────────────────────

saved = list_resumes()

if saved:
    load_col, del_col = st.columns([4, 1])
    with load_col:
        options = ["— Select a saved resume —"] + [
            f"{e['name']}  (modified {e['last_modified'].strftime('%Y-%m-%d %H:%M')})"
            for e in saved
        ]
        chosen = st.selectbox("📂 Load Saved Resume", options=options,
                               key="rl_load_selector")
    with del_col:
        st.write("")
        st.write("")
        if chosen != options[0]:
            chosen_name = saved[options.index(chosen) - 1]["name"]
            if st.button("🗑️ Delete", key="rl_delete_btn"):
                delete_resume(chosen_name)
                st.session_state.pop("rl_loaded_cv", None)
                st.session_state.pop("rl_loaded_name", None)
                st.toast(f"Deleted '{chosen_name}'")
                st.rerun()

    if chosen != options[0]:
        chosen_name = saved[options.index(chosen) - 1]["name"]
        if st.button(f"📥 Load '{chosen_name}'", type="primary", key="rl_load_btn"):
            loaded = load_resume(chosen_name)
            if loaded:
                st.session_state["rl_loaded_cv"] = loaded
                st.session_state["rl_loaded_name"] = chosen_name
                st.session_state.pop("rl_pdf_bytes", None)
                st.session_state.pop("rl_latex_source", None)
                st.toast(f"Loaded '{chosen_name}'")
                st.rerun()

if st.session_state.get("rl_loaded_name"):
    st.info(f"✏️ Editing: **{st.session_state['rl_loaded_name']}**")

# ── Template selector ─────────────────────────────────────────────────────────

_templates_dir = Path(__file__).parent.parent / "support" / "latex_templates"
_available = sorted(p.stem for p in _templates_dir.glob("*.tex"))

if not _available:
    st.error("No LaTeX templates found in `support/latex_templates/`. Add a `.tex` file there.")
    st.stop()

selected_template = st.selectbox(
    "🎨 Template",
    options=_available,
    index=_available.index("rohans_format") if "rohans_format" in _available else 0,
    help="Edit .tex files in support/latex_templates/ — changes apply on next compile.",
    key="rl_template",
)

# ── Load from active portfolio as fallback ────────────────────────────────────

_initial_cv: FinalCurriculum | None = (
    st.session_state.get("rl_loaded_cv")
    or st.session_state.get("final_cv_content")
)

# ── Two-column layout ─────────────────────────────────────────────────────────

form_col, preview_col = st.columns([1, 1])

with form_col:
    submitted, built_cv = render_cv_editor(
        initial_cv=_initial_cv,
        key_prefix="rl",
        submit_label="Compile & Preview",
    )

if submitted and built_cv:
    st.session_state["rl_last_built_cv"] = built_cv
    try:
        latex_source = render_latex(built_cv, template_name=selected_template)
        st.session_state["rl_latex_source"] = latex_source
        pdf_bytes = compile_latex(latex_source)
        st.session_state["rl_pdf_bytes"] = pdf_bytes
    except RuntimeError as exc:
        err_msg = str(exc)
        if "not available" in err_msg or "not found" in err_msg:
            st.error("pdflatex is not available. Make sure you are running inside the Docker container.")
        else:
            st.error(f"LaTeX compilation error:\n\n```\n{err_msg}\n```")
        st.session_state["rl_pdf_bytes"] = None

# ── Save resume ───────────────────────────────────────────────────────────────

_cv_to_save = st.session_state.get("rl_last_built_cv") or _initial_cv
if _cv_to_save is not None:
    st.divider()
    st.subheader("💾 Save to Library")
    if st.session_state.get("rl_last_built_cv") is None:
        st.caption("⚠️ Click **Compile & Preview** first to capture latest edits.")
    sv1, sv2 = st.columns([3, 1])
    with sv1:
        resume_name = st.text_input(
            "Resume name",
            value=st.session_state.get("rl_loaded_name", ""),
            placeholder="e.g. Senior Backend Engineer",
            label_visibility="collapsed",
            key="rl_save_name",
        )
    with sv2:
        if st.button("💾 Save", type="primary", use_container_width=True, key="rl_save_btn"):
            if not resume_name.strip():
                st.warning("Enter a name before saving.")
            else:
                try:
                    save_resume(resume_name.strip(), _cv_to_save)
                    st.session_state["rl_loaded_name"] = resume_name.strip()
                    st.toast(f"Saved '{resume_name.strip()}'")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")

# ── Preview panel ─────────────────────────────────────────────────────────────

with preview_col:
    st.subheader("Preview")
    pdf_bytes = st.session_state.get("rl_pdf_bytes")
    latex_source = st.session_state.get("rl_latex_source")

    if pdf_bytes or latex_source:
        with st.expander("📝 LaTeX Source", expanded=False):
            if latex_source:
                st.code(latex_source, language="latex")
            else:
                st.info("LaTeX source not available.")

        with st.expander("🖼️ Compiled PDF", expanded=True):
            if pdf_bytes:
                show_pdf_pages(pdf_bytes)
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name="resume.pdf",
                    mime="application/pdf",
                )
            else:
                st.warning("PDF not available — compilation failed.")
    else:
        st.info("Fill in the form and click **Compile & Preview** to generate your resume.")
```

- [ ] **Step 2: Commit**

```bash
git add pages/latex_resume.py
git commit -m "refactor: rebuild latex_resume as Resume Library using shared cv_editor_component"
```

---

## Task 4: Update `pages/new_submission.py` — Replace CV Editor & Preview

**Files:**
- Modify: `pages/new_submission.py`

Replace only the "Document Editor and Preview" section (lines 366–387). Everything above (JD input, keywords, generate button) stays unchanged.

- [ ] **Step 1: Update the imports at the top of the file**

Find the existing import block and add / replace as follows:

```python
# REMOVE only this one import (CVBuilder-side only):
from support.html_builder import render_editable_cv, render_editable_cover_letter, inject_iframe_reset

# REPLACE with:
from support.html_builder import render_editable_cover_letter, inject_iframe_reset
from pathlib import Path
from support.cv_editor_component import render_cv_editor
from support.latex_builder import render_latex, compile_latex
from support.pdf_preview import show_pdf_pages
from support.latex_resume_manager import list_resumes, load_resume
```

Keep all other existing imports unchanged.

- [ ] **Step 2: Replace the "Document Editor and Preview" section**

Find and replace the block that starts with:
```python
# ── Document Editor and Preview ──────────────────────────────────────────────
if "generated_html" in st.session_state and "generated_html_cover_letter" in st.session_state:
```

Replace the entire block (everything from that comment down to the end of tab2) with:

```python
# ── Document Editor and Preview ──────────────────────────────────────────────
if "generated_html" in st.session_state and "generated_html_cover_letter" in st.session_state:
    st.subheader("✏️ Edit & Preview Documents")

    # Template selector (outside form so it doesn't force re-render on change)
    _templates_dir = Path(__file__).parent.parent / "support" / "latex_templates"
    _available = sorted(p.stem for p in _templates_dir.glob("*.tex"))
    _default_idx = _available.index("rohans_format") if "rohans_format" in _available else 0
    ns_template = st.selectbox(
        "🎨 LaTeX Template",
        options=_available,
        index=_default_idx,
        key="ns_template",
    )

    # Optional: load a saved resume from the library as starting point
    _saved_resumes = list_resumes()
    if _saved_resumes:
        _lib_options = ["— Use generated CV —"] + [e["name"] for e in _saved_resumes]
        _lib_choice = st.selectbox(
            "📚 Or load a base from Resume Library",
            options=_lib_options,
            key="ns_lib_choice",
        )
        if _lib_choice != _lib_options[0]:
            if st.button("📥 Load from Library", key="ns_load_lib_btn"):
                loaded = load_resume(_lib_choice)
                if loaded:
                    st.session_state["final_cv_content"] = loaded
                    st.toast(f"Loaded '{_lib_choice}' as CV base")
                    st.rerun()

    tab1, tab2 = st.tabs(["📄 CV Editor & Preview", "✉️ Cover Letter Preview"])

    with tab1:
        form_col, preview_col = st.columns([1, 1])

        with form_col:
            ns_submitted, ns_cv = render_cv_editor(
                initial_cv=st.session_state.get("final_cv_content"),
                key_prefix="ns_cv",
                submit_label="Compile CV Preview",
            )

        if ns_submitted and ns_cv:
            st.session_state["final_cv_content"] = ns_cv
            st.session_state["ns_template_used"] = ns_template
            try:
                _latex = render_latex(ns_cv, template_name=ns_template)
                _pdf = compile_latex(_latex)
                st.session_state["ns_cv_pdf_bytes"] = _pdf
                st.session_state["ns_cv_latex_source"] = _latex
            except RuntimeError as exc:
                st.error(f"LaTeX compilation error:\n\n```\n{str(exc)}\n```")
                st.session_state["ns_cv_pdf_bytes"] = None

        with preview_col:
            st.markdown("**👀 CV Preview**")
            _pdf_preview = st.session_state.get("ns_cv_pdf_bytes")
            _latex_src = st.session_state.get("ns_cv_latex_source")
            if _pdf_preview:
                with st.expander("📝 LaTeX Source", expanded=False):
                    if _latex_src:
                        st.code(_latex_src, language="latex")
                show_pdf_pages(_pdf_preview)
            else:
                st.info("Click **Compile CV Preview** to render your CV as a PDF.")

    with tab2:
        cl_left, cl_right = st.columns([0.4, 0.6], gap="large")
        with cl_left:
            st.markdown("**📝 Edit Your Cover Letter**")
            render_editable_cover_letter(st.session_state.final_cover_letter_content)
        with cl_right:
            st.markdown("**👀 Cover Letter Preview**")
            st.components.v1.html(
                inject_iframe_reset(st.session_state.get("generated_html_cover_letter", "")),
                height=1300,
                scrolling=True,
            )
```

- [ ] **Step 3: Update the "Save to Database" section to store template_name**

Find the `create_pdf()` call inside the save button handler (around line 423) and add a template update right after:

```python
                    if st.session_state.is_new_submission:
                        st.session_state.information_extractor.create_pdf()
                        st.session_state.is_new_submission = False
                        st.session_state.current_submission_id = "new"
                        # Pre-fill job URL and compile + cache the LaTeX CV
                        from support.submission_manager import (
                            get_all_submissions,
                            update_submission_metadata,
                            compile_cv_for_submission,
                        )
                        all_subs = get_all_submissions()
                        if all_subs:
                            latest_id = all_subs[-1][0]
                            st.session_state.current_submission_id = latest_id
                            if st.session_state.get("scraped_job_url"):
                                update_submission_metadata(
                                    latest_id, "Applied", "",
                                    st.session_state.scraped_job_url,
                                )
                            _tmpl = st.session_state.get("ns_template_used", "rohans_format")
                            if st.session_state.get("final_cv_content"):
                                try:
                                    compile_cv_for_submission(latest_id, _tmpl)
                                except Exception:
                                    pass  # non-fatal — can recompile from detail page
                        st.success("✅ New submission created in database!")
```

- [ ] **Step 4: Commit**

```bash
git add pages/new_submission.py
git commit -m "feat: replace HTML CV editor/preview with LaTeX shared component in new_submission"
```

---

## Task 5: Rebuild `pages/submission_detail.py`

**Files:**
- Modify: `pages/submission_detail.py`

Full rewrite. CV tab: structured editor + cached LaTeX preview + recompile button + "Save to Library". CL tab: HTML PDF via pdf2image (same as before). Status/notes/URL editable at top.

- [ ] **Step 1: Replace the entire file**

```python
# pages/submission_detail.py
import os
from pathlib import Path

import streamlit as st

from support.cv_editor_component import render_cv_editor
from support.latex_builder import compile_latex, render_latex
from support.latex_resume_manager import list_resumes, save_resume
from support.pdf_preview import show_pdf_pages
from support.submission_manager import (
    compile_cv_for_submission,
    delete_submission,
    generate_cl_pdf_from_submission,
    get_cv_pdf_bytes,
    get_submission_metadata,
    get_submission_objects,
    update_submission,
    update_submission_metadata,
    cleanup_temp_files,
)

st.set_page_config(page_title="Submission Detail", layout="wide")

STATUSES = ["Applied", "Interviewing", "Technical Assessment", "Offer", "Rejected", "Withdrawn"]

# ── Load submission ───────────────────────────────────────────────────────────

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

# ── Page header ───────────────────────────────────────────────────────────────

st.title(f"📄 {company} — {position}")
st.caption(f"Submitted: {submission_date.split('T')[0]}")

hd1, hd2, hd3 = st.columns([2, 2, 1])
with hd1:
    st.text_input("Company", value=company, disabled=True, key="sd_company_ro")
with hd2:
    st.text_input("Position", value=position, disabled=True, key="sd_position_ro")
with hd3:
    st.text_input("Date", value=submission_date.split("T")[0], disabled=True, key="sd_date_ro")

st.markdown("---")

# ── Editable metadata ─────────────────────────────────────────────────────────

st.subheader("Application Details")
m1, m2 = st.columns(2)
with m1:
    status_index = STATUSES.index(status) if status in STATUSES else 0
    new_status = st.selectbox("Status", options=STATUSES, index=status_index, key="sd_status")
    new_job_url = st.text_input("Job URL", value=job_url or "", key="sd_job_url")
with m2:
    new_notes = st.text_area("Notes", value=notes or "", height=120,
                              placeholder="Interview notes, contacts, follow-ups…",
                              key="sd_notes")

if st.button("💾 Save Details", key="sd_save_meta"):
    if update_submission_metadata(submission_id, new_status, new_notes, new_job_url):
        st.toast("✅ Details saved!")
    else:
        st.error("❌ Failed to save details.")

st.markdown("---")

# ── Template selector (shared between CV tab and recompile) ───────────────────

_templates_dir = Path(__file__).parent.parent / "support" / "latex_templates"
_available = sorted(p.stem for p in _templates_dir.glob("*.tex"))

_cached_pdf, _cached_template = get_cv_pdf_bytes(submission_id)
_default_template = _cached_template if _cached_template in _available else (
    "rohans_format" if "rohans_format" in _available else (_available[0] if _available else "")
)
_default_idx = _available.index(_default_template) if _default_template in _available else 0

selected_template = st.selectbox(
    "🎨 CV Template",
    options=_available,
    index=_default_idx,
    key="sd_template",
)

# ── Document tabs ─────────────────────────────────────────────────────────────

tab_cv, tab_cl = st.tabs(["📋 CV", "✉️ Cover Letter"])

# ─────────────────────────── CV TAB ──────────────────────────────────────────

with tab_cv:
    cv_left, cv_right = st.columns([1, 1])

    # Load the stored FinalCurriculum
    _cv_obj, _, _ = get_submission_objects(submission_id)

    with cv_left:
        st.markdown("**Edit CV**")
        sd_submitted, sd_cv = render_cv_editor(
            initial_cv=_cv_obj,
            key_prefix="sd_cv",
            submit_label="Compile & Save CV",
        )

    if sd_submitted and sd_cv:
        # Persist updated CV to DB and recompile
        _, cl_obj, jd_obj = get_submission_objects(submission_id)
        update_submission(submission_id, sd_cv, cl_obj, jd_obj)
        try:
            _new_pdf = compile_cv_for_submission(submission_id, selected_template)
            st.session_state[f"sd_cv_pdf_{submission_id}"] = _new_pdf
            st.toast("✅ CV compiled and saved.")
        except RuntimeError as exc:
            st.error(f"LaTeX compilation error:\n\n```\n{str(exc)}\n```")

    with cv_right:
        st.markdown("**CV Preview**")

        # Use session-state cache if available, else DB cache, else prompt compile
        _preview_pdf = st.session_state.get(f"sd_cv_pdf_{submission_id}") or _cached_pdf

        if _preview_pdf:
            show_pdf_pages(_preview_pdf)
            st.download_button(
                "⬇️ Download CV PDF",
                data=_preview_pdf,
                file_name=f"CV_{company}_{position}.pdf",
                mime="application/pdf",
                key="sd_cv_dl",
            )
        else:
            st.info("No compiled CV yet. Edit the form and click **Compile & Save CV**.")
            if st.button("🔄 Compile with current template", key="sd_cv_compile_btn"):
                with st.spinner("Compiling…"):
                    try:
                        _pdf = compile_cv_for_submission(submission_id, selected_template)
                        st.session_state[f"sd_cv_pdf_{submission_id}"] = _pdf
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(f"Compilation failed:\n\n```\n{str(exc)}\n```")

    # Save to Resume Library
    st.markdown("---")
    st.markdown("**💾 Save CV snapshot to Resume Library**")
    lib1, lib2 = st.columns([3, 1])
    with lib1:
        lib_name = st.text_input(
            "Library name",
            value=f"{company} – {position}",
            label_visibility="collapsed",
            key="sd_lib_name",
        )
    with lib2:
        if st.button("💾 Save to Library", use_container_width=True, key="sd_lib_save"):
            _save_cv = sd_cv if (sd_submitted and sd_cv) else _cv_obj
            if _save_cv and lib_name.strip():
                try:
                    save_resume(lib_name.strip(), _save_cv)
                    st.toast(f"Saved '{lib_name.strip()}' to Resume Library")
                except Exception as exc:
                    st.error(f"Failed: {exc}")
            else:
                st.warning("No CV to save or name is empty.")

# ─────────────────────────── COVER LETTER TAB ────────────────────────────────

with tab_cl:
    _cl_cache_key = f"sd_cl_pdf_{submission_id}"

    if _cl_cache_key not in st.session_state:
        with st.spinner("Generating cover letter preview…"):
            cl_path, temp_dir = generate_cl_pdf_from_submission(submission_id)
            if cl_path and os.path.exists(cl_path):
                with open(cl_path, "rb") as f:
                    st.session_state[_cl_cache_key] = f.read()
                cleanup_temp_files(temp_dir)
            else:
                st.session_state[_cl_cache_key] = None

    if st.button("🔄 Refresh Cover Letter", key="sd_cl_refresh"):
        st.session_state.pop(_cl_cache_key, None)
        st.rerun()

    _cl_bytes = st.session_state.get(_cl_cache_key)
    if _cl_bytes:
        show_pdf_pages(_cl_bytes)
        st.download_button(
            "⬇️ Download Cover Letter PDF",
            data=_cl_bytes,
            file_name=f"CoverLetter_{company}_{position}.pdf",
            mime="application/pdf",
            key="sd_cl_dl",
        )
    else:
        st.warning("Could not generate a cover letter preview for this submission.")

# ── Delete + back navigation ──────────────────────────────────────────────────

st.markdown("---")
nav1, nav2, nav3 = st.columns([1, 1, 2])
with nav1:
    if st.button("← Back to Submissions", key="sd_back"):
        st.switch_page("pages/my_submissions.py")
with nav2:
    confirm_del = st.checkbox("Confirm deletion", key="sd_confirm_del")
    if st.button("🗑️ Delete Submission", disabled=not confirm_del, key="sd_delete"):
        if delete_submission(submission_id):
            st.switch_page("pages/my_submissions.py")
        else:
            st.error("❌ Failed to delete submission.")
```

- [ ] **Step 2: Commit**

```bash
git add pages/submission_detail.py
git commit -m "feat: rebuild submission_detail with shared cv editor, LaTeX preview, and save-to-library"
```

---

## Task 6: Rebuild `pages/my_submissions.py`

**Files:**
- Modify: `pages/my_submissions.py`

Replace entirely. Status filter pills at top. Per-row: View, Download CV, Download CL, Delete. Remove the separate download dropdown section.

- [ ] **Step 1: Replace the full file**

```python
# pages/my_submissions.py
import os
import streamlit as st

from support.submission_manager import (
    get_all_submissions_with_metadata,
    delete_submission,
    compile_cv_for_submission,
    get_cv_pdf_bytes,
    generate_cl_pdf_from_submission,
    cleanup_temp_files,
)

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
ALL_STATUSES = ["All"] + list(STATUS_BADGE.keys())

submissions = get_all_submissions_with_metadata()
# Each row: (id, company, position, submission_date, status, notes, job_url)

if not submissions:
    st.info("No applications yet. Once you generate CVs and cover letters, they will appear here.")
    st.page_link("pages/new_submission.py", label="➕ Create First Application", icon="📝")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────

filter_col, search_col = st.columns([1, 2])
with filter_col:
    status_filter = st.selectbox("Filter by status", options=ALL_STATUSES, key="ms_status_filter")
with search_col:
    search_query = st.text_input("🔍 Search by company or position", key="ms_search")

filtered = submissions
if status_filter != "All":
    filtered = [s for s in filtered if s[4] == status_filter]
if search_query:
    q = search_query.lower()
    filtered = [s for s in filtered if q in s[1].lower() or q in s[2].lower()]

st.caption(f"Showing {len(filtered)} of {len(submissions)} submissions")
st.markdown("---")

# ── Session state for confirmation ───────────────────────────────────────────

if "ms_confirm_del" not in st.session_state:
    st.session_state.ms_confirm_del = None

# ── Table header ─────────────────────────────────────────────────────────────

cols = st.columns([2, 2, 1.4, 1.6, 0.5, 0.6, 0.6, 0.5])
for header, col in zip(
    ["**Company**", "**Position**", "**Date**", "**Status**", "", "", "", ""],
    cols,
):
    col.markdown(header)

st.markdown("---")

# ── Rows ──────────────────────────────────────────────────────────────────────

for sub in filtered:
    sub_id, company, position, date, status = sub[0], sub[1], sub[2], sub[3], sub[4]
    date_str = date.split("T")[0]
    badge = STATUS_BADGE.get(status, "🔵")

    row = st.columns([2, 2, 1.4, 1.6, 0.5, 0.6, 0.6, 0.5])
    row[0].markdown(company)
    row[1].markdown(position)
    row[2].markdown(date_str)
    row[3].markdown(f"{badge} {status}")

    # ✏️ View / Edit
    if row[4].button("✏️", key=f"ms_edit_{sub_id}", help="View & Edit"):
        st.query_params["id"] = str(sub_id)
        st.switch_page("pages/submission_detail.py")

    # ⬇️ CV PDF
    if row[5].button("📄CV", key=f"ms_cv_{sub_id}", help="Download CV PDF"):
        with st.spinner(f"Preparing CV for {company}…"):
            try:
                cached_pdf, tmpl = get_cv_pdf_bytes(sub_id)
                if not cached_pdf:
                    cached_pdf = compile_cv_for_submission(sub_id, tmpl)
                st.download_button(
                    label="⬇️ CV PDF",
                    data=cached_pdf,
                    file_name=f"CV_{company}_{position}.pdf",
                    mime="application/pdf",
                    key=f"ms_cv_dl_{sub_id}",
                )
            except Exception as exc:
                st.error(f"CV generation failed: {exc}")

    # ⬇️ Cover Letter PDF
    if row[6].button("📄CL", key=f"ms_cl_{sub_id}", help="Download Cover Letter PDF"):
        with st.spinner(f"Preparing cover letter for {company}…"):
            try:
                cl_path, temp_dir = generate_cl_pdf_from_submission(sub_id)
                if cl_path and os.path.exists(cl_path):
                    with open(cl_path, "rb") as f:
                        cl_data = f.read()
                    cleanup_temp_files(temp_dir)
                    st.download_button(
                        label="⬇️ Cover Letter PDF",
                        data=cl_data,
                        file_name=f"CoverLetter_{company}_{position}.pdf",
                        mime="application/pdf",
                        key=f"ms_cl_dl_{sub_id}",
                    )
                else:
                    st.error("Could not generate cover letter PDF.")
            except Exception as exc:
                st.error(f"Cover letter generation failed: {exc}")

    # 🗑️ Delete
    if row[7].button("🗑️", key=f"ms_del_{sub_id}", help="Delete"):
        st.session_state.ms_confirm_del = sub_id
        st.rerun()

    # Inline delete confirmation
    if st.session_state.ms_confirm_del == sub_id:
        with st.container():
            st.warning(f"Delete **{company} — {position}**? This cannot be undone.")
            c1, c2 = st.columns([1, 5])
            if c1.button("Yes, delete", key=f"ms_yes_{sub_id}", type="primary"):
                delete_submission(sub_id)
                st.session_state.ms_confirm_del = None
                st.rerun()
            if c2.button("Cancel", key=f"ms_no_{sub_id}"):
                st.session_state.ms_confirm_del = None
                st.rerun()

# ── Navigation ────────────────────────────────────────────────────────────────

st.markdown("---")
n1, n2, n3 = st.columns(3)
with n1:
    st.page_link("home.py", label="⬅️ Back to Home", icon="🏠")
with n2:
    st.page_link("pages/portfolio.py", label="Portfolio", icon="📁")
with n3:
    st.page_link("pages/new_submission.py", label="New Application", icon="📝")
```

- [ ] **Step 2: Commit**

```bash
git add pages/my_submissions.py
git commit -m "feat: rebuild my_submissions with status filter, per-row inline downloads, remove dropdown"
```

---

## Task 7: Update `pages/home.py` — Remove HTML submissions rendering

**Files:**
- Modify: `pages/home.py`

Replace the `render_submissions_html` iframe with a clean submissions table.

- [ ] **Step 1: Update imports at top of home.py**

Remove:
```python
from support.html_builder import render_submissions_html
```

Add (or leave if already present):
```python
from support.submission_manager import get_all_submissions_with_metadata
```

Also remove the existing:
```python
from support.submission_manager import get_all_submissions
```

- [ ] **Step 2: Replace the "Recent Submissions" section**

Find and replace the block:
```python
# Recent Submissions
st.subheader("📬 Recent Applications")

try:
    submissions = get_all_submissions()
    
    if not submissions:
        ...
    else:
        html_content = render_submissions_html(submissions[:5])
        st.components.v1.html(html_content, height=300, scrolling=True)
        
except Exception as e:
    st.info("No applications yet. Start by configuring your settings and creating your portfolio!")
    print(f"Error loading submissions: {e}")
```

Replace with:
```python
# Recent Submissions
st.subheader("📬 Recent Applications")

STATUS_BADGE = {
    "Applied": "🔵", "Interviewing": "🟡", "Technical Assessment": "🟠",
    "Offer": "🟢", "Rejected": "🔴", "Withdrawn": "⚪",
}

try:
    recent = get_all_submissions_with_metadata()[:5]
    if not recent:
        st.info("No applications yet. Create your first tailored application!")
    else:
        cols = st.columns([2, 2, 1.4, 1.6, 1])
        for h, c in zip(["**Company**", "**Position**", "**Date**", "**Status**", ""], cols):
            c.markdown(h)
        for sub in recent:
            sub_id, company, position, date, status = sub[0], sub[1], sub[2], sub[3], sub[4]
            badge = STATUS_BADGE.get(status, "🔵")
            row = st.columns([2, 2, 1.4, 1.6, 1])
            row[0].markdown(company)
            row[1].markdown(position)
            row[2].markdown(date.split("T")[0])
            row[3].markdown(f"{badge} {status}")
            if row[4].button("✏️", key=f"home_edit_{sub_id}", help="View"):
                st.query_params["id"] = str(sub_id)
                st.switch_page("pages/submission_detail.py")
        st.page_link("pages/my_submissions.py", label="View all submissions →")
except Exception as e:
    st.info("No applications yet.")
    print(f"Error loading submissions: {e}")
```

- [ ] **Step 3: Update the Stats section to use the new function**

Find:
```python
        submission_count = len(get_all_submissions()) if 'submissions' in locals() else 0
```

Replace with:
```python
        submission_count = len(get_all_submissions_with_metadata())
```

- [ ] **Step 4: Commit**

```bash
git add pages/home.py
git commit -m "feat: replace HTML iframe submissions preview with plain table on home page"
```

---

## Task 8: Clean up `support/html_builder.py`

**Files:**
- Modify: `support/html_builder.py`

Delete three functions/classes that are no longer called anywhere: `CVBuilder`, `render_editable_cv`, `render_submissions_html`. Keep `CoverLetterBuilder`, `render_editable_cover_letter`, and `inject_iframe_reset` — these are still used by the cover letter HTML path.

- [ ] **Step 1: Verify no remaining callers before deleting**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
grep -rn "render_editable_cv\|render_submissions_html\|CVBuilder" \
  pages/ support/ home.py
```

Expected: **zero results**. (`render_editable_cover_letter` and `inject_iframe_reset` should still appear in `new_submission.py` — that is correct.) If any remain, fix them in that file before continuing.

- [ ] **Step 2: Check what line CVBuilder starts and CoverLetterBuilder starts**

```bash
grep -n "^class CVBuilder\|^class CoverLetterBuilder\|^def render_editable_cv\|^def render_editable_cover_letter\|^def inject_iframe_reset\|^def render_submissions_html" \
  support/html_builder.py
```

Note the line numbers, then delete everything from `class CVBuilder` up to (but not including) `class CoverLetterBuilder`. Also delete `render_editable_cv`, `render_editable_cover_letter`, `inject_iframe_reset`, `render_submissions_html` function bodies.

- [ ] **Step 3: Remove the now-unused imports at the top of html_builder.py**

Check the top of html_builder.py:
```bash
head -10 support/html_builder.py
```

Remove `import base64` and `import streamlit as st` if they are only used by the deleted code (CoverLetterBuilder still uses `os` and the template imports — check before removing).

- [ ] **Step 4: Commit**

```bash
git add support/html_builder.py
git commit -m "chore: remove CVBuilder, render_editable_cv, inject_iframe_reset, render_submissions_html from html_builder"
```

---

## Task 9: Docker Rebuild & Smoke Test

**Files:** None — verification only.

- [ ] **Step 1: Rebuild the Docker image**

```bash
cd /Users/rohan.dcosta/Documents/personal/tailor-your-document
docker compose down && docker compose up --build -d
```

Wait for the container to start (watch logs):
```bash
docker compose logs -f --tail=50
```

Expected last line: `You can now view your Streamlit app in your browser.`

- [ ] **Step 2: Smoke test — Home page**

Open `http://localhost:8501`. Verify:
- Recent Applications section shows a clean table (not an iframe)
- No Python errors in terminal logs

- [ ] **Step 3: Smoke test — Resume Library**

Navigate to **📚 Resume Library**. Verify:
- Template selector present
- Form renders with all sections (Personal Info, Summary, Experience, Education, Projects, Skills)
- Fill in minimal data, click **Compile & Preview** — PDF renders via image tiles
- Save gives a toast; reload page shows it in the selectbox

- [ ] **Step 4: Smoke test — New Submission**

Navigate to **New Submission**. Paste a short job description. Click **Generate Tailored Documents**. Verify:
- **CV Editor & Preview** tab shows the structured form on the left
- Cover Letter tab still shows HTML iframe
- Click **Compile CV Preview** — PDF renders on the right
- Save to Database completes without error

- [ ] **Step 5: Smoke test — My Submissions**

Navigate to **My Submissions**. Verify:
- Status filter dropdown works
- Search box filters rows
- ✏️ button navigates to detail page
- 📄CV button triggers compile + download button appears
- 📄CL button generates cover letter PDF

- [ ] **Step 6: Smoke test — Submission Detail**

Open a submission. Verify:
- Status/notes/URL editable; Save Details works
- CV tab: form pre-filled with stored CV data
- CV tab: if cached PDF exists it renders immediately; if not, compile button appears
- Compile & Save CV updates the preview
- Save to Library saves to Resume Library (verify by going to Resume Library page)
- Cover Letter tab: PDF renders

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "chore: consolidation complete — LaTeX-only CV pipeline, unified editor, improved submissions UX"
```
