import copy
import os
import pickle
import time
import streamlit as st
from support.extractor import InformationExtractor
from support.load_models import load_openAI_model, load_gemini_model
from support.html_builder import render_editable_cover_letter, inject_iframe_reset
from pathlib import Path
from support.cv_editor_component import render_cv_editor
from support.latex_builder import render_latex, compile_latex
from support.pdf_preview import show_pdf_pages
from support.latex_resume_manager import list_resumes, load_resume
from support.file_manager import FileManager
from support.settings import TESTING
from support.portfolio_manager import (
    list_portfolios,
    load_portfolio,
    get_active_portfolio_name,
    migrate_legacy_portfolio,
)


def _apply_accepted_rewrites(cv_object, accepted_rewrites: list):
    """Return a deep copy of cv_object with accepted rewrites applied."""
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

# Session state for job scraping and keywords
for _key, _default in [
    ("scraped_job_url", None),
    ("extracted_keywords", {}),
    ("removed_keywords", set()),
    ("custom_keywords", []),
    ("keyword_suggestions", {}),
    ("accepted_rewrites", []),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

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

paste_tab, scrape_tab = st.tabs(["✍️ Paste Manually", "🔗 Scrape from URL"])

with scrape_tab:
    scrape_url = st.text_input("Job posting URL", placeholder="https://company.com/careers/role-123")
    if st.button("🔍 Fetch Job"):
        if not scrape_url.strip():
            st.error("Please enter a URL.")
        else:
            try:
                from support.job_scraper import scrape_job_description
                with st.spinner("Fetching job description..."):
                    scraped_text = scrape_job_description(scrape_url.strip())
                if scraped_text and len(scraped_text) >= 200:
                    st.session_state.scraped_jd_text = scraped_text
                    st.session_state.scraped_job_url = scrape_url.strip()
                    st.toast("✅ Job description fetched!")
                    st.rerun()
                else:
                    st.error("❌ Could not extract enough text from that URL. Try pasting manually.")
            except ImportError:
                st.error("❌ Job scraper dependencies not installed. Try pasting manually.")

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

# ── Keywords Panel ────────────────────────────────────────────────────────────
if job_description.strip():
    st.markdown("---")
    st.subheader("🔑 Keywords")

    if st.button("🔑 Extract Keywords from Job Description"):
        with st.spinner("Extracting keywords..."):
            try:
                from support.job_scraper import extract_keywords
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
            except ImportError:
                st.error("❌ Job scraper dependencies not installed.")

    if st.session_state.extracted_keywords or st.session_state.custom_keywords:
        kw_col, sug_col = st.columns([1, 1.5])

        with kw_col:
            st.markdown("**Keywords**")

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

            if st.session_state.custom_keywords:
                st.markdown("*Custom*")
                for kw in list(st.session_state.custom_keywords):
                    c1, c2 = st.columns([0.85, 0.15])
                    c1.markdown(f"• {kw}")
                    if c2.button("❌", key=f"rm_custom_{kw}"):
                        st.session_state.custom_keywords.remove(kw)
                        st.session_state.keyword_suggestions.pop(kw, None)
                        st.rerun()

            new_kw = st.text_input("Add keyword", key="custom_kw_input",
                                    placeholder="e.g. Kubernetes")
            if st.button("➕ Add"):
                kw = new_kw.strip()
                if kw and kw not in st.session_state.custom_keywords:
                    st.session_state.custom_keywords.append(kw)
                    st.rerun()

        with sug_col:
            st.markdown("**Suggestions**")

            all_active = [
                k for cat_kws in st.session_state.extracted_keywords.values()
                for k in cat_kws if k not in st.session_state.removed_keywords
            ] + st.session_state.custom_keywords

            if st.button("💡 Generate Suggestions"):
                try:
                    from support.job_scraper import generate_keyword_suggestions
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
                except ImportError:
                    st.error("❌ Job scraper dependencies not installed.")

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

                # Apply any accepted keyword rewrites before generation
                working_cv = _apply_accepted_rewrites(
                    st.session_state.structured_cv,
                    st.session_state.get("accepted_rewrites", []),
                )
                st.session_state.information_extractor.structured_cv = working_cv

                st.info(f"🔍 Debug Info: Using {selected_model.upper()} model")
                st.info(f"🔍 Debug Info: Structured CV loaded: {working_cv is not None}")

                if not TESTING:
                    st.info("🔄 Generating new CV...")
                    new_cv = st.session_state.information_extractor.create_new_cv(
                        structured_curriculum=working_cv,
                        job_description=job_description,
                    )
                    st.info("🔄 Generating cover letter...")
                    cover_letter = st.session_state.information_extractor.create_new_cover_letter(
                        structured_curriculum=working_cv,
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

    tab1, tab2 = st.tabs(["📄 CV Editor & Preview", "✉️ Cover Letter Editor & Preview"])

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

# ── PDF Download handling ─────────────────────────────────────────────────────
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
