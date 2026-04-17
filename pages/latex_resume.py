from pathlib import Path

import pandas as pd
import streamlit as st

from support.pdf_preview import show_pdf_pages
from support.supportClasses import (
    Experience,
    EducationExperience,
    FinalCurriculum,
    Personality,
)
from support.latex_builder import render_latex, compile_latex
from support.latex_resume_manager import (
    save_resume,
    load_resume,
    list_resumes,
    delete_resume,
)

st.set_page_config(page_title="LaTeX Resume", layout="wide")
st.title("📄 LaTeX Resume")
st.markdown("Build and preview a professional two-column LaTeX resume. Load a saved resume or start from your active portfolio.")

# ── Saved resumes (load / delete) ─────────────────────────────────────────────

saved = list_resumes()

if saved:
    load_col, del_col = st.columns([4, 1])
    with load_col:
        options = ["— Select a saved resume —"] + [
            f"{e['name']}  (modified {e['last_modified'].strftime('%Y-%m-%d %H:%M')})"
            for e in saved
        ]
        chosen = st.selectbox("📂 Load Saved Resume", options=options, key="load_resume_selector")
    with del_col:
        st.write("")  # spacer to align button with selectbox
        st.write("")
        if chosen != options[0]:
            chosen_name = saved[options.index(chosen) - 1]["name"]
            if st.button("🗑️ Delete", key="delete_saved_resume"):
                delete_resume(chosen_name)
                st.session_state.pop("latex_loaded_cv", None)
                st.toast(f"Deleted '{chosen_name}'")
                st.rerun()

    if chosen != options[0]:
        chosen_name = saved[options.index(chosen) - 1]["name"]
        if st.button(f"📥 Load '{chosen_name}'", type="primary", key="load_saved_btn"):
            loaded = load_resume(chosen_name)
            if loaded:
                st.session_state["latex_loaded_cv"] = loaded
                st.session_state["latex_loaded_name"] = chosen_name
                st.toast(f"Loaded '{chosen_name}'")
                st.rerun()

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
    help="Choose a template. Edit .tex files in support/latex_templates/ — changes apply on next compile.",
)

# ── Pre-populate: loaded saved resume takes priority, else active portfolio ───

_cv: FinalCurriculum | None = (
    st.session_state.get("latex_loaded_cv")
    or st.session_state.get("final_cv_content")
)

if st.session_state.get("latex_loaded_name"):
    st.info(f"✏️ Editing saved resume: **{st.session_state['latex_loaded_name']}**")


def _cv_val(attr, default=""):
    if _cv is None:
        return default
    return getattr(_cv, attr, default) or default


def _personality_val(attr, default=""):
    if _cv is None or _cv.personality is None:
        return default
    return getattr(_cv.personality, attr, default) or default


# ── Layout: form on left, preview on right ────────────────────────────────────

form_col, preview_col = st.columns([1, 1])

