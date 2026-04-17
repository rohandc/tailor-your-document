import os

import streamlit as st

from support.submission_manager import (
    get_submission_metadata,
    update_submission_metadata,
    delete_submission,
    generate_pdf_from_submission,
    cleanup_temp_files,
)
from support.pdf_preview import show_pdf_pages

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

# --- Document Preview ---
st.markdown("---")
st.subheader("📄 Document Preview")

_cache_key = f"preview_pdfs_{submission_id}"

def _load_preview():
    with st.spinner("Generating preview…"):
        cv_path, cl_path, temp_dir = generate_pdf_from_submission(submission_id)
        result = {"cv": None, "cl": None, "temp_dir": temp_dir}
        if cv_path and os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                result["cv"] = f.read()
        if cl_path and os.path.exists(cl_path):
            with open(cl_path, "rb") as f:
                result["cl"] = f.read()
        cleanup_temp_files(temp_dir)
        return result

if _cache_key not in st.session_state:
    st.session_state[_cache_key] = _load_preview()

_preview = st.session_state[_cache_key]

if st.button("🔄 Refresh Preview"):
    st.session_state[_cache_key] = _load_preview()
    st.rerun()

tab_cv, tab_cl = st.tabs(["📋 CV", "✉️ Cover Letter"])

with tab_cv:
    if _preview["cv"]:
        show_pdf_pages(_preview["cv"])
        st.download_button("⬇️ Download CV PDF", data=_preview["cv"],
                           file_name=f"CV_{company}_{position}.pdf",
                           mime="application/pdf")
    else:
        st.warning("Could not generate CV preview for this submission.")

with tab_cl:
    if _preview["cl"]:
        show_pdf_pages(_preview["cl"])
        st.download_button("⬇️ Download Cover Letter PDF", data=_preview["cl"],
                           file_name=f"CoverLetter_{company}_{position}.pdf",
                           mime="application/pdf")
    else:
        st.warning("Could not generate Cover Letter preview for this submission.")
