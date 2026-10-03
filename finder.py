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
