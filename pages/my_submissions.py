import streamlit as st
from support.submission_manager import (
    get_all_submissions_with_metadata,
    delete_submission,
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

# Track which row is pending deletion confirmation
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None

# --- Submissions table ---
st.markdown("---")
header = st.columns([2, 2, 1.8, 1.8, 0.5, 0.5])
header[0].markdown("**Company**")
header[1].markdown("**Position**")
header[2].markdown("**Date**")
header[3].markdown("**Status**")
header[4].markdown("")
header[5].markdown("")

for sub in submissions:
    sub_id, company, position, date, status = sub[0], sub[1], sub[2], sub[3], sub[4]
    date_str = date.split("T")[0]
    badge = STATUS_BADGE.get(status, "🔵")

    row = st.columns([2, 2, 1.8, 1.8, 0.5, 0.5])
    row[0].markdown(company)
    row[1].markdown(position)
    row[2].markdown(date_str)
    row[3].markdown(f"{badge} {status}")

    if row[4].button("✏️", key=f"edit_{sub_id}", help="Edit submission"):
        st.query_params["id"] = str(sub_id)
        st.switch_page("pages/submission_detail.py")

    if row[5].button("🗑️", key=f"del_{sub_id}", help="Delete submission"):
        st.session_state.confirm_delete_id = sub_id
        st.rerun()

    # Inline confirmation row
    if st.session_state.confirm_delete_id == sub_id:
        with st.container():
            st.warning(f"Delete **{company} — {position}**? This cannot be undone.")
            c1, c2 = st.columns([1, 5])
            if c1.button("Yes, delete", key=f"confirm_yes_{sub_id}", type="primary"):
                delete_submission(sub_id)
                st.session_state.confirm_delete_id = None
                st.rerun()
            if c2.button("Cancel", key=f"confirm_no_{sub_id}"):
                st.session_state.confirm_delete_id = None
                st.rerun()

st.markdown("---")

# --- Download section ---
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
