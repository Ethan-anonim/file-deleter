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


def test_search_root_pinned_per_search(app, tmp_path):
    touch(tmp_path / "drop" / "sodium-0.5.jar")
    target = touch(tmp_path / "mods" / "x" / "y" / "sodium-0.5.jar")
    other = tmp_path / "other"
    other.mkdir()
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    app.set_search_root(other)
    app.delete_current()
    assert not target.exists()
    assert not (tmp_path / "mods" / "x").exists()
    assert (tmp_path / "mods").exists()


def test_buttons_disabled_during_delete_and_reenabled_after(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "a.jar")
    touch(tmp_path / "drop" / "b.jar")
    touch(tmp_path / "mods" / "a.jar")
    touch(tmp_path / "mods" / "b.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    states = []
    real = app_module.finder.delete_match

    def spy(*a, **k):
        states.append([str(b["state"]) for b in (app.btn_delete, app.btn_skip, app.btn_stop)])
        return real(*a, **k)

    monkeypatch.setattr(app_module.finder, "delete_match", spy)
    app.delete_current()
    assert states == [["disabled"] * 3]
    assert [str(b["state"]) for b in (app.btn_delete, app.btn_skip, app.btn_stop)] == ["normal"] * 3


def _setup(app, tmp_path, names, permanent=True):
    for n in names:
        touch(tmp_path / "drop" / n)
        touch(tmp_path / "mods" / n)
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(permanent)
    app.start_search()


def _states(app):
    return [str(b["state"]) for b in (app.btn_delete, app.btn_skip, app.btn_stop)]


def test_click_guard_ignores_early_clicks(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"])
    t = {"now": 100.0}
    monkeypatch.setattr(app_module.time, "monotonic", lambda: t["now"])
    app.shown_at = 100.0
    t["now"] = 100.1
    app._on_delete_click()
    app._on_skip_click()
    assert app.deleted == 0 and app.index == 0
    t["now"] = 100.5
    app._on_skip_click()
    assert app.index == 1
    app.shown_at = 100.5
    t["now"] = 100.6
    app._on_delete_click()
    assert app.deleted == 0
    t["now"] = 101.0
    app._on_delete_click()
    assert app.deleted == 1


def test_no_recycle_bin_asks_and_declining_keeps_file(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar"], permanent=False)
    path = app.matches[0].path
    monkeypatch.setattr(app_module.finder, "drive_has_recycle_bin", lambda p: False)
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: False)
    calls = []
    monkeypatch.setattr(app_module.finder, "delete_match",
                        lambda *a, **k: calls.append(a) or app_module.finder.DeleteResult(path, []))
    app.delete_current()
    assert calls == [] and app.deleted == 0
    assert _states(app) == ["normal"] * 3
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: True)
    app.delete_current()
    assert len(calls) == 1 and app.deleted == 1


def test_source_file_confirmation(app, tmp_path, monkeypatch):
    target = touch(tmp_path / "mods" / "a.jar")
    app.add_paths([target])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    assert app.matches[0].is_source
    answers = iter([False, True, True])
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: next(answers))
    app.delete_current()
    assert target.exists()
    app.delete_current()
    assert not target.exists()


def test_vanished_matches_are_skipped_and_buttons_consistent(app, tmp_path):
    _setup(app, tmp_path, ["a.jar", "b.jar", "c.jar", "d.jar"])
    order = [m.path for m in app.matches]
    order[1].unlink()
    order[2].unlink()
    app.skip_current()
    assert app.index == 3
    assert _states(app) == ["normal"] * 3
    assert str(order[3]) == app.match_path.get()
    app.delete_current()
    assert app.deleted == 1
    assert _states(app) == ["disabled"] * 3
    assert app.warning.get() == ""
    app.finish()


def test_vanished_folder_does_not_lock_window(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"])
    def boom(*a, **k):
        raise PermissionError("brak dostępu")
    monkeypatch.setattr(app_module.finder, "folders_emptied_by", boom)
    app.skip_current()
    assert _states(app) == ["normal"] * 3
    assert "nie można sprawdzić" in app.warning.get()


def test_all_remaining_vanished_ends_cleanly(app, tmp_path):
    _setup(app, tmp_path, ["a.jar", "b.jar"])
    for m in app.matches[1:]:
        m.path.unlink()
    app.skip_current()
    assert _states(app) == ["disabled"] * 3
    assert "Koniec" in app.status.get()
