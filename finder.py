from __future__ import annotations

import difflib
import os
import re
import send2trash
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

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


class SearchCancelled(Exception):
    pass


def find_matches(sources: Iterable[SourceFile], root: str | Path,
                 threshold: float = 85.0,
                 on_progress: Callable[[int], None] | None = None,
                 should_cancel: Callable[[], bool] | None = None,
                 progress_every: int = 200) -> list[Match]:
    sources = list(sources)
    source_keys = {_key(s.path) for s in sources}
    exact: dict[tuple[str, str], str] = {}
    for s in sources:
        ext, n = _split(s.name)
        if n:
            exact.setdefault((ext, n), s.name)
    norm_sources = [(ext, n, name) for (ext, n), name in exact.items()]

    matches: list[Match] = []
    scanned = 0
    reported: int | None = None
    for dirpath, _dirs, files in os.walk(root):
        for filename in files:
            if should_cancel is not None and should_cancel():
                raise SearchCancelled()
            scanned += 1
            if on_progress is not None and scanned % progress_every == 0:
                on_progress(scanned)
                reported = scanned
            ext, norm_file = _split(filename)
            if not norm_file:
                continue
            best = _best_source(ext, norm_file, exact, norm_sources, threshold)
            if best is None:
                continue
            path = Path(dirpath) / filename
            matches.append(Match(path, best[0], best[1], _key(path) in source_keys))
    if on_progress is not None and reported != scanned:
        on_progress(scanned)
    matches.sort(key=lambda m: (-m.score, str(m.path).casefold()))
    return matches


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


def drive_has_recycle_bin(path: str | Path) -> bool:
    drive = os.path.splitdrive(os.path.abspath(path))[0]
    if drive.startswith("\\\\") or drive.startswith("//"):
        return False
    try:
        import ctypes
        kind = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
    except Exception:
        return True
    return kind not in (2, 4)


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
        trash(os.path.abspath(path))


def delete_match(path: str | Path, root: str | Path, permanent: bool = False,
                 trash=send2trash.send2trash) -> DeleteResult:
    path = Path(path)
    if path.is_dir():
        raise IsADirectoryError(f"Nie usuwam folderów: {path}")
    emptied = folders_emptied_by(path, root) if path.exists() else []
    _remove(path, permanent, trash)
    removed: list[Path] = []
    for folder in emptied:
        try:
            if any(folder.iterdir()):
                break
            _remove(folder, permanent, trash)
        except OSError:
            break
        removed.append(folder)
    return DeleteResult(path, removed)