with form_col:
    with st.form("latex_cv_form"):
        # Personal Info
        st.subheader("Personal Info")
        fi_c1, fi_c2 = st.columns(2)
        with fi_c1:
            first_name = st.text_input("First Name", value=_personality_val("name"))
            job_title_input = st.text_input("Job Title", value=_cv_val("job_title") or _personality_val("job_title"))
            email_input = st.text_input("Email", value=_personality_val("e_mail"))
        with fi_c2:
            last_name = st.text_input("Last Name", value=_personality_val("surname"))
            phone_input = st.text_input("Phone", value=_personality_val("telephone"))
            linkedin_input = st.text_input("LinkedIn URL", value=_personality_val("linkedin_link"))

        address_input = st.text_input("Address", value=_personality_val("address"))

        st.divider()

        # Summary
        st.subheader("Summary")
        summary_input = st.text_area(
            "Professional Summary (2-3 sentences)",
            value=_cv_val("summary"),
            height=90,
        )

        st.divider()

        # Work Experience
        st.subheader("Work Experience")
        existing_experiences: list = list(_cv.experiences or []) if _cv else []
        # Ensure at least one blank entry
        if not existing_experiences:
            existing_experiences = [Experience()]

        exp_data = []
        for i, exp in enumerate(existing_experiences):
            with st.expander(f"Experience {i + 1}: {exp.title or 'New'}", expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    t = st.text_input("Title", value=exp.title or "", key=f"exp_title_{i}")
                    sd = st.text_input("Start Date", value=exp.start_date or "", key=f"exp_sd_{i}")
                with ec2:
                    c = st.text_input("Company", value=exp.company or "", key=f"exp_company_{i}")
                    ed = st.text_input("End Date", value=exp.end_date or "", key=f"exp_ed_{i}")
                desc = st.text_area(
                    "Bullets (one per line, start with •, -, or *)",
                    value=exp.description or "",
                    height=100,
                    key=f"exp_desc_{i}",
                )
                exp_data.append((t, c, sd, ed, desc))

        st.divider()

        # Education
        st.subheader("Education")
        existing_education: list = list(_cv.education or []) if _cv else []
        if not existing_education:
            existing_education = [EducationExperience()]

        edu_data = []
        for i, edu in enumerate(existing_education):
            with st.expander(f"Education {i + 1}: {edu.title or 'New'}", expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    t = st.text_input("Degree / Title", value=edu.title or "", key=f"edu_title_{i}")
                    sd = st.text_input("Start Date", value=edu.start_date or "", key=f"edu_sd_{i}")
                with ec2:
                    s = st.text_input("School / University", value=edu.school_name or "", key=f"edu_school_{i}")
                    ed = st.text_input("End Date", value=edu.end_date or "", key=f"edu_ed_{i}")
                desc = st.text_area(
                    "Description",
                    value=edu.description or "",
                    height=80,
                    key=f"edu_desc_{i}",
                )
                edu_data.append((t, s, sd, ed, desc))

        st.divider()

        # Projects
        st.subheader("Projects")
        existing_projects: list = list(_cv.projects or []) if _cv else []

        proj_data = []
        for i, proj in enumerate(existing_projects):
            with st.expander(f"Project {i + 1}: {proj.title or 'New'}", expanded=(i == 0)):
                pc1, pc2 = st.columns(2)
                with pc1:
                    t = st.text_input("Project Title", value=proj.title or "", key=f"proj_title_{i}")
                    sd = st.text_input("Start Date", value=proj.start_date or "", key=f"proj_sd_{i}")
                with pc2:
                    c = st.text_input("Organisation / Context", value=proj.company or "", key=f"proj_company_{i}")
                    ed = st.text_input("End Date", value=proj.end_date or "", key=f"proj_ed_{i}")
                desc = st.text_area(
                    "Bullets",
                    value=proj.description or "",
                    height=100,
                    key=f"proj_desc_{i}",
                )
                proj_data.append((t, c, sd, ed, desc))

        st.divider()

        # Skills
        st.subheader("Skills")

        _hard_seed = pd.DataFrame(
            {"Skill": pd.Series((_cv.hard_skills or []) if _cv else [], dtype="string")}
        )
        _soft_seed = pd.DataFrame(
            {"Skill": pd.Series((_cv.soft_skills or []) if _cv else [], dtype="string")}
        )

        with st.expander("🛠️ Technical Skills", expanded=True):
            hard_skills_df = st.data_editor(
                _hard_seed,
                num_rows="dynamic",
                use_container_width=True,
                key="hard_skills_editor",
                column_config={"Skill": st.column_config.TextColumn("Skill", required=False)},
            )

        with st.expander("🤝 Soft Skills", expanded=False):
            soft_skills_df = st.data_editor(
                _soft_seed,
                num_rows="dynamic",
                use_container_width=True,
                key="soft_skills_editor",
                column_config={"Skill": st.column_config.TextColumn("Skill", required=False)},
            )

        st.divider()

        submitted = st.form_submit_button("Compile & Preview", type="primary")

# ── Form submission logic ─────────────────────────────────────────────────────

if submitted:
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
        Experience(title=t or None, company=c or None, start_date=sd or None, end_date=ed or None, description=desc or None)
        for t, c, sd, ed, desc in exp_data
        if any([t, c, sd, ed, desc])
    ]

    education = [
        EducationExperience(title=t or None, school_name=s or None, start_date=sd or None, end_date=ed or None, description=desc or None)
        for t, s, sd, ed, desc in edu_data
        if any([t, s, sd, ed, desc])
    ]

    projects = [
        Experience(title=t or None, company=c or None, start_date=sd or None, end_date=ed or None, description=desc or None)
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

    st.session_state["latex_form_data"] = {
        "first_name": first_name,
        "last_name": last_name,
        "job_title": job_title_input,
    }
    # Cache the built FinalCurriculum so the user can save it below
    st.session_state["latex_last_built_cv"] = final_cv

    try:
        latex_source = render_latex(final_cv, template_name=selected_template)
        st.session_state["latex_source"] = latex_source
        pdf_bytes = compile_latex(latex_source)
        st.session_state["latex_pdf_bytes"] = pdf_bytes
    except RuntimeError as exc:
        err_msg = str(exc)
        if "not available" in err_msg or "not found" in err_msg:
            st.error("LaTeX compiler not available in this environment. pdflatex must be installed (included in the Docker image).")
        else:
            st.error(f"LaTeX compilation error:\n\n```\n{err_msg}\n```")
        st.session_state["latex_pdf_bytes"] = None

# ── Save resume (outside the form so it can act on the last build) ───────────

_cv_to_save = st.session_state.get("latex_last_built_cv") or _cv
if _cv_to_save is not None:
    st.divider()
    st.subheader("💾 Save Resume")
    if st.session_state.get("latex_last_built_cv") is None:
        st.caption("⚠️ Click **Compile & Preview** first to capture your latest edits before saving.")
    save_col1, save_col2 = st.columns([3, 1])
    with save_col1:
        default_name = st.session_state.get("latex_loaded_name", "")
        resume_name = st.text_input(
            "Resume Name",
            value=default_name,
            placeholder="e.g. Senior Backend Engineer – Acme",
            key="latex_save_name",
            label_visibility="collapsed",
        )
    with save_col2:
        if st.button("💾 Save", type="primary", key="save_resume_btn", use_container_width=True):
            if not resume_name or not resume_name.strip():
                st.warning("Please enter a name before saving.")
            else:
                try:
                    save_resume(resume_name.strip(), _cv_to_save)
                    st.session_state["latex_loaded_name"] = resume_name.strip()
                    st.toast(f"Saved '{resume_name.strip()}'")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save: {exc}")

# ── Preview panel ─────────────────────────────────────────────────────────────

with preview_col:
    st.subheader("Preview")
    pdf_bytes: bytes | None = st.session_state.get("latex_pdf_bytes")
    latex_source: str | None = st.session_state.get("latex_source")

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
        st.info("Fill in the form on the left and click **Compile & Preview** to generate your resume.")
