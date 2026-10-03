# Mod Deleter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Okienkowy program na Windows, który z wrzuconych folderów/plików bierze nazwy plików, szuka w wybranym folderze plików o takiej samej lub bardzo podobnej nazwie, pyta o usunięcie każdego trafienia i usuwa też foldery, które po tym zostały puste.

**Architecture:** Logika bez GUI w `finder.py` (zbieranie nazw, dopasowanie, usuwanie), cienkie okno tkinter w `app.py` korzystające tylko z publicznego API `finder`. Dystrybucja jako jeden `ModDeleter.exe` zbudowany PyInstallerem.

**Tech Stack:** Python 3.11, tkinter, `tkinterdnd2`, `send2trash`, `pytest`, `pyinstaller`.

**Spec:** `docs/superpowers/specs/2026-10-03-mod-deleter-design.md`

**Uwaga o git:** katalog projektu nie jest repozytorium git, więc plan nie zawiera kroków commit. Jeśli repozytorium zostanie założone, commit po każdym zadaniu.

## Global Constraints

- Platforma: Windows 10, Python 3.11.
- Wszystkie ścieżki obsługiwane przez `pathlib.Path`; porównania ścieżek przez `os.path.normcase(os.path.abspath(...))`.
- Celami usuwania są wyłącznie pliki; folder jest usuwany tylko wtedy, gdy jest całkowicie pusty (ukryte pliki liczą się jako zawartość).
- Folder główny wybrany do przeszukania i foldery powyżej niego nigdy nie są usuwane.
- Dopasowanie: rozszerzenie musi być identyczne (`casefold`; brak rozszerzenia pasuje tylko do braku rozszerzenia); nazwa bez rozszerzenia: `casefold`, separatory `-`, `_`, `.`, spacja ujednolicone do jednej spacji; podobieństwo `difflib.SequenceMatcher`, wynik 0–100; próg domyślny 85.
- Domyślnie usuwanie do Kosza (`send2trash`); „usuń trwale” to opcja w oknie z dodatkowym potwierdzeniem.
- Nic nie jest usuwane bez kliknięcia „Usuń” przy konkretnym trafieniu.
- Teksty w interfejsie po polsku.

## Review Focus

1. Nazwa złożona tylko z separatorów (np. `---.jar`) normalizuje się do pustego tekstu i nie może pasować do niczego ani do wszystkiego (Task 2).
2. Pliki o tej samej nazwie i różnych rozszerzeniach (`sodium.jar`, `sodium.txt`) nie mogą do siebie pasować, a rozszerzenie pisane inną wielkością liter (`.JAR`) musi pasować (Task 1, Task 2).
3. Nazwy z polskimi znakami (`Żółć-1.0.jar`) i plik bez rozszerzenia (`LICENSE`) muszą się dopasowywać normalnie (Task 2).
4. Folder wrzucony leży wewnątrz przeszukiwanego, albo ten sam plik podano dwa razy: trafienie oznaczone jako plik wzorcowy, a lista źródeł bez duplikatów (Task 1, Task 2).
5. Między podglądem a usunięciem w folderze pojawił się nowy plik, albo plik zniknął lub jest katalogiem: folder nie może zostać usunięty, a błąd nie może przerwać pracy ani skasować katalogu (Task 3, Task 4).

---

## File Structure

- `finder.py` — cała logika: `normalize`, `similarity`, `SourceFile`, `collect_sources`, `Match`, `find_matches`, `folders_emptied_by`, `DeleteResult`, `delete_match`.
- `app.py` — okno tkinter (`App`, `main`).
- `tests/test_finder.py` — testy logiki.
- `tests/test_app_smoke.py` — test dymny okna.
- `pytest.ini`, `requirements.txt`, `requirements-dev.txt`, `build.bat`.

---

### Task 1: Szkielet projektu, normalizacja, podobieństwo, zbieranie nazw

**Files:**
- Create: `pytest.ini`, `requirements.txt`, `requirements-dev.txt`
- Create: `finder.py`
- Create: `tests/test_finder.py`

