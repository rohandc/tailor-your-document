import sqlite3
import pickle
import tempfile
import os
from datetime import datetime
from support.settings import dest_dir
from support.html_builder import CVBuilder, CoverLetterBuilder
from xhtml2pdf import pisa

DB_PATH = f"{dest_dir}/cv_submissions.db"


def initialize_db():
    """Initialize the database and create tables if they don't exist.
    Also runs safe ALTER TABLE migrations for new columns."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                submission_date TEXT NOT NULL,
                cv_data BLOB NOT NULL,
                cover_letter_data BLOB NOT NULL,
                jd_information_data BLOB NOT NULL
            )
        """)
        # Safe migration: add new columns only if they don't already exist
        for column_def in [
            "status TEXT DEFAULT 'Applied'",
            "notes TEXT",
            "job_url TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE submissions ADD COLUMN {column_def}")
            except sqlite3.OperationalError:
                pass  # column already exists — safe to ignore
        conn.commit()


def save_submission(company, position, cv_object, cover_letter_object, jd_information_object):
    """Save a submission with structured objects to the database"""
    initialize_db()

    with sqlite3.connect(DB_PATH) as conn:
        cv_blob = pickle.dumps(cv_object)
        cover_letter_blob = pickle.dumps(cover_letter_object)
        jd_info_blob = pickle.dumps(jd_information_object)

        conn.execute("""
            INSERT INTO submissions (company, position, submission_date,
            cv_data, cover_letter_data, jd_information_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company, position, datetime.now().isoformat(),
              cv_blob, cover_letter_blob, jd_info_blob))
        conn.commit()


def update_submission(submission_id, cv_object, cover_letter_object, jd_information_object):
    """Update an existing submission with new structured objects"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cv_blob = pickle.dumps(cv_object)
            cover_letter_blob = pickle.dumps(cover_letter_object)
            jd_info_blob = pickle.dumps(jd_information_object)

            conn.execute("""
                UPDATE submissions
                SET cv_data = ?, cover_letter_data = ?, jd_information_data = ?
                WHERE id = ?
            """, (cv_blob, cover_letter_blob, jd_info_blob, submission_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating submission: {e}")
        return False


def update_submission_metadata(submission_id, status, notes, job_url):
    """Update the editable metadata fields of a submission."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE submissions SET status = ?, notes = ?, job_url = ? WHERE id = ?",
                (status, notes, job_url, submission_id),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating submission metadata: {e}")
        return False


def delete_submission(submission_id):
    """Permanently delete a submission by ID."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error deleting submission: {e}")
        return False


def get_submission_metadata(submission_id):
    """Return (id, company, position, submission_date, status, notes, job_url) for one row."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date, "
                "COALESCE(status, 'Applied') as status, notes, job_url "
                "FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
    except Exception as e:
        print(f"Error getting submission metadata: {e}")
        return None


def get_all_submissions():
    """Get all submissions (id, company, position, submission_date). Preserved for backward compat."""
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date FROM submissions"
            ).fetchall()
    except Exception as e:
        print(f"Error getting submissions: {e}")
        return []


def get_all_submissions_with_metadata():
    """Return all submissions with all metadata columns, newest first.

    Each row: (id, company, position, submission_date, status, notes, job_url)
    """
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                "SELECT id, company, position, submission_date, "
                "COALESCE(status, 'Applied') as status, notes, job_url "
                "FROM submissions ORDER BY submission_date DESC"
            ).fetchall()
    except Exception as e:
        print(f"Error getting submissions with metadata: {e}")
        return []


def get_submission_objects(submission_id):
    """Get structured objects for a specific submission"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute(
                "SELECT cv_data, cover_letter_data, jd_information_data FROM submissions WHERE id = ?",
                (submission_id,)
            ).fetchone()

            if result:
                cv_object = pickle.loads(result[0])
                cover_letter_object = pickle.loads(result[1])
                jd_info_object = pickle.loads(result[2])
                return cv_object, cover_letter_object, jd_info_object
            return None, None, None
    except Exception as e:
        print(f"Error getting submission objects: {e}")
        return None, None, None


def generate_pdf_from_submission(submission_id, template_id="1"):
    """Generate PDFs from stored structured objects and return file paths"""
    try:
        cv_object, cover_letter_object, jd_info_object = get_submission_objects(submission_id)

        if not all([cv_object, cover_letter_object, jd_info_object]):
            raise ValueError("Could not retrieve submission objects")

        temp_dir = tempfile.mkdtemp(prefix="cv_builder_")

        cv_builder = CVBuilder()
        cv_html = cv_builder.build_html_from_cv(cv_object, template_id, temp_dir)
        cv_pdf_path = f"{temp_dir}/cv_{submission_id}.pdf"
        with open(cv_pdf_path, "wb") as f:
            pisa.CreatePDF(cv_html, dest=f)

        cover_letter_builder = CoverLetterBuilder()
        cl_html = cover_letter_builder.build_html_from_cover_letter(cover_letter_object, template_id, temp_dir)
        cl_pdf_path = f"{temp_dir}/cover_letter_{submission_id}.pdf"
        with open(cl_pdf_path, "wb") as f:
            pisa.CreatePDF(cl_html, dest=f)

        return cv_pdf_path, cl_pdf_path, temp_dir

    except Exception as e:
        print(f"Error generating PDFs: {e}")
        return None, None, None


def cleanup_temp_files(temp_dir):
    """Clean up temporary files and directory"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temp files: {e}")


def has_submissions():
    """Check if there are any submissions in the database"""
    try:
        initialize_db()
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
            return result[0] > 0 if result else False
    except Exception as e:
        print(f"Error checking submissions: {e}")
        return False
