import os
import sys
import json
import pickle
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeCVObject:
    def __init__(self, name):
        self.name = name


def _patch_dirs(monkeypatch, tmp_path):
    portfolios_dir = str(tmp_path / "portfolios")
    index_file = os.path.join(portfolios_dir, "portfolios.json")
    monkeypatch.setattr("support.portfolio_manager.PORTFOLIOS_DIR", portfolios_dir)
    monkeypatch.setattr("support.portfolio_manager.INDEX_FILE", index_file)
    return portfolios_dir, index_file


def test_save_and_load_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, load_portfolio

    cv = FakeCVObject("Alice")
    save_portfolio("Work", cv)

    loaded = load_portfolio("Work")
    assert loaded.name == "Alice"


def test_save_creates_index_entry(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    entries = list_portfolios()

    assert len(entries) == 1
    assert entries[0]["name"] == "Work"
    assert entries[0]["is_active"] is True  # first portfolio is auto-active


def test_second_portfolio_not_auto_active(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))

    entries = list_portfolios()
    active = [e for e in entries if e["is_active"]]
    assert len(active) == 1
    assert active[0]["name"] == "Work"


def test_set_and_get_active_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, get_active_portfolio

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Side")

    active = get_active_portfolio()
    assert active.name == "Bob"


def test_delete_active_sets_next_active(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, delete_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Work")
    delete_portfolio("Work")

    entries = list_portfolios()
    assert len(entries) == 1
    assert entries[0]["name"] == "Side"
    assert entries[0]["is_active"] is True


def test_delete_nonactive_leaves_active_unchanged(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, set_active_portfolio, delete_portfolio, get_active_portfolio_name

    save_portfolio("Work", FakeCVObject("Alice"))
    save_portfolio("Side", FakeCVObject("Bob"))
    set_active_portfolio("Work")
    delete_portfolio("Side")

    assert get_active_portfolio_name() == "Work"


def test_rename_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    from support.portfolio_manager import save_portfolio, rename_portfolio, load_portfolio, list_portfolios

    save_portfolio("Work", FakeCVObject("Alice"))
    rename_portfolio("Work", "Career")

    loaded = load_portfolio("Career")
    assert loaded.name == "Alice"
    names = [e["name"] for e in list_portfolios()]
    assert "Career" in names
    assert "Work" not in names


def test_migrate_legacy_portfolio(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr("support.portfolio_manager.dest_dir", str(tmp_path))

    legacy_path = str(tmp_path / "structured_cv.pkl")
    cv = FakeCVObject("Legacy")
    with open(legacy_path, "wb") as f:
        pickle.dump(cv, f)

    from support.portfolio_manager import migrate_legacy_portfolio, list_portfolios, get_active_portfolio_name

    migrate_legacy_portfolio()

    entries = list_portfolios()
    assert len(entries) == 1
    assert entries[0]["name"] == "Default"
    assert get_active_portfolio_name() == "Default"