**Interfaces:**
- Produces:
  - `normalize(filename: str) -> str`
  - `similarity(a: str, b: str) -> float` (0–100, argumenty to nazwy plików)
  - `@dataclass(frozen=True) SourceFile(name: str, path: Path)`
  - `collect_sources(paths: Iterable[str | Path]) -> list[SourceFile]` (bez duplikatów, posortowane po `name.casefold()` i ścieżce)
  - `_key(path) -> str` (znormalizowany klucz ścieżki, używany dalej)

- [ ] **Step 1: Pliki konfiguracyjne i zależności**

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

`requirements.txt`:
```
tkinterdnd2
send2trash
pyinstaller
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
```

Run: `python -m pip install -r requirements-dev.txt`
Expected: instalacja kończy się bez błędów.

- [ ] **Step 2: Napisz testy, które nie przechodzą**

`tests/test_finder.py`:
```python
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
```

- [ ] **Step 3: Uruchom testy, upewnij się że padają**

Run: `python -m pytest tests/test_finder.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'finder'`).

- [ ] **Step 4: Minimalna implementacja**

`finder.py`:
```python
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_SEPARATORS = re.compile(r"[\s._\-]+")


def _key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def normalize(filename: str) -> str:
    stem = Path(filename).stem
    return _SEPARATORS.sub(" ", stem.casefold()).strip()


def similarity(a: str, b: str) -> float:
    if Path(a).suffix.casefold() != Path(b).suffix.casefold():
        return 0.0
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    return difflib.SequenceMatcher(None, na, nb).ratio() * 100


@dataclass(frozen=True)
class SourceFile:
    name: str
    path: Path


def collect_sources(paths: Iterable[str | Path]) -> list[SourceFile]:
    found: dict[str, SourceFile] = {}
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            found[_key(p)] = SourceFile(p.name, p)
        elif p.is_dir():
            for dirpath, _dirs, files in os.walk(p):
                for name in files:
                    fp = Path(dirpath) / name
                    found[_key(fp)] = SourceFile(name, fp)
    return sorted(found.values(), key=lambda s: (s.name.casefold(), str(s.path)))
```

- [ ] **Step 5: Uruchom testy, upewnij się że przechodzą**

Run: `python -m pytest tests/test_finder.py -v`
Expected: wszystkie testy PASS.

---

### Task 2: Wyszukiwanie dopasowań

**Files:**
- Modify: `finder.py` (dopisz na końcu)
- Modify: `tests/test_finder.py` (dopisz na końcu)

**Interfaces:**
- Consumes: `normalize`, `SourceFile`, `_key` z Task 1.
- Produces:
  - `@dataclass(frozen=True) Match(path: Path, score: float, source_name: str, is_source: bool)`
  - `find_matches(sources: Iterable[SourceFile], root: str | Path, threshold: float = 85.0) -> list[Match]` (posortowane malejąco po `score`, potem po `str(path).casefold()`; tylko pliki; jeden `Match` na plik z najlepszym wynikiem)

- [ ] **Step 1: Napisz testy, które nie przechodzą**

Dopisz do `tests/test_finder.py`:
```python
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
```

- [ ] **Step 2: Uruchom testy, upewnij się że padają**

Run: `python -m pytest tests/test_finder.py -v -k "find or match or fuzzy or sorted or unicode or flagged or empty_sources or separator_only"`
Expected: FAIL (`AttributeError: module 'finder' has no attribute 'find_matches'`).

- [ ] **Step 3: Implementacja**

