"""Activity layer: VCD / SAIF → per-instance toggle density.

Does not invent an RTL→ITerm map. Missing waveforms stay missing; the
Dynamic IR oracle keeps its existing I(t) scale. Replaceable: point
`DSE_ACTIVITY` at a VCD or SAIF and this adapter fills `activity.json`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def activity_path(*, variant: str = "flowlab", design_id: str = "gcd") -> Path:
    env = os.environ.get("DSE_ACTIVITY")
    if env:
        return Path(env)
    root = REPO / "learn" / "sim" / "dse" / "activity"
    for name in (
        f"{design_id}_{variant}.saif",
        f"{design_id}_{variant}.vcd",
        f"{design_id}.saif",
        f"{design_id}.vcd",
    ):
        p = root / name
        if p.is_file():
            return p
    return root / f"{design_id}_{variant}.saif"


def load_activity(*, variant: str = "flowlab", design_id: str = "gcd") -> dict | None:
    """Parse SAIF TC / VCD 0↔1 edges. None when no waveform is on disk."""
    p = activity_path(variant=variant, design_id=design_id)
    if not p.is_file():
        return None
    text = p.read_text(errors="replace")
    if p.suffix.lower() == ".saif" or "(SAIFILE" in text[:200]:
        return _parse_saif(text, path=p)
    if p.suffix.lower() == ".vcd" or text.startswith("$date") or "$timescale" in text[:400]:
        return _parse_vcd(text, path=p)
    return None


def _parse_saif(text: str, *, path: Path) -> dict:
    toggles: dict[str, int] = {}
    inst = ""
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"INSTANCE\s+(\S+)", line, re.I)
        if m:
            inst = m.group(1).strip('"')
            continue
        tm = re.search(r"TC\s*\(?\s*(\d+)", line, re.I)
        if tm and inst:
            toggles[inst] = toggles.get(inst, 0) + int(tm.group(1))
    n = sum(toggles.values())
    dens = {k: (v / n if n else 0.0) for k, v in toggles.items()}
    return {
        "via": "saif_tc",
        "path": str(path),
        "n_inst": len(toggles),
        "n_toggle": n,
        "density": dens,
        "not": "an invented VCD remap / gold restamp",
    }


def _parse_vcd(text: str, *, path: Path) -> dict:
    id_to_net: dict[str, str] = {}
    edges: dict[str, int] = {}
    last: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("$var"):
            parts = line.split()
            if len(parts) >= 5:
                id_to_net[parts[3]] = parts[4]
            continue
        if not line or line[0] in ("$", "#"):
            continue
        if line[0] in "01xXzZ" and len(line) >= 2:
            val, sid = line[0].lower(), line[1:]
            net = id_to_net.get(sid, sid)
            prev = last.get(sid)
            if prev is not None and prev in "01" and val in "01" and prev != val:
                edges[net] = edges.get(net, 0) + 1
            last[sid] = val
    n = sum(edges.values())
    dens = {k: (v / n if n else 0.0) for k, v in edges.items()}
    return {
        "via": "vcd_edges",
        "path": str(path),
        "n_inst": len(edges),
        "n_toggle": n,
        "density": dens,
        "not": "an invented VCD remap / gold restamp",
    }


def persist_activity(report: dict, *, variant: str = "flowlab", design_id: str = "gcd") -> Path:
    dest = REPO / "learn" / "sim" / "dse" / "activity" / f"{design_id}_{variant}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2))
    return dest
