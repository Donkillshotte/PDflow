#!/usr/bin/env python3
"""Parse DRC .lyrdb and LVS .lvsdb / log for signoff UI summaries."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_lyrdb(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "items": 0, "categories": [], "samples": []}
    text = path.read_text(errors="replace")
    # KLayout lyrdb: count <item> elements (not <items> wrapper)
    items = len(re.findall(r"<item\b", text))
    categories: list[str] = []
    samples: list[dict] = []
    try:
        root = ET.fromstring(text)
        for cat in root.findall(".//category/name"):
            if cat.text and cat.text not in categories:
                categories.append(cat.text)
        for item in root.findall(".//items/item")[:8]:
            cat = item.find("category")
            cat_name = cat.text if cat is not None and cat.text else "?"
            vals = item.find("values")
            msg = ""
            if vals is not None:
                for v in vals.findall("value"):
                    if v.text:
                        msg = v.text[:120]
                        break
            samples.append({"category": cat_name, "detail": msg})
    except ET.ParseError:
        pass
    return {
        "exists": True,
        "items": items,
        "categories": categories[:12],
        "samples": samples,
        "path": str(path),
    }


def parse_lvsdb(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "errors": 0, "messages": []}
    text = path.read_text(errors="replace")
    if "LVS not supported" in text:
        return {"exists": True, "supported": False, "errors": 0, "messages": ["LVS not supported on platform"]}
    errors = len(re.findall(r"<error\b", text, flags=re.I))
    must_connect = len(re.findall(r"Must-connect", text))
    messages: list[str] = []
    for m in re.findall(r"<message[^>]*>([^<]+)", text)[:6]:
        messages.append(m.strip()[:160])
    if must_connect and not messages:
        for m in re.findall(r"Must-connect[^']{0,160}", text)[:4]:
            messages.append(m.strip())
    return {
        "exists": True,
        "supported": True,
        "errors": errors,
        "must_connect": must_connect,
        "messages": messages,
        "path": str(path),
    }


def parse_lvs_log(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "tail": []}
    lines = path.read_text(errors="replace").splitlines()
    tail = [ln for ln in lines[-15:] if ln.strip()]
    missing_lylvs = any("FreePDK45.lylvs" in ln or "No rule to make" in ln for ln in tail)
    blob = "\n".join(lines)
    matched = "Netlists match" in blob and "Netlists don't match" not in blob
    return {
        "exists": True,
        "tail": tail,
        "missing_lylvs": missing_lylvs,
        "netlists_match": matched,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["drc", "lvs"], required=True)
    ap.add_argument("--path", type=Path, required=True)
    ap.add_argument("--log", type=Path, help="LVS make log")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.kind == "drc":
        result = parse_lyrdb(args.path)
    else:
        result = {
            "lvsdb": parse_lvsdb(args.path),
            "log": parse_lvs_log(args.log) if args.log else {"exists": False},
        }
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
