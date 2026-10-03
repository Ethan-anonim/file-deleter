from pathlib import Path

import pytest
import tkinter as tk

app_module = pytest.importorskip("app")


@pytest.fixture
def app(monkeypatch):
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except (tk.TclError, ImportError) as exc:
        pytest.skip(f"brak środowiska graficznego: {exc}")
    root.withdraw()
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: True)
    instance = app_module.App(root)
    yield instance
    root.destroy()


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    return path


def test_full_flow_search_skip_and_delete(app, tmp_path):
    touch(tmp_path / "drop" / "sodium-0.5.jar")
    touch(tmp_path / "drop" / "lithium-1.0.jar")
    a = touch(tmp_path / "mods" / "x" / "y" / "sodium-0.5.jar")
    b = touch(tmp_path / "mods" / "lithium-1.0.jar")

    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    assert len(app.matches) == 2

    first = app.matches[app.index].path
    app.skip_current()
    assert first.exists()

    app.delete_current()
    app.root.update()
    assert app.deleted == 1
    assert sum(p.exists() for p in (a, b)) == 1


def test_empty_folder_removed_after_delete(app, tmp_path):
    touch(tmp_path / "drop" / "sodium-0.5.jar")
    target = touch(tmp_path / "mods" / "x" / "y" / "sodium-0.5.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    app.delete_current()
    assert not target.exists()
    assert not (tmp_path / "mods" / "x").exists()
    assert (tmp_path / "mods").exists()


def test_delete_error_does_not_crash(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "a.jar")
    touch(tmp_path / "mods" / "a.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")

    def boom(*a, **k):
        raise PermissionError("zablokowany")

    monkeypatch.setattr(app_module.finder, "delete_match", boom)
    app.start_search()
    app.delete_current()
    assert app.deleted == 0
    assert "zablokowany" in app.status.get()
