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


def sources_of(*names: str) -> list[finder.SourceFile]:
    return [finder.SourceFile(n, Path("/src") / n) for n in names]


def test_find_exact_match_in_nested_folders(tmp_path):
    target = touch(tmp_path / "root" / "a" / "b" / "sodium-0.5.jar")
    touch(tmp_path / "root" / "other.jar")
    matches = finder.find_matches(sources_of("sodium-0.5.jar"), tmp_path / "root")
    assert [m.path for m in matches] == [target]
    assert matches[0].score == 100.0
    assert matches[0].source_name == "sodium-0.5.jar"
    assert matches[0].is_source is False


def test_different_extension_is_not_a_match(tmp_path):
    touch(tmp_path / "root" / "sodium.jar")
    touch(tmp_path / "root" / "sodium.txt")
    matches = finder.find_matches(sources_of("sodium.jar"), tmp_path / "root", 0)
    assert [m.path.name for m in matches] == ["sodium.jar"]


def test_extension_case_is_ignored(tmp_path):
    touch(tmp_path / "root" / "sodium.JAR")
    matches = finder.find_matches(sources_of("sodium.jar"), tmp_path / "root")
    assert [m.path.name for m in matches] == ["sodium.JAR"]


def test_fuzzy_match_also_requires_same_extension(tmp_path):
    touch(tmp_path / "root" / "sodium-0.6.txt")
    assert finder.find_matches(sources_of("sodium-0.5.jar"), tmp_path / "root") == []


def test_folders_are_never_matches(tmp_path):
    touch(tmp_path / "root" / "sodium-0.5.jar" / "readme.txt")
    assert finder.find_matches(sources_of("sodium-0.5.jar"), tmp_path / "root") == []


def test_fuzzy_match_respects_threshold(tmp_path):
    touch(tmp_path / "root" / "sodium-0.6.jar")
    src = sources_of("sodium-0.5.jar")
    assert len(finder.find_matches(src, tmp_path / "root", threshold=85)) == 1
    assert finder.find_matches(src, tmp_path / "root", threshold=95) == []


def test_matches_sorted_by_score_desc(tmp_path):
    touch(tmp_path / "root" / "sodium-0.6.jar")
    touch(tmp_path / "root" / "deep" / "sodium-0.5.jar")
    matches = finder.find_matches(sources_of("sodium-0.5.jar"), tmp_path / "root")
    assert [m.path.name for m in matches] == ["sodium-0.5.jar", "sodium-0.6.jar"]
    assert matches[0].score > matches[1].score


def test_file_matching_several_sources_appears_once_with_best_score(tmp_path):
    touch(tmp_path / "root" / "sodium-0.5.jar")
    matches = finder.find_matches(
        sources_of("sodium-0.6.jar", "sodium-0.5.jar"), tmp_path / "root"
    )
    assert len(matches) == 1
    assert matches[0].score == 100.0
    assert matches[0].source_name == "sodium-0.5.jar"


def test_separator_only_names_match_nothing(tmp_path):
    touch(tmp_path / "root" / "---.jar")
    touch(tmp_path / "root" / "abc.jar")
    assert finder.find_matches(sources_of("---.jar"), tmp_path / "root", 0) == []
    assert finder.find_matches(sources_of("abc.jar"), tmp_path / "root", 0)[0].path.name == "abc.jar"


def test_unicode_and_extensionless_names(tmp_path):
    touch(tmp_path / "root" / "Żółć-1.0.jar")
    touch(tmp_path / "root" / "LICENSE")
    matches = finder.find_matches(sources_of("żółć_1.0.JAR", "license"), tmp_path / "root")
    assert {m.path.name for m in matches} == {"Żółć-1.0.jar", "LICENSE"}


def test_source_file_inside_search_root_is_flagged(tmp_path):
    original = touch(tmp_path / "root" / "drop" / "x.jar")
    copy = touch(tmp_path / "root" / "mods" / "x.jar")
    sources = finder.collect_sources([tmp_path / "root" / "drop"])
    matches = finder.find_matches(sources, tmp_path / "root")
    flags = {m.path: m.is_source for m in matches}
    assert flags == {original: True, copy: False}


def test_empty_sources_returns_empty(tmp_path):
    touch(tmp_path / "root" / "x.jar")
    assert finder.find_matches([], tmp_path / "root") == []
