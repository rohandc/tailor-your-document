# pages/submission_detail.py
import os
from pathlib import Path

import streamlit as st

from support.cv_editor_component import render_cv_editor
from support.latex_resume_manager import save_resume
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
