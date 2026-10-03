from pathlib import Path

import pytest
import tkinter as tk

app_module = pytest.importorskip("app")


def make_root(attempts=4):
    """Create a Tk root; Tcl occasionally fails to initialise transiently on Windows, so retry."""
    import time
    from tkinterdnd2 import TkinterDnD

    last = None
    for _ in range(attempts):
        try:
            root = TkinterDnD.Tk()
        except (tk.TclError, RuntimeError) as exc:
            last = exc
            time.sleep(0.3)
            continue
        root.withdraw()
        return root
    raise last


@pytest.fixture
def app(monkeypatch, tmp_path_factory):
    try:
        root = make_root()
    except (tk.TclError, RuntimeError, ImportError) as exc:
        pytest.skip(f"no graphical environment: {exc}")
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: True)
    settings_file = tmp_path_factory.mktemp('cfg') / 'settings.json'
    instance = app_module.App(root, settings_file=settings_file)
    yield instance
    root.destroy()


def search(app):
    app.start_search()
    app.wait_for_search()


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
    search(app)
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
    search(app)
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
    search(app)
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
    search(app)
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
    search(app)
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
    search(app)


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
    search(app)
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
        raise PermissionError("access denied")
    monkeypatch.setattr(app_module.finder, "folders_emptied_by", boom)
    app.skip_current()
    assert _states(app) == ["normal"] * 3
    assert "cannot inspect" in app.warning.get()


def test_all_remaining_vanished_ends_cleanly(app, tmp_path):
    _setup(app, tmp_path, ["a.jar", "b.jar"])
    for m in app.matches[1:]:
        m.path.unlink()
    app.skip_current()
    assert _states(app) == ["disabled"] * 3
    assert "Done" in app.status.get()


class FakeEvent:
    def __init__(self, data="", action="copy"):
        self.data = data
        self.action = action


def test_score_level_thresholds():
    assert app_module.score_level(100) == "ok"
    assert app_module.score_level(99.9) == "mid"
    assert app_module.score_level(90) == "mid"
    assert app_module.score_level(89.9) == "low"


