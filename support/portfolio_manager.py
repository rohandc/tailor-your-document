import os
import json
import pickle
from datetime import datetime
from support.settings import dest_dir

PORTFOLIOS_DIR = os.path.join(dest_dir, "portfolios")
INDEX_FILE = os.path.join(PORTFOLIOS_DIR, "portfolios.json")


def _ensure_portfolios_dir():
    os.makedirs(PORTFOLIOS_DIR, exist_ok=True)


def _read_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r") as f:
        return json.load(f)


def _write_index(entries):
    _ensure_portfolios_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def save_portfolio(name: str, cv_object) -> None:
    """Serialise cv_object to output/portfolios/<name>.pkl and update the index."""
    _ensure_portfolios_dir()
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    with open(file_path, "wb") as f:
        pickle.dump(cv_object, f)

    entries = _read_index()
    now = datetime.now().isoformat()

    for entry in entries:
        if entry["name"] == name:
            entry["last_modified"] = now
            _write_index(entries)
            return

    entries.append({
        "name": name,
        "created_date": now,
        "last_modified": now,
        "is_active": len(entries) == 0,  # first portfolio becomes active automatically
    })
    _write_index(entries)


def load_portfolio(name: str):
    """Deserialise and return a cv_object, or None if not found."""
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        return pickle.load(f)


def list_portfolios():
    """Return list of index entries: [{name, created_date, last_modified, is_active}]."""
    return _read_index()


def set_active_portfolio(name: str) -> None:
    """Mark one portfolio as active and clear the flag on all others."""
    entries = _read_index()
    for entry in entries:
        entry["is_active"] = entry["name"] == name
    _write_index(entries)


def get_active_portfolio():
    """Load and return the currently active cv_object, or None if no portfolios exist."""
    entries = _read_index()
    for entry in entries:
        if entry["is_active"]:
            return load_portfolio(entry["name"])
    # Fallback: return the first portfolio if none is explicitly active
    if entries:
        return load_portfolio(entries[0]["name"])
    return None


def get_active_portfolio_name() -> str | None:
    """Return the name of the active portfolio, or None."""
    entries = _read_index()
    for entry in entries:
        if entry["is_active"]:
            return entry["name"]
    if entries:
        return entries[0]["name"]
    return None


def delete_portfolio(name: str) -> None:
    """Remove a portfolio file and its index entry.

    If the deleted portfolio was the active one and others remain,
    the most recently modified becomes the new active.
    """
    file_path = os.path.join(PORTFOLIOS_DIR, f"{name}.pkl")
    if os.path.exists(file_path):
        os.remove(file_path)

    entries = _read_index()
    was_active = any(e["name"] == name and e["is_active"] for e in entries)
    entries = [e for e in entries if e["name"] != name]

    if was_active and entries:
        entries.sort(key=lambda e: e["last_modified"], reverse=True)
        entries[0]["is_active"] = True

    _write_index(entries)


def rename_portfolio(old_name: str, new_name: str) -> None:
    """Rename the .pkl file and update the index entry."""
    old_path = os.path.join(PORTFOLIOS_DIR, f"{old_name}.pkl")
    new_path = os.path.join(PORTFOLIOS_DIR, f"{new_name}.pkl")
    if os.path.exists(old_path):
        os.rename(old_path, new_path)

    entries = _read_index()
    for entry in entries:
        if entry["name"] == old_name:
            entry["name"] = new_name
            entry["last_modified"] = datetime.now().isoformat()
            break
    _write_index(entries)


def migrate_legacy_portfolio() -> None:
    """One-time migration: copy output/structured_cv.pkl → portfolios/Default.pkl.

    Only runs if no portfolios exist yet and the legacy file is present.
    """
    legacy_path = os.path.join(dest_dir, "structured_cv.pkl")
    if not os.path.exists(legacy_path):
        return
    if list_portfolios():
        return  # already migrated

    with open(legacy_path, "rb") as f:
        cv_object = pickle.load(f)

    save_portfolio("Default", cv_object)
    set_active_portfolio("Default")
