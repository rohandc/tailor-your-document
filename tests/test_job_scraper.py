import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeExperience:
    def __init__(self, title, company, description):
        self.title = title
        self.company = company
        self.description = description


class FakeCVObject:
    def __init__(self):
        self.experiences = [
            FakeExperience(
                "Senior Engineer",
                "Acme Corp",
                "- Built REST APIs using Python and Flask\n- Deployed services using Docker and GitLab CI/CD",
            )
        ]
        self.projects = [
            FakeExperience(
                "Open Source Contrib",
                None,
                "- Contributed Kubernetes operator for automated scaling",
            )
        ]


def test_extract_keywords_parses_llm_response():
    from support.job_scraper import extract_keywords

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = json.dumps({
        "Technical Skills": ["Python", "Docker"],
        "Soft Skills": ["communication"],
        "Tools": ["JIRA"],
        "Domain Knowledge": ["microservices"],
    })
    fake_llm.invoke.return_value = fake_response

    result = extract_keywords("We need Python and Docker skills.", fake_llm)

    assert "Technical Skills" in result
    assert "Python" in result["Technical Skills"]
    assert "Docker" in result["Technical Skills"]
    assert "communication" in result["Soft Skills"]


def test_extract_keywords_returns_empty_on_bad_json():
    from support.job_scraper import extract_keywords

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = "not valid json at all"
    fake_llm.invoke.return_value = fake_response

    result = extract_keywords("some job", fake_llm)
    assert result == {}


def test_generate_keyword_suggestions_returns_suggestion():
    from support.job_scraper import generate_keyword_suggestions

    fake_llm = MagicMock()
    fake_response = MagicMock()
    fake_response.content = json.dumps({
        "keyword": "Kubernetes",
        "original_bullet": "Deployed services using Docker and GitLab CI/CD",
        "suggested_rewrite": "Deployed and orchestrated services using Docker, Kubernetes, and GitLab CI/CD",
        "location": "Experience — Acme Corp, Senior Engineer",
        "source_type": "experience",
        "source_index": 0,
    })
    fake_llm.invoke.return_value = fake_response

    cv = FakeCVObject()
    result = generate_keyword_suggestions("Kubernetes", cv, fake_llm)

    assert result["keyword"] == "Kubernetes"
    assert "Kubernetes" in result["suggested_rewrite"]
    assert result["source_type"] == "experience"
    assert result["source_index"] == 0


def test_generate_keyword_suggestions_returns_none_for_empty_cv():
    from support.job_scraper import generate_keyword_suggestions

    fake_llm = MagicMock()

    class EmptyCVObject:
        experiences = []
        projects = []

    result = generate_keyword_suggestions("Kubernetes", EmptyCVObject(), fake_llm)
    assert result is None


@patch("support.job_scraper.requests.get")
def test_scrape_job_description_returns_text(mock_get):
    from support.job_scraper import scrape_job_description

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <html><body>
    <main>
        <h1>Software Engineer</h1>
        <p>We are looking for a Python developer with 3+ years of experience building REST APIs.
        You will work with Docker, Kubernetes, and CI/CD pipelines to deploy microservices at scale.
        Strong communication skills required. Experience with JIRA and GitLab preferred.
        This is a great opportunity to join a fast-growing team working on cutting-edge technology.</p>
    </main>
    </body></html>
    """
    mock_get.return_value = mock_response

    result = scrape_job_description("https://example.com/job/123")

    assert "Python" in result
    assert "REST APIs" in result
    assert len(result) >= 200
