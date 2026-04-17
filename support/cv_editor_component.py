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
        if not existing_proj:
            existing_proj = [Experience()]

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
        if s is not None and not pd.isna(s) and str(s).strip()
    ]
    final_cv = FinalCurriculum(
        personality=personality,
        job_title=job_title_input or None,
        summary=summary_input or None,
        experiences=experiences,
        projects=projects,
        education=education,
        hard_skills=hard_skills,
        soft_skills=[],
    )
    return True, final_cv
