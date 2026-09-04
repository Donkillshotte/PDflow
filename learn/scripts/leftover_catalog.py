"""Load the machine-readable leftover catalog for tests and stamp helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "learn/signoff/leftover_catalog.json"


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_items() -> list[dict[str, Any]]:
    return list(load_catalog().get("items") or [])


def catalog_ids() -> set[str]:
    return {str(item["id"]) for item in catalog_items() if item.get("id")}


def items_for_hook(hook_id: str) -> list[dict[str, Any]]:
    return [
        item
        for item in catalog_items()
        if hook_id in (item.get("suite_hooks") or [])
    ]


def home_compact_phrases() -> list[str]:
    return list(load_catalog().get("home_compact_phrases") or [])