def test_search_runs_in_background_and_reports_progress(app, tmp_path):
    for i in range(250):
        touch(tmp_path / "mods" / f"noise{i}.jar")
    touch(tmp_path / "drop" / "noise7.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    app.start_search()
    assert app.searching is True
    assert str(app.btn_search["state"]) == "disabled"
    assert str(app.btn_cancel["state"]) == "normal"
    app.wait_for_search()
    assert app.searching is False
    assert str(app.btn_search["state"]) == "normal"
    assert str(app.btn_cancel["state"]) == "disabled"
    assert "250" in app.progress_text.get()
    assert len(app.matches) >= 1


def test_start_search_ignored_while_searching(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "a.jar")
    touch(tmp_path / "mods" / "a.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    calls = []
    real = app_module.finder.find_matches

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(app_module.finder, "find_matches", counting)
    app.start_search()
    app.start_search()
    app.wait_for_search()
    assert len(calls) == 1


def test_cancel_search(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "a.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path)

    def endless(sources, root, threshold, on_progress, should_cancel, progress_every):
        import time as _t
        while not should_cancel():
            _t.sleep(0.005)
        raise app_module.finder.SearchCancelled()

    monkeypatch.setattr(app_module.finder, "find_matches", endless)
    app.start_search()
    app.cancel_search()
    app.wait_for_search()
    assert "cancelled" in app.status.get()
    assert app.matches == []
    assert str(app.btn_search["state"]) == "normal"
    assert str(app.btn_delete["state"]) == "disabled"


def test_worker_error_is_reported_not_raised(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "a.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("awaria dysku")

    monkeypatch.setattr(app_module.finder, "find_matches", boom)
    app.start_search()
    app.wait_for_search()
    assert "awaria dysku" in app.status.get()
    assert app.searching is False
    assert str(app.btn_search["state"]) == "normal"


def test_badge_shows_score_color_and_hides_after_finish(app, tmp_path):
    _setup(app, tmp_path, ["a.jar"])
    assert app.badge.cget("text") == "100%"
    assert app.badge.cget("bg") == app_module.BADGE_COLORS["ok"][0]
    assert app.badge.winfo_manager() == "pack"
    app.finish()
    assert app.badge.winfo_manager() == ""


def test_reveal_in_explorer_selects_file(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar"])
    launched = []
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda args, **k: launched.append(args))
    app.reveal_current()
    assert launched == [["explorer", "/select,", str(app.matches[0].path)]]


def test_reveal_falls_back_to_parent_folder_when_file_is_gone(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"])
    launched = []
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda args, **k: launched.append(args))
    current = app.matches[app.index].path
    current.unlink()
    app.reveal_current()
    assert launched == [["explorer", str(current.parent)]]


def test_reveal_error_is_shown_not_raised(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar"])

    def boom(*a, **k):
        raise OSError("brak explorer")

    monkeypatch.setattr(app_module.subprocess, "Popen", boom)
    app.reveal_current()
    assert "brak explorer" in app.status.get()


def test_drop_enter_and_leave_toggle_highlight(app):
    assert app._on_drop_enter(FakeEvent(action="copy")) == "copy"
    assert app._hover is True
    assert app._on_drop_leave(FakeEvent(action="copy")) == "copy"
    assert app._hover is False


def test_drop_event_adds_paths_with_spaces(app, tmp_path):
    folder = tmp_path / "my drop"
    touch(folder / "x.jar")
    single = touch(tmp_path / "y.jar")
    app._hover = True
    result = app._on_drop(FakeEvent(data=f"{{{folder.as_posix()}}} {single.as_posix()}", action="copy"))
    assert result == "copy"
    assert app._hover is False
    assert {s.name for s in app.sources.values()} == {"x.jar", "y.jar"}
    assert "2" in app.sources_text.get()


def test_sources_counter_follows_checkboxes(app, tmp_path):
    touch(tmp_path / "drop" / "a.jar")
    touch(tmp_path / "drop" / "b.jar")
    app.add_paths([tmp_path / "drop"])
    assert app.sources_text.get() == "Selected: 2 of 2"
    key = next(iter(app.sources))
    app.checked[key] = False
    app._refresh_sources_text()
    assert app.sources_text.get() == "Selected: 1 of 2"
    app.clear_sources()
    assert app.sources_text.get() == "List is empty"


def test_theme_toggle_switches_and_persists(app):
    start = app.theme
    app.toggle_theme()
    assert app.theme != start
    import settings
    assert settings.load(app.settings_file)["theme"] == app.theme
    app.toggle_theme()
    assert app.theme == start


def test_settings_restored_on_next_start(app, tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    app.set_search_root(mods)
    app._on_scale(72.4)
    app.toggle_theme()
    app._save_settings()
    chosen_theme = app.theme
    second_root = make_root()
    try:
        second = app_module.App(second_root, settings_file=app.settings_file)
        assert second.search_root == mods
        assert second.threshold.get() == 72
        assert second.theme == chosen_theme
        assert second.permanent.get() is False
    finally:
        second_root.destroy()


def test_missing_saved_root_is_ignored(app, tmp_path):
    import settings
    settings.save({"theme": "dark", "last_root": str(tmp_path / "gone"), "threshold": 85},
                  app.settings_file)
    other = make_root()
    try:
        fresh = app_module.App(other, settings_file=app.settings_file)
        assert fresh.search_root is None
    finally:
        other.destroy()


def _record_dialog(monkeypatch, answer=True):
    calls = []

    def fake(title, message, **kwargs):
        calls.append((title, message, kwargs))
        return answer

    monkeypatch.setattr(app_module.messagebox, "askyesno", fake)
    return calls


def test_delete_all_removes_every_remaining_match_and_empty_folders(app, tmp_path, monkeypatch):
    names = ["a.jar", "b.jar", "c.jar"]
    for n in names:
        touch(tmp_path / "drop" / n)
        touch(tmp_path / "mods" / "deep" / n)
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    search(app)
    calls = _record_dialog(monkeypatch)
    app.delete_all()
    assert len(calls) == 1
    assert not (tmp_path / "mods" / "deep").exists()
    assert (tmp_path / "mods").exists()
    assert app.deleted == 3
    assert app.matches == []
    assert _states(app) == ["disabled"] * 3
    assert "deleted" in app.status.get() and "3" in app.status.get()


def test_delete_all_asks_with_count_mode_and_defaults_to_no(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"], permanent=False)
    monkeypatch.setattr(app_module.finder, "drive_has_recycle_bin", lambda p: True)
    calls = _record_dialog(monkeypatch, answer=False)
    app.delete_all()
    (title, message, kwargs), = calls
    assert "2" in message and "Recycle Bin" in message
    assert kwargs.get("default") == "no"
    assert kwargs.get("icon") == "warning"
    assert all(m.path.exists() for m in app.matches)
    assert app.deleted == 0
    assert _states(app) == ["normal"] * 3


def test_delete_all_message_says_permanent_when_permanent(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar"], permanent=True)
    calls = _record_dialog(monkeypatch, answer=False)
    app.delete_all()
    assert "PERMANENTLY" in calls[0][1]


def test_delete_all_message_mentions_lower_similarity(app, tmp_path, monkeypatch):
    touch(tmp_path / "drop" / "sodium-0.5.jar")
    touch(tmp_path / "mods" / "sodium-0.5.jar")
    touch(tmp_path / "mods" / "sodium-0.6.jar")
    app.add_paths([tmp_path / "drop"])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    search(app)
    calls = _record_dialog(monkeypatch, answer=False)
    app.delete_all()
    message = calls[0][1]
    assert "below 100%" in message
    assert "1" in message and "90%" in message


def test_delete_all_skips_source_files_and_reports_it(app, tmp_path, monkeypatch):
    original = touch(tmp_path / "mods" / "keep" / "a.jar")
    copy = touch(tmp_path / "mods" / "other" / "a.jar")
    app.add_paths([original])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    search(app)
    assert any(m.is_source for m in app.matches)
    calls = _record_dialog(monkeypatch)
    app.delete_all()
    assert original.exists()
    assert not copy.exists()
    assert "eference" in calls[0][1]
    assert "eference" in app.status.get()


def test_delete_all_with_only_source_files_does_nothing(app, tmp_path, monkeypatch):
    target = touch(tmp_path / "mods" / "a.jar")
    app.add_paths([target])
    app.set_search_root(tmp_path / "mods")
    app.permanent.set(True)
    search(app)
    calls = _record_dialog(monkeypatch)
    app.delete_all()
    assert calls == []
    assert target.exists()
    assert "eference" in app.status.get()
    assert _states(app) == ["normal"] * 3


def test_delete_all_starts_from_current_match(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar", "c.jar"])
    first = app.matches[0].path
    app.skip_current()
    _record_dialog(monkeypatch)
    app.delete_all()
    assert first.exists()
    assert app.deleted == 2


def test_delete_all_ignores_vanished_files(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar", "c.jar"])
    app.matches[1].path.unlink()
    calls = _record_dialog(monkeypatch)
    app.delete_all()
    assert app.deleted == 2
    assert "Files to delete: 2" in calls[0][1]


def test_delete_all_continues_after_an_error(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar", "c.jar"])
    real = app_module.finder.delete_match
    bad = app.matches[1].path

    def flaky(path, root, permanent=False, **k):
        if path == bad:
            raise PermissionError("zablokowany")
        return real(path, root, permanent=permanent, **k)

    monkeypatch.setattr(app_module.finder, "delete_match", flaky)
    _record_dialog(monkeypatch)
    app.delete_all()
    assert app.deleted == 2
    assert bad.exists()
    assert "zablokowany" in app.status.get()
    assert "1" in app.status.get()


def test_delete_all_warns_about_drives_without_recycle_bin(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"], permanent=False)
    monkeypatch.setattr(app_module.finder, "drive_has_recycle_bin", lambda p: False)
    calls = _record_dialog(monkeypatch, answer=False)
    app.delete_all()
    message = calls[0][1]
    assert "without a Recycle Bin" in message and "2" in message


def test_delete_all_uses_trash_mode_when_not_permanent(app, tmp_path, monkeypatch):
    _setup(app, tmp_path, ["a.jar", "b.jar"], permanent=False)
    monkeypatch.setattr(app_module.finder, "drive_has_recycle_bin", lambda p: True)
    seen = []

    def fake(path, root, permanent=False, **k):
        seen.append(permanent)
        return app_module.finder.DeleteResult(path, [])

    monkeypatch.setattr(app_module.finder, "delete_match", fake)
    _record_dialog(monkeypatch)
    app.delete_all()
    assert seen == [False, False]


def test_delete_all_button_label_tracks_remaining_matches(app, tmp_path):
    _setup(app, tmp_path, ["a.jar", "b.jar", "c.jar"])
    assert app.delete_all_text.get() == "Delete all (3)"
    app.skip_current()
    assert app.delete_all_text.get() == "Delete all (2)"
    app.finish()
    assert str(app.btn_delete_all["state"]) == "disabled"
    assert app.delete_all_text.get() == "Delete all"
