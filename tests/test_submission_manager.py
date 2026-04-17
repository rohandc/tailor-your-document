import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_initialize_db_adds_new_columns(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    # Simulate an old DB without the new columns
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                submission_date TEXT NOT NULL,
                cv_data BLOB NOT NULL,
                cover_letter_data BLOB NOT NULL,
                jd_information_data BLOB NOT NULL
            )
        """)

    from support.submission_manager import initialize_db
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()]

    assert "status" in cols
    assert "notes" in cols
    assert "job_url" in cols


def test_update_and_get_submission_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, update_submission_metadata, get_submission_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TestCorp", "Engineer", "2026-01-01", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    row = get_submission_metadata(1)
    assert row[1] == "TestCorp"
    assert row[4] == "Applied"  # default status via COALESCE

    success = update_submission_metadata(1, "Interviewing", "Called on Monday", "https://example.com/job")
    assert success is True

    row = get_submission_metadata(1)
    assert row[4] == "Interviewing"
    assert row[5] == "Called on Monday"
    assert row[6] == "https://example.com/job"


def test_delete_submission(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, delete_submission, get_submission_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TestCorp", "Engineer", "2026-01-01", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    success = delete_submission(1)
    assert success is True
    assert get_submission_metadata(1) is None


def test_get_all_submissions_with_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("support.submission_manager.DB_PATH", db_path)

    from support.submission_manager import initialize_db, get_all_submissions_with_metadata
    initialize_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Corp A", "Dev", "2026-01-01", b"cv", b"cl", b"jd", "Offer"),
        )
        conn.execute(
            "INSERT INTO submissions "
            "(company, position, submission_date, cv_data, cover_letter_data, jd_information_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Corp B", "Manager", "2026-01-02", b"cv", b"cl", b"jd"),
        )
        conn.commit()

    rows = get_all_submissions_with_metadata()
    assert len(rows) == 2
    # Ordered DESC by submission_date — Corp B first
    assert rows[0][1] == "Corp B"
    assert rows[0][4] == "Applied"  # default via COALESCE
    assert rows[1][1] == "Corp A"
    assert rows[1][4] == "Offer"