Dopisz do `finder.py`:
```python
@dataclass(frozen=True)
class Match:
    path: Path
    score: float
    source_name: str
    is_source: bool


def _split(name: str) -> tuple[str, str]:
    return Path(name).suffix.casefold(), normalize(name)


def _best_source(ext: str, norm_file: str, exact: dict[tuple[str, str], str],
                 sources: list[tuple[str, str, str]],
                 threshold: float) -> tuple[float, str] | None:
    if (ext, norm_file) in exact:
        return 100.0, exact[(ext, norm_file)]
    matcher = difflib.SequenceMatcher(None)
    matcher.set_seq2(norm_file)
    best_score, best_name = 0.0, ""
    for source_ext, norm_source, name in sources:
        if source_ext != ext:
            continue
        matcher.set_seq1(norm_source)
        cutoff = max(threshold, best_score) / 100
        if matcher.real_quick_ratio() < cutoff or matcher.quick_ratio() < cutoff:
            continue
        score = matcher.ratio() * 100
        if score >= threshold and score > best_score:
            best_score, best_name = score, name
    return (best_score, best_name) if best_name else None


def find_matches(sources: Iterable[SourceFile], root: str | Path,
                 threshold: float = 85.0) -> list[Match]:
    sources = list(sources)
    source_keys = {_key(s.path) for s in sources}
    exact: dict[tuple[str, str], str] = {}
    for s in sources:
        ext, n = _split(s.name)
        if n:
            exact.setdefault((ext, n), s.name)
    norm_sources = [(ext, n, name) for (ext, n), name in exact.items()]

    matches: list[Match] = []
    for dirpath, _dirs, files in os.walk(root):
        for filename in files:
            ext, norm_file = _split(filename)
            if not norm_file:
                continue
            best = _best_source(ext, norm_file, exact, norm_sources, threshold)
            if best is None:
                continue
            path = Path(dirpath) / filename
            matches.append(Match(path, best[0], best[1], _key(path) in source_keys))
    matches.sort(key=lambda m: (-m.score, str(m.path).casefold()))
    return matches
```

- [ ] **Step 4: Uruchom wszystkie testy**

Run: `python -m pytest tests/test_finder.py -v`
Expected: wszystkie testy PASS.

---

### Task 3: Usuwanie pliku i pustych folderów

**Files:**
- Modify: `finder.py` (dopisz importy i funkcje)
- Modify: `tests/test_finder.py` (dopisz na końcu)

**Interfaces:**
- Consumes: `_key` z Task 1.
- Produces:
  - `folders_emptied_by(path: str | Path, root: str | Path) -> list[Path]` — foldery (od najgłębszego w górę), które staną się puste po usunięciu `path`; nigdy nie zawiera `root` ani folderów powyżej.
  - `@dataclass(frozen=True) DeleteResult(file: Path, removed_folders: list[Path])`
  - `delete_match(path, root, permanent: bool = False, trash=send2trash.send2trash) -> DeleteResult` — rzuca `IsADirectoryError`, gdy `path` jest katalogiem, i `OSError` przy innych błędach.

- [ ] **Step 1: Napisz testy, które nie przechodzą**

