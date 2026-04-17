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
