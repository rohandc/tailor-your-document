import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List

import jinja2


# ── Escape helper ────────────────────────────────────────────────────────────

def latex_escape(text) -> str:
    """Escape special LaTeX characters in a string. Returns empty string for None."""
    if text is None:
        return ""
    text = str(text)
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text


# ── Bullet-point parser ──────────────────────────────────────────────────────

def description_to_items(desc) -> List[str]:
    """Split a bullet-point description string into a list of clean strings.

    Handles lines starting with •, -, *, or plain text. Falls back to
    splitting on '. ' if no bullet markers are found (max 5 items).
    """
    if not desc:
        return []

    lines = [line.strip() for line in desc.splitlines()]
    bullet_pattern = re.compile(r"^[•\-\*]\s*")
    bullet_lines = [bullet_pattern.sub("", line) for line in lines if bullet_pattern.match(line)]

    if bullet_lines:
        return [item for item in bullet_lines if item]

    # No bullet markers — try splitting on ". "
    sentences = [s.strip() for s in desc.split(". ") if s.strip()]
    # Re-add periods removed by split, except last if it already ends with punctuation
    result = []
    for i, sentence in enumerate(sentences[:5]):
        if i < len(sentences) - 1 and not sentence.endswith((".", "!", "?")):
            sentence = sentence + "."
        result.append(sentence)
    return result


# ── Jinja2 environment ───────────────────────────────────────────────────────

_TEMPLATES_DIR = Path(__file__).parent / "latex_templates"


def _build_jinja_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.Undefined,
        autoescape=False,
    )
    env.filters["e"] = latex_escape
    return env


# ── Renderer ─────────────────────────────────────────────────────────────────

def render_latex(final_cv, template_name: str = "neo_kim") -> str:
    """Render a FinalCurriculum to a LaTeX string using the named template."""
    env = _build_jinja_env()
    template = env.get_template(f"{template_name}.tex")

    personality = final_cv.personality
    name = latex_escape(personality.name if personality else "")
    surname = latex_escape(personality.surname if personality else "")
    job_title = latex_escape(final_cv.job_title or (personality.job_title if personality else "") or "")
    email = latex_escape(personality.e_mail if personality else "")
    telephone = latex_escape(personality.telephone if personality else "")
    linkedin = personality.linkedin_link if personality else ""  # used in \href — escape separately
    address = latex_escape(personality.address if personality else "")
    summary = latex_escape(final_cv.summary or "")

    hard_skills = final_cv.hard_skills or []
    soft_skills = final_cv.soft_skills or []
    hard_skills_str = latex_escape(", ".join(hard_skills))
    soft_skills_str = latex_escape(", ".join(soft_skills))

    experiences = final_cv.experiences or []
    exp_items = [description_to_items(exp.description) for exp in experiences]

    projects = final_cv.projects or []
    proj_items = [description_to_items(proj.description) for proj in projects]

    education = final_cv.education or []
    edu_items = [description_to_items(edu.description) for edu in education]

    ctx = {
        "name": name,
        "surname": surname,
        "job_title": job_title,
        "email": email,
        "telephone": telephone,
        "linkedin": linkedin,
        "address": address,
        "summary": summary,
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "hard_skills_str": hard_skills_str,
        "soft_skills_str": soft_skills_str,
        "experiences": experiences,
        "exp_items": exp_items,
        "projects": projects,
        "proj_items": proj_items,
        "education": education,
        "edu_items": edu_items,
    }

    return template.render(**ctx)


# ── Compiler ─────────────────────────────────────────────────────────────────

def compile_latex(latex_str: str) -> bytes:
    """Write latex_str to a temp file, compile twice with pdflatex, return PDF bytes.

    Raises RuntimeError if pdflatex is not found or compilation fails.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_str)

        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory", tmpdir,
            tex_path,
        ]

        for _pass in range(2):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "LaTeX compiler not available in this environment. "
                    "pdflatex was not found on the system PATH."
                )

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                stdout = result.stdout.decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"pdflatex compilation failed (pass {_pass + 1}).\n\n"
                    f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                )

        if not os.path.exists(pdf_path):
            raise RuntimeError("pdflatex ran successfully but no PDF was produced.")

        with open(pdf_path, "rb") as f:
            return f.read()


# ── Convenience entry point ───────────────────────────────────────────────────

def latex_to_pdf_bytes(final_cv, template_name: str = "neo_kim") -> bytes:
    """Render FinalCurriculum to LaTeX then compile to PDF, returning bytes."""
    latex_str = render_latex(final_cv, template_name=template_name)
    return compile_latex(latex_str)