Dopisz do `tests/test_finder.py`:
```python
import os


def test_delete_removes_file_keeps_nonempty_folder(tmp_path):
    target = touch(tmp_path / "root" / "a" / "x.jar")
    touch(tmp_path / "root" / "a" / "other.jar")
    result = finder.delete_match(target, tmp_path / "root", permanent=True)
    assert not target.exists()
    assert (tmp_path / "root" / "a" / "other.jar").exists()
    assert result.removed_folders == []


def test_delete_removes_empty_folders_up_to_but_not_including_root(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "b" / "c" / "x.jar")
    result = finder.delete_match(target, root, permanent=True)
    assert [p.name for p in result.removed_folders] == ["c", "b", "a"]
    assert root.exists()
    assert list(root.iterdir()) == []


def test_delete_stops_at_first_nonempty_parent(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "b" / "x.jar")
    touch(root / "a" / "keep.txt")
    result = finder.delete_match(target, root, permanent=True)
    assert [p.name for p in result.removed_folders] == ["b"]
    assert (root / "a" / "keep.txt").exists()


def test_hidden_file_keeps_folder(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "x.jar")
    touch(root / "a" / ".hidden")
    finder.delete_match(target, root, permanent=True)
    assert (root / "a").exists()


def test_sibling_subfolder_keeps_folder(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "x.jar")
    (root / "a" / "sub").mkdir()
    finder.delete_match(target, root, permanent=True)
    assert (root / "a" / "sub").exists()


def test_file_directly_in_root_never_removes_root(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "x.jar")
    result = finder.delete_match(target, root, permanent=True)
    assert result.removed_folders == []
    assert root.exists()


def test_folders_emptied_by_previews_without_deleting(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "b" / "x.jar")
    preview = finder.folders_emptied_by(target, root)
    assert [p.name for p in preview] == ["b", "a"]
    assert target.exists()


def test_refuses_to_delete_a_directory(tmp_path):
    root = tmp_path / "root"
    folder = root / "a"
    folder.mkdir(parents=True)
    with pytest.raises(IsADirectoryError):
        finder.delete_match(folder, root, permanent=True)
    assert folder.exists()


def test_delete_missing_file_raises_oserror(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(OSError):
        finder.delete_match(root / "nope.jar", root, permanent=True)


def test_folder_that_gained_a_file_after_preview_is_kept(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "x.jar")
    calls = []

    def racing_trash(p):
        calls.append(p)
        os.remove(p)
        touch(root / "a" / "new.txt")

    result = finder.delete_match(target, root, permanent=False, trash=racing_trash)
    assert (root / "a" / "new.txt").exists()
    assert result.removed_folders == []
    assert len(calls) == 1


def test_trash_mode_sends_file_and_empty_folders_to_trash(tmp_path):
    root = tmp_path / "root"
    target = touch(root / "a" / "x.jar")
    trashed = []

    def fake_trash(p):
        trashed.append(Path(p).name)
        if os.path.isdir(p):
            os.rmdir(p)
        else:
            os.remove(p)

    result = finder.delete_match(target, root, permanent=False, trash=fake_trash)
    assert trashed == ["x.jar", "a"]
    assert [p.name for p in result.removed_folders] == ["a"]
```

- [ ] **Step 2: Uruchom testy, upewnij się że padają**

Run: `python -m pytest tests/test_finder.py -v -k "delete or emptied or hidden or sibling or trash or directory or gained"`
Expected: FAIL (`AttributeError: ... 'delete_match'`).

- [ ] **Step 3: Implementacja**

Na górze `finder.py` dodaj `import send2trash` (po `import re`). Dopisz na końcu:
```python
def _inside(child: str | Path, root: str | Path) -> bool:
    c, r = _key(child), _key(root)
    if c == r:
        return False
    try:
        return os.path.commonpath([c, r]) == r
    except ValueError:
        return False


def folders_emptied_by(path: str | Path, root: str | Path) -> list[Path]:
    emptied: list[Path] = []
    gone = Path(path)
    current = gone.parent
    while _inside(current, root):
        remaining = [c for c in current.iterdir() if _key(c) != _key(gone)]
        if remaining:
            break
        emptied.append(current)
        gone = current
        current = current.parent
    return emptied


@dataclass(frozen=True)
class DeleteResult:
    file: Path
    removed_folders: list[Path]


def _remove(path: Path, permanent: bool, trash) -> None:
    if permanent:
        if path.is_dir():
            os.rmdir(path)
        else:
            os.remove(path)
    else:
        trash(str(path.resolve()))


def delete_match(path: str | Path, root: str | Path, permanent: bool = False,
                 trash=send2trash.send2trash) -> DeleteResult:
    path = Path(path)
    if path.is_dir():
        raise IsADirectoryError(f"Nie usuwam folderów: {path}")
    emptied = folders_emptied_by(path, root) if path.exists() else []
    _remove(path, permanent, trash)
    removed: list[Path] = []
    for folder in emptied:
        if any(folder.iterdir()):
            break
        _remove(folder, permanent, trash)
        removed.append(folder)
    return DeleteResult(path, removed)
```

Uwaga: dla nieistniejącego pliku `os.remove` rzuca `FileNotFoundError` (podklasa `OSError`), co spełnia test; w trybie Kosza `send2trash` też rzuca `OSError`.

- [ ] **Step 4: Uruchom wszystkie testy**

