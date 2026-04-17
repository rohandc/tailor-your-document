import streamlit as st
from support.submission_manager import get_all_submissions
from support.html_builder import render_submissions_html
from support.file_manager import FileManager
from support.config_manager import ConfigManager
import os

st.set_page_config(page_title="AI CV Builder - Home", layout="wide")

# Initialize managers
file_manager = FileManager()
config_manager = ConfigManager()

# Auto-load saved configuration if not in session state
if "selected_model" not in st.session_state:
    saved_config = config_manager.load_config()
    if saved_config:
        st.session_state.selected_model = saved_config.get(
            "selected_model", "openai"
        )
        st.session_state.openai_api_key = saved_config.get(
            "openai_api_key", ""
        )
        st.session_state.gemini_api_key = saved_config.get(
            "gemini_api_key", ""
        )
        
        # Set environment variables
        if st.session_state.openai_api_key:
            os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
        if st.session_state.gemini_api_key:
            os.environ["GOOGLE_API_KEY"] = st.session_state.gemini_api_key

# Check portfolio status
has_portfolio = file_manager.has_portfolio_data()

# Title and Description
st.markdown(
    "<h1 style='text-align: center;'>🚀 AI CV Builder</h1>", 
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align: center; font-size:18px;'>Your smart assistant for creating, editing, and customizing professional CVs and cover letters.</p>", 
    unsafe_allow_html=True
)

# Portfolio Status Banner
if has_portfolio:
    st.success(
        "✅ Your portfolio is ready! You can create tailored applications or edit your existing portfolio."
    )
else:
    st.warning(
        "⚠️ No portfolio found. Start by uploading your CV to create your portfolio."
    )

# Configuration Status
if config_manager.has_config():
    st.info(
        "⚙️ Your configuration has been automatically loaded from previous sessions."
    )

# Quick Action Buttons
st.subheader("🚀 Quick Actions")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.page_link("pages/manage_settings.py", label="Manage Settings", icon="⚙️")
    st.markdown("*Configure API keys and model preferences*")

with col2:
    if has_portfolio:
        st.page_link("pages/portfolio.py", label="Edit Portfolio", icon="✏️")
        st.markdown("*Modify your existing CV data*")
    else:
        st.page_link("pages/portfolio.py", label="Create Portfolio", icon="📁")
        st.markdown("*Upload and process your CV*")

with col3:
    if has_portfolio:
        st.page_link("pages/new_submission.py", label="New Application", icon="📝")
        st.markdown("*Create tailored CV and cover letter*")
    else:
        st.page_link("pages/new_submission.py", label="New Submission", icon="📝")
        st.markdown("*Create tailored CVs and cover letters*")

with col4:
    st.page_link("pages/my_submissions.py", label="My Submissions", icon="📬")
    st.markdown("*View your application history*")

with col5:
    st.page_link("pages/latex_resume.py", label="LaTeX Resume", icon="📄")
    st.markdown("*Build a professional two-column PDF resume*")

st.markdown("---")

# Workflow Guide
st.subheader("📋 How It Works")
workflow_col1, workflow_col2 = st.columns(2)

with workflow_col1:
    st.markdown("""
    **1️⃣ Setup & Configuration**
    - Configure your OpenAI or Gemini API keys
    - Choose your preferred AI model
    - Settings are automatically saved and loaded
    
    **2️⃣ Portfolio Management**
    - Upload your existing CV
    - AI extracts and structures your information
    - Edit and refine your experiences, skills, and education
    - Save your portfolio for future use
    """)

with workflow_col2:
    st.markdown("""
    **3️⃣ Job Application**
    - Paste a job description
    - AI generates tailored CV and cover letter
    - Edit both documents to your preference
    - Download PDFs or save to database
    
    **4️⃣ Track Applications**
    - View all your submissions
    - Download previous applications
    - Monitor your job search progress
    """)

st.markdown("---")

# Recent Submissions
st.subheader("📬 Recent Applications")

try:
    submissions = get_all_submissions()
    
    if not submissions:
        if has_portfolio:
            st.info(
                "No applications yet. Start creating tailored applications for specific jobs!"
            )
        else:
            st.info(
                "No applications yet. Start by configuring your settings and creating your portfolio!"
            )
    else:
        html_content = render_submissions_html(submissions[:5])
        st.components.v1.html(html_content, height=300, scrolling=True)
        
except Exception as e:
    st.info("No applications yet. Start by configuring your settings and creating your portfolio!")
    print(f"Error loading submissions: {e}")

# Stats Section
st.markdown("---")
st.subheader("📊 Your Stats")
col1, col2, col3 = st.columns(3)

with col1:
    try:
        submission_count = len(get_all_submissions()) if 'submissions' in locals() else 0
        st.metric("Total Applications", submission_count)
    except:
        st.metric("Total Applications", 0)

with col2:
    last_template = st.session_state.get("template_id", "Not set")
    st.metric("Last Used Template", last_template)

with col3:
    if has_portfolio:
        st.metric("Portfolio Status", "✅ Ready")
    else:
        st.metric("Portfolio Status", "⚠️ Not Created")

# Getting Started Section
st.markdown("---")
st.subheader("🎯 Getting Started")

if not has_portfolio:
    st.warning(
        "**First time here?** Start by configuring your API keys and creating your portfolio."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/manage_settings.py", label="Configure API Keys", icon="🔑")
    with col2:
        st.page_link("pages/portfolio.py", label="Create Portfolio", icon="📁")
else:
    st.success(
        "**Great!** Your portfolio is ready. You can now create tailored applications for specific jobs."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/new_submission.py", label="Create New Application", icon="📝")
    with col2:
        st.page_link("pages/portfolio.py", label="Edit Portfolio", icon="✏️")
