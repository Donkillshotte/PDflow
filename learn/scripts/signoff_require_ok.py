#!/usr/bin/env python3
"""Exit 0 only when a signoff report has ok: true.

Pillar scripts write JSON even on FAIL. The orchestrator used to key off
shell exit codes only, so a failed LVS/STA/DRC/power cook could still
print OK. Leftover must-connect does not flip ok — a named leftover on a
matching compare stays exit 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def report_ok(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing {path}"
    try:
        blob = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return False, f"{path.name} is not JSON: {exc}"
    summary = str(blob.get("summary") or path.name)
    if blob.get("ok") is True:
        return True, summary
    return False, f"{path.name} ok={blob.get('ok')} · {summary}"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: signoff_require_ok.py <report.json>", file=sys.stderr)
        return 2
    path = Path(args[0])
    ok, msg = report_ok(path)
    print(("OK" if ok else "FAIL") + " " + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