Run: `python -m pytest tests/test_finder.py -v`
Expected: wszystkie testy PASS.

---

### Task 4: Okno aplikacji

**Files:**
- Create: `app.py`
- Create: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: z `finder`: `collect_sources`, `SourceFile`, `find_matches`, `Match`, `folders_emptied_by`, `delete_match`, `_key`.
- Produces: `App(root)` z metodami używanymi w teście dymnym: `add_paths(paths)`, `set_search_root(path)`, `start_search()`, `delete_current()`, `skip_current()`, atrybuty `matches`, `index`, `deleted`, `permanent` (`tk.BooleanVar`), `threshold` (`tk.IntVar`); `main()`.

- [ ] **Step 1: Napisz test dymny, który nie przechodzi**

`tests/test_app_smoke.py`:
```python
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
```

- [ ] **Step 2: Uruchom test, upewnij się że pada**

Run: `python -m pytest tests/test_app_smoke.py -v`
Expected: SKIP lub FAIL z powodu braku modułu `app` (`importorskip` pomija test). Jeśli test został pominięty, sprawdź komunikat — to oznacza brak `app.py`, co jest oczekiwane na tym etapie.

- [ ] **Step 3: Implementacja okna**

`app.py`:
```python
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

import finder


class App:
    def __init__(self, root: tk.Misc):
        self.root = root
        root.title("Mod Deleter")
        root.geometry("860x700")

        self.sources: dict[str, finder.SourceFile] = {}
        self.checked: dict[str, bool] = {}
        self.search_root: Path | None = None
        self.matches: list[finder.Match] = []
        self.index = 0
        self.deleted = 0
        self.last_error = ""

        self.permanent = tk.BooleanVar(value=False)
        self.threshold = tk.IntVar(value=85)
        self.status = tk.StringVar(value="")
        self.root_label = tk.StringVar(value="(nie wybrano folderu)")
        self.counter = tk.StringVar(value="")
        self.match_path = tk.StringVar(value="")
        self.match_info = tk.StringVar(value="")
        self.warning = tk.StringVar(value="")

        self._build()
        self._set_review_enabled(False)

    # ---------- budowa okna ----------
    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        src = ttk.LabelFrame(self.root, text="1. Czego szukam (przeciągnij tu foldery lub pliki)")
        src.pack(fill="both", expand=True, **pad)
        self.tree = ttk.Treeview(src, columns=("use", "name", "from"), show="headings", height=8)
        self.tree.heading("use", text="Szukaj")
        self.tree.heading("name", text="Nazwa pliku")
        self.tree.heading("from", text="Pochodzi z")
        self.tree.column("use", width=60, anchor="center", stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("from", width=420)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Button-1>", self._on_tree_click)
        row = ttk.Frame(src)
        row.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(row, text="Dodaj pliki…", command=self._pick_files).pack(side="left")
        ttk.Button(row, text="Dodaj folder…", command=self._pick_source_folder).pack(side="left", padx=6)
        ttk.Button(row, text="Wyczyść listę", command=self.clear_sources).pack(side="left")
        for widget in (self.tree, src):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

        where = ttk.LabelFrame(self.root, text="2. Gdzie szukam")
        where.pack(fill="x", **pad)
        row = ttk.Frame(where)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Button(row, text="Wybierz folder…", command=self._pick_search_root).pack(side="left")
        ttk.Label(row, textvariable=self.root_label).pack(side="left", padx=10)
        row = ttk.Frame(where)
        row.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(row, text="Podobieństwo nazwy (min. %):").pack(side="left")
        tk.Scale(row, from_=50, to=100, orient="horizontal", variable=self.threshold,
                 length=260).pack(side="left", padx=8)
        ttk.Button(row, text="Szukaj", command=self.start_search).pack(side="right")

        rev = ttk.LabelFrame(self.root, text="3. Trafienia")
        rev.pack(fill="x", **pad)
        ttk.Label(rev, textvariable=self.counter).pack(anchor="w", padx=6, pady=(6, 0))
        ttk.Label(rev, textvariable=self.match_path, wraplength=800,
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6)
        ttk.Label(rev, textvariable=self.match_info).pack(anchor="w", padx=6)
        tk.Label(rev, textvariable=self.warning, fg="#b00020", wraplength=800,
                 justify="left").pack(anchor="w", padx=6)
        row = ttk.Frame(rev)
        row.pack(fill="x", padx=6, pady=6)
        self.btn_delete = ttk.Button(row, text="Usuń", command=self.delete_current)
        self.btn_skip = ttk.Button(row, text="Pomiń", command=self.skip_current)
        self.btn_stop = ttk.Button(row, text="Zakończ", command=self.finish)
        for b in (self.btn_delete, self.btn_skip, self.btn_stop):
            b.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(row, text="Usuń trwale (bez Kosza)", variable=self.permanent).pack(side="right")
        ttk.Label(self.root, textvariable=self.status).pack(anchor="w", padx=12, pady=(0, 8))

    # ---------- lista źródeł ----------
    def _on_drop(self, event) -> None:
        self.add_paths(self.root.tk.splitlist(event.data))

    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Wybierz pliki")
        if paths:
            self.add_paths(paths)

    def _pick_source_folder(self) -> None:
        path = filedialog.askdirectory(title="Wybierz folder ze wzorcami")
        if path:
            self.add_paths([path])

    def add_paths(self, paths) -> None:
        for source in finder.collect_sources(paths):
            key = finder._key(source.path)
            if key not in self.sources:
                self.sources[key] = source
                self.checked[key] = True
        self._refresh_tree()
        self.status.set(f"Na liście: {len(self.sources)} nazw plików.")

    def clear_sources(self) -> None:
        self.sources.clear()
        self.checked.clear()
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        ordered = sorted(self.sources.items(), key=lambda kv: kv[1].name.casefold())
        for key, source in ordered:
            mark = "☑" if self.checked[key] else "☐"
            self.tree.insert("", "end", iid=key, values=(mark, source.name, str(source.path.parent)))

    def _on_tree_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        key = self.tree.identify_row(event.y)
        if key:
            self.checked[key] = not self.checked[key]
            self.tree.set(key, "use", "☑" if self.checked[key] else "☐")

    # ---------- wybór folderu i szukanie ----------
    def _pick_search_root(self) -> None:
        path = filedialog.askdirectory(title="Wybierz folder do przeszukania")
        if path:
            self.set_search_root(path)

    def set_search_root(self, path) -> None:
        self.search_root = Path(path)
        self.root_label.set(str(self.search_root))

    def start_search(self) -> None:
        chosen = [s for k, s in self.sources.items() if self.checked.get(k)]
        if not chosen:
            messagebox.showinfo("Mod Deleter", "Lista „Czego szukam” jest pusta lub nic nie jest zaznaczone.")
            return
        if self.search_root is None or not self.search_root.is_dir():
            messagebox.showinfo("Mod Deleter", "Najpierw wybierz folder do przeszukania.")
            return
        self.matches = finder.find_matches(chosen, self.search_root, float(self.threshold.get()))
        self.index = 0
        self.deleted = 0
        self.last_error = ""
        if not self.matches:
            self.status.set("Nie znaleziono pasujących plików.")
            self._clear_review()
            return
        self.status.set(f"Znaleziono trafień: {len(self.matches)}.")
        self._show_current()

    # ---------- przegląd trafień ----------
    def _set_review_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in (self.btn_delete, self.btn_skip, self.btn_stop):
            b.configure(state=state)

    def _clear_review(self) -> None:
        self.counter.set("")
        self.match_path.set("")
        self.match_info.set("")
        self.warning.set("")
        self._set_review_enabled(False)

    def _show_current(self) -> None:
        if self.index >= len(self.matches):
            self.finish()
            return
        match = self.matches[self.index]
        self.counter.set(f"Trafienie {self.index + 1} z {len(self.matches)}")
        self.match_path.set(str(match.path))
        self.match_info.set(f"Podobieństwo: {match.score:.0f}%   |   szukana nazwa: {match.source_name}")
        notes = []
        if match.is_source:
            notes.append("UWAGA: to jest plik wzorcowy, z którego pobrano nazwę.")
        emptied = finder.folders_emptied_by(match.path, self.search_root)
        if emptied:
            names = ", ".join(str(p) for p in emptied)
            notes.append(f"Po usunięciu zostaną też usunięte puste foldery: {names}")
        self.warning.set("\n".join(notes))
        self._set_review_enabled(True)

    def delete_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        match = self.matches[self.index]
        permanent = self.permanent.get()
        if permanent and not messagebox.askyesno(
                "Usuń trwale", f"Usunąć trwale, bez Kosza?\n\n{match.path}"):
            return
        try:
            result = finder.delete_match(match.path, self.search_root, permanent=permanent)
        except OSError as exc:
            self.last_error = f"Nie udało się usunąć {match.path.name}: {exc}"
            self.status.set(self.last_error)
            self.index += 1
            self._show_current()
            return
        self.deleted += 1
        extra = f" (+ {len(result.removed_folders)} pustych folderów)" if result.removed_folders else ""
        self.status.set(f"Usunięto: {match.path.name}{extra}")
        self.index += 1
        self._show_current()

    def skip_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        self.index += 1
        self._show_current()

    def finish(self) -> None:
        summary = f"Koniec. Usunięto plików: {self.deleted}."
        if self.last_error:
            summary += f"  Ostatni błąd: {self.last_error}"
        self.status.set(summary)
        self.matches = []
        self._clear_review()


def main() -> None:
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Uruchom wszystkie testy**

Run: `python -m pytest -v`
Expected: testy `finder` PASS; testy okna PASS (jeśli środowisko graficzne dostępne) albo SKIP z jawnym komunikatem. Test `test_delete_error_does_not_crash` sprawdza, że status zawiera „zablokowany”.

- [ ] **Step 5: Ręczny test okna**

Run: `python app.py`
Sprawdź: przeciągnij folder na listę, zaznacz/odznacz pozycję kliknięciem w kolumnę „Szukaj”, wybierz folder do przeszukania, kliknij „Szukaj”, przejdź przez trafienia przyciskami Usuń/Pomiń. Użyj tymczasowych folderów testowych, nie prawdziwych modów.

---

### Task 5: Budowanie pliku `.exe`

**Files:**
- Create: `build.bat`

**Interfaces:**
- Consumes: `app.py`, `requirements.txt`.
- Produces: `dist\ModDeleter.exe`.

- [ ] **Step 1: Napisz skrypt budowania**

`build.bat`:
```bat
@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt || exit /b 1
python -m PyInstaller --noconfirm --onefile --windowed --name ModDeleter --collect-all tkinterdnd2 app.py || exit /b 1
echo.
echo Gotowe: dist\ModDeleter.exe
```

- [ ] **Step 2: Zbuduj**

Run: `build.bat`
Expected: kończy się wierszem „Gotowe: dist\ModDeleter.exe”, plik `dist\ModDeleter.exe` istnieje.

- [ ] **Step 3: Sprawdź, że `.exe` startuje**

Run (PowerShell):
```powershell
$p = Start-Process -FilePath "dist\ModDeleter.exe" -PassThru
Start-Sleep -Seconds 4
if ($p.HasExited) { "BŁĄD: proces zakończył się, kod $($p.ExitCode)" } else { "OK: okno działa"; Stop-Process -Id $p.Id }
```
Expected: „OK: okno działa”. Jeśli proces się zakończył, uruchom `python -m PyInstaller` bez `--windowed`, żeby zobaczyć błąd (zwykle brakujące pliki `tkdnd`).

- [ ] **Step 4: Ręczny test przeciągania w `.exe`**

Uruchom `dist\ModDeleter.exe`, przeciągnij tymczasowy folder na listę i potwierdź, że nazwy się pojawiają (to sprawdza, że binaria `tkdnd` zostały dołączone).
