"""Content hashes for RTL / netlist / knob vectors. Not a physical fingerprint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def knobs_fp(level: str, knobs: dict) -> str:
    blob = json.dumps({"level": level, "knobs": knobs}, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)
