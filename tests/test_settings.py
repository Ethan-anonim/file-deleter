import json

import settings


def test_load_missing_file_returns_defaults(tmp_path):
    assert settings.load(tmp_path / "nope.json") == settings.DEFAULTS


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    data = {"theme": "dark", "last_root": "D:/mods", "threshold": 92}
    assert settings.save(data, path) is True
    assert settings.load(path) == data


def test_corrupted_file_returns_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    assert settings.load(path) == settings.DEFAULTS


def test_non_object_json_returns_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert settings.load(path) == settings.DEFAULTS


def test_invalid_values_fall_back_per_key(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "neon", "last_root": 5, "threshold": "x"}),
                    encoding="utf-8")
    assert settings.load(path) == settings.DEFAULTS


def test_threshold_is_clamped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"threshold": 10}), encoding="utf-8")
    assert settings.load(path)["threshold"] == 50
    path.write_text(json.dumps({"threshold": 500}), encoding="utf-8")
    assert settings.load(path)["threshold"] == 100


def test_unknown_keys_are_dropped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "light", "evil": "x"}), encoding="utf-8")
    assert "evil" not in settings.load(path)
    assert settings.load(path)["theme"] == "light"


def test_save_failure_is_swallowed(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert settings.save(settings.DEFAULTS, blocker / "settings.json") is False


def test_default_path_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert settings.settings_path() == tmp_path / "ModDeleter" / "settings.json"
