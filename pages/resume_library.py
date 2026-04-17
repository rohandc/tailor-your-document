# pages/resume_library.py
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
from support.submission_manager import (
    compile_cv_for_submission,
    get_all_submissions_with_metadata,
    get_cv_pdf_bytes,
)
from support.supportClasses import FinalCurriculum

st.set_page_config(page_title="Resume Library", layout="wide")
st.title("📚 Resume Library")
st.markdown(
    "Save and reuse named LaTeX resume drafts, and browse your past job submissions."
)

STATUS_BADGE = {
    "Applied": "🔵", "Interviewing": "🟡", "Technical Assessment": "🟠",
    "Offer": "🟢", "Rejected": "🔴", "Withdrawn": "⚪",
}

tab_saved, tab_past = st.tabs(["💾 Saved Resumes", "📬 Past Submissions"])

# ══════════════════════ TAB 1: SAVED RESUMES ══════════════════════════════════

with tab_saved:
    # ── Load / Delete saved resumes ──────────────────────────────────────────
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

    # ── Template selector ────────────────────────────────────────────────────
    _templates_dir = Path(__file__).parent.parent / "support" / "latex_templates"
    _available = sorted(p.stem for p in _templates_dir.glob("*.tex"))

    if not _available:
        st.error("No LaTeX templates found in `support/latex_templates/`.")
        st.stop()

    selected_template = st.selectbox(
        "🎨 Template",
        options=_available,
        index=_available.index("rohans_format") if "rohans_format" in _available else 0,
        help="Edit .tex files in support/latex_templates/ — changes apply on next compile.",
        key="rl_template",
    )

    # ── Initial CV (loaded resume or active portfolio) ───────────────────────
    _initial_cv: FinalCurriculum | None = (
        st.session_state.get("rl_loaded_cv")
        or st.session_state.get("final_cv_content")
    )

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

    # ── Save resume ──────────────────────────────────────────────────────────
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

    # ── Preview panel ────────────────────────────────────────────────────────
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

# ══════════════════════ TAB 2: PAST SUBMISSIONS ═══════════════════════════════

with tab_past:
    submissions = get_all_submissions_with_metadata()
    # row: (id, company, position, date, status, notes, job_url)

    if not submissions:
        st.info("No past submissions yet. Create one from **New Application**.")
        st.page_link("pages/new_submission.py", label="➕ New Application", icon="📝")
    else:
        # Selector
        ps_options = [
            f"{s[1]} — {s[2]}  ({s[3].split('T')[0]})  {STATUS_BADGE.get(s[4], '🔵')} {s[4]}"
            for s in submissions
        ]
        selected_label = st.selectbox(
            "📂 Select a past submission",
            options=ps_options,
            key="ps_selector",
        )
        selected_idx = ps_options.index(selected_label)
        sub = submissions[selected_idx]
        sub_id, company, position, date, status, notes, job_url = sub

        # Header card
        meta1, meta2, meta3 = st.columns(3)
        with meta1:
            st.metric("Company", company)
        with meta2:
            st.metric("Position", position)
        with meta3:
            st.metric("Status", f"{STATUS_BADGE.get(status, '🔵')} {status}")

        if job_url:
            st.markdown(f"🔗 [Job Posting]({job_url})")
        if notes:
            with st.expander("📝 Notes"):
                st.write(notes)

        st.divider()

        # Actions row
        act1, act2, act3 = st.columns([1, 1, 2])
        with act1:
            if st.button("✏️ Edit in Detail", key=f"ps_edit_{sub_id}"):
                st.query_params["id"] = str(sub_id)
                st.switch_page("pages/submission_detail.py")
        with act2:
            if st.button("🔄 Re-compile CV", key=f"ps_recompile_{sub_id}"):
                _, tmpl = get_cv_pdf_bytes(sub_id)
                try:
                    with st.spinner("Compiling…"):
                        compile_cv_for_submission(sub_id, tmpl)
                    st.session_state.pop(f"ps_cv_pdf_{sub_id}", None)
                    st.toast("CV recompiled.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Compile failed: {exc}")

        # CV preview
        st.markdown("### 📋 CV Preview")
        cache_key = f"ps_cv_pdf_{sub_id}"
        if cache_key not in st.session_state:
            cached_pdf, tmpl = get_cv_pdf_bytes(sub_id)
            if cached_pdf:
                st.session_state[cache_key] = cached_pdf
            else:
                # Compile on first view
                try:
                    with st.spinner("Compiling CV…"):
                        st.session_state[cache_key] = compile_cv_for_submission(sub_id, tmpl)
                except Exception as exc:
                    st.error(f"Could not compile CV: {exc}")
                    st.session_state[cache_key] = None

        pdf_bytes = st.session_state.get(cache_key)
        if pdf_bytes:
            show_pdf_pages(pdf_bytes)
            st.download_button(
                "⬇️ Download CV PDF",
                data=pdf_bytes,
                file_name=f"CV_{company}_{position}.pdf",
                mime="application/pdf",
                key=f"ps_cv_dl_{sub_id}",
            )
        else:
            st.warning("CV preview unavailable.")
