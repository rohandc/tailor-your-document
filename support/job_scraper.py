import json
import requests
from bs4 import BeautifulSoup


def scrape_job_description(url: str) -> str:
    """Fetch and clean job description text from a URL.

    Attempt 1: requests + BeautifulSoup.
    Attempt 2 (fallback): Playwright headless Chromium for JS-rendered pages.
    Returns cleaned plain-text job description.
    """
    text = _scrape_with_requests(url)
    if len(text) >= 200:
        return text
    return _scrape_with_playwright(url)


def _scrape_with_requests(url: str) -> str:
    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JobScraper/1.0)"
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise elements
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        # Prefer semantic content containers
        for selector in ["main", "article", '[role="main"]']:
            container = soup.select_one(selector)
            if container:
                return _clean_text(container.get_text(separator="\n"))

        # Fallback: largest div block
        divs = soup.find_all("div")
        if divs:
            largest = max(divs, key=lambda d: len(d.get_text()))
            return _clean_text(largest.get_text(separator="\n"))

        return _clean_text(soup.get_text(separator="\n"))
    except Exception:
        return ""


def _scrape_with_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        for selector in ["main", "article", '[role="main"]']:
            container = soup.select_one(selector)
            if container:
                return _clean_text(container.get_text(separator="\n"))

        return _clean_text(soup.get_text(separator="\n"))
    except Exception:
        return ""


def _clean_text(text: str) -> str:
    """Collapse blank lines and strip leading/trailing whitespace."""
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return "\n".join(cleaned).strip()


def extract_keywords(job_description: str, llm) -> dict:
    """Send job description to LLM and return keywords grouped by category.

    Returns:
        {
            "Technical Skills": ["Python", "Docker", ...],
            "Soft Skills": ["communication", ...],
            "Tools": ["JIRA", ...],
            "Domain Knowledge": ["microservices", ...]
        }
    Returns {} on parse failure.
    """
    prompt = f"""Extract keywords from the following job description and group them by category.
Return ONLY a JSON object with these exact keys:
- "Technical Skills": list of programming languages, frameworks, platforms
- "Soft Skills": list of interpersonal/non-technical skills
- "Tools": list of specific tools, software, platforms (JIRA, Splunk, etc.)
- "Domain Knowledge": list of domain/industry concepts

Return ONLY the JSON object, no explanation.

Job Description:
{job_description}"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, Exception):
        return {}


def generate_keyword_suggestions(keyword: str, cv_object, llm) -> dict | None:
    """Find the most relevant existing bullet point for a keyword and suggest a rewrite.

    Returns:
        {
            "keyword": str,
            "original_bullet": str,
            "suggested_rewrite": str,
            "location": str,
            "source_type": "experience" | "project",
            "source_index": int
        }
    Returns None if the cv_object has no bullets to work with.
    """
    # Collect all bullets with their source metadata
    all_bullets = []
    for i, exp in enumerate(cv_object.experiences or []):
        if exp.description:
            for line in exp.description.splitlines():
                bullet = line.strip().lstrip("-•*").strip()
                if bullet:
                    all_bullets.append({
                        "bullet": bullet,
                        "location": f"Experience — {exp.company or exp.title}",
                        "source_type": "experience",
                        "source_index": i,
                    })
    for i, proj in enumerate(cv_object.projects or []):
        if proj.description:
            for line in proj.description.splitlines():
                bullet = line.strip().lstrip("-•*").strip()
                if bullet:
                    all_bullets.append({
                        "bullet": bullet,
                        "location": f"Project — {proj.title or proj.company}",
                        "source_type": "project",
                        "source_index": i,
                    })

    if not all_bullets:
        return None

    bullets_text = "\n".join(
        f"[{i}] ({b['location']}) {b['bullet']}"
        for i, b in enumerate(all_bullets)
    )

    prompt = f"""Given the keyword "{keyword}", find the most relevant bullet point from this CV and suggest a rewrite that naturally incorporates the keyword.

Bullet points (indexed):
{bullets_text}

Return ONLY a JSON object with these keys:
- "keyword": the keyword
- "original_bullet": the exact original bullet text (copy exactly from above)
- "suggested_rewrite": improved version that naturally includes the keyword
- "location": the location label from the bullet list
- "source_type": "experience" or "project"
- "source_index": the integer index from the bracket at the start of the chosen bullet

Return ONLY the JSON object, no explanation."""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, Exception):
        return None
