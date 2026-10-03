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
