from pathlib import Path

import pytest

import finder


def touch(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_normalize_strips_extension_case_and_separators():
    assert finder.normalize("Sodium-Fabric_0.5.jar") == "sodium fabric 0 5"


def test_normalize_separator_only_name_is_empty():
    assert finder.normalize("---.jar") == ""


def test_similarity_exact_ignores_case_and_separators():
    assert finder.similarity("Sodium-0.5.jar", "sodium_0.5.JAR") == 100.0


def test_similarity_different_extension_is_zero():
    assert finder.similarity("sodium.jar", "sodium.txt") == 0.0


def test_similarity_extensionless_only_matches_extensionless():
    assert finder.similarity("LICENSE", "license") == 100.0
    assert finder.similarity("LICENSE", "license.txt") == 0.0


def test_similarity_close_versions_are_high():
    assert finder.similarity("sodium-0.5.jar", "sodium-0.6.jar") > 85


def test_similarity_unrelated_is_low():
    assert finder.similarity("abc.jar", "xyz.jar") < 50


def test_similarity_empty_normalized_is_zero():
    assert finder.similarity("---.jar", "---.jar") == 0.0


def test_collect_sources_from_folder_and_file(tmp_path):
    touch(tmp_path / "drop" / "a" / "b" / "x.jar")
    touch(tmp_path / "drop" / "y.jar")
    single = touch(tmp_path / "z.jar")
    sources = finder.collect_sources([tmp_path / "drop", single])
    assert [s.name for s in sources] == ["x.jar", "y.jar", "z.jar"]
    assert sources[0].path == tmp_path / "drop" / "a" / "b" / "x.jar"


def test_collect_sources_ignores_folders_themselves(tmp_path):
    (tmp_path / "drop" / "empty-folder").mkdir(parents=True)
    assert finder.collect_sources([tmp_path / "drop"]) == []


def test_collect_sources_has_no_duplicates(tmp_path):
    f = touch(tmp_path / "drop" / "x.jar")
    sources = finder.collect_sources([tmp_path / "drop", f, f])
    assert len(sources) == 1


def test_collect_sources_ignores_missing_paths(tmp_path):
    assert finder.collect_sources([tmp_path / "nope"]) == []
