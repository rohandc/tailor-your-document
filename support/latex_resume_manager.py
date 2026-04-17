"""
latex_resume_manager.py — save, load, list, and delete named LaTeX resume drafts.

Storage: pickled FinalCurriculum objects under output/latex_resumes/{name}.pkl
The output/ directory is volume-mounted in Docker so data persists across rebuilds.
"""
import os
import pickle
from datetime import datetime
from typing import List, Optional

from support.settings import dest_dir
from support.supportClasses import FinalCurriculum

RESUMES_DIR = os.path.join(dest_dir, "latex_resumes")
os.makedirs(RESUMES_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    """Replace path-unsafe characters."""
    keep = "-_. "
    return "".join(c for c in name if c.isalnum() or c in keep).strip() or "unnamed"


def _path_for(name: str) -> str:
    return os.path.join(RESUMES_DIR, f"{_safe_filename(name)}.pkl")


def save_resume(name: str, final_cv: FinalCurriculum) -> str:
    """Pickle a FinalCurriculum under the given name. Returns the storage path."""
    if not name or not name.strip():
        raise ValueError("Resume name cannot be empty.")
    path = _path_for(name)
    with open(path, "wb") as f:
        pickle.dump(final_cv, f)
    return path


def load_resume(name: str) -> Optional[FinalCurriculum]:
    """Load a resume by name. Returns None if it doesn't exist."""
    path = _path_for(name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def list_resumes() -> List[dict]:
    """Return a list of {name, last_modified} dicts, newest first."""
    if not os.path.isdir(RESUMES_DIR):
        return []
    entries = []
    for fname in os.listdir(RESUMES_DIR):
        if not fname.endswith(".pkl"):
            continue
        path = os.path.join(RESUMES_DIR, fname)
        entries.append({
            "name": fname[:-4],  # strip .pkl
            "last_modified": datetime.fromtimestamp(os.path.getmtime(path)),
        })
    entries.sort(key=lambda e: e["last_modified"], reverse=True)
    return entries


def delete_resume(name: str) -> bool:
    """Delete a saved resume. Returns True on success."""
    path = _path_for(name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
