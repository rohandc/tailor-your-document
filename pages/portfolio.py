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
            st.rerun()
else:
    st.info("No portfolios yet. Upload a CV below to create your first portfolio.")

st.markdown("---")

# ──────────────────────────────────────────────
# REST OF PAGE
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
