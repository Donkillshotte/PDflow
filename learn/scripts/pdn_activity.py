#!/usr/bin/env python3
"""Replaceable activity layer: when each ITerm switches.

Default: synthetic clock / spatial / simultaneous t50.
STA arrivals (OpenSTA report_arrival) overwrite t50 by instance name.
VCD/SAIF/FSDB join by hierarchical name only — never a silent RTL→ITerm map.
SAIF TC=0 idle-zeros the pulse; TC does not invent t50 or rescale I_avg.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

COORD_RE = re.compile(r"(ITermNode|Node)_metal(\d+)_(-?\d+)_(-?\d+)")
TS_RE = re.compile(r"\$timescale\s+([0-9.]+)\s*([fpnum]?s)", re.I)
VAR_RE = re.compile(r"\$var\s+\S+\s+\d+\s+(\S+)\s+(\S+)")


def node_xy(name: str) -> tuple[float, float] | None:
    m = COORD_RE.search(name)
    if not m:
        return None
    return float(m.group(3)), float(m.group(4))


def norm_inst(name: str | None) -> str:
    """ODB Verilog escapes `\\[` — STA does not. Join on the unescaped name."""
    if not name:
        return ""
    return str(name).replace("\\", "")


def load_insts(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    blob = json.loads(path.read_text())
    return blob.get("insts") or []


def nearest_inst(x: float, y: float, insts: list[dict], max_dbu: float = 4000.0):
    """Nearest non-filler instance. Default 4000 dbu = 2 µm at 2000 dbu/µm.

    write_pg_spice ITerm nodes are VDD pins, not the instance origin.
    On Nangate45 GCD that offset is ~1.0–1.6 µm — 800 dbu matched nothing
    and clock mode never saw a flip-flop.
    """
    best = None
    best_d = max_dbu
    for inst in insts:
        if inst.get("filler"):
            continue
        d = math.hypot(float(inst["x"]) - x, float(inst["y"]) - y)
        if d < best_d:
            best_d = d
            best = inst
    return best


def _timescale_s(num: float, unit: str) -> float:
    u = unit.lower()
    scale = {"fs": 1e-15, "ps": 1e-12, "ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}
    return float(num) * scale.get(u, 1e-12)


def parse_vcd(path: Path) -> dict:
    """IEEE VCD → {hier_name: first 0↔1 time in seconds}. Scopes become inst keys."""
    text = Path(path).read_text(errors="replace")
    ts = 1e-12
    mts = TS_RE.search(text)
    if mts:
        ts = _timescale_s(float(mts.group(1)), mts.group(2))
    scopes: list[str] = []
    id_to_hier: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("$scope"):
            parts = s.split()
            if len(parts) >= 3:
                scopes.append(parts[2])
        elif s.startswith("$upscope"):
            if scopes:
                scopes.pop()
        elif s.startswith("$var"):
            vm = VAR_RE.search(s)
            if not vm:
                continue
            sid, nm = vm.group(1), vm.group(2)
            hier = ".".join(scopes + [nm])
            id_to_hier[sid] = hier
            id_to_name[sid] = "/".join(scopes) if scopes else nm
    prev: dict[str, str] = {}
    first_edge: dict[str, float] = {}
    t = 0.0
    in_dump = False
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("$dumpvars") or s.startswith("$dumpon"):
            in_dump = True
            continue
        if s.startswith("$end"):
            in_dump = False
            continue
        if s.startswith("$"):
            continue
        if s.startswith("#"):
            try:
                t = float(s[1:]) * ts
            except ValueError:
                pass
            continue
        sid = None
        val = None
        if s[0] in "01xzXZ" and len(s) >= 2:
            val, sid = s[0].lower(), s[1:]
        elif s[0] in "bBrR" and " " in s:
            left, sid = s.split(None, 1)
            val = left[1:].lower()[:1] or "x"
        if not sid or sid not in id_to_hier:
            continue
        if in_dump:
            prev[sid] = val or "x"
            continue
        old = prev.get(sid)
        prev[sid] = val or "x"
        if old in ("0", "1") and val in ("0", "1") and old != val:
            hier = id_to_hier[sid]
            if hier not in first_edge:
                first_edge[hier] = t
            inst = id_to_name.get(sid) or ""
            if inst and inst not in first_edge:
                first_edge[inst] = t
    return {"timescale_s": ts, "n_signals": len(id_to_hier), "first_edge_s": first_edge}


def load_sta_arrivals(path: Path | None) -> dict:
    if path is None or not Path(path).is_file():
        return {}
    blob = json.loads(Path(path).read_text())
    by = blob.get("by_inst") or {}
    out = {}
    for k, rec in by.items():
        out[norm_inst(k)] = rec
    return out


def load_sta_path(path: Path | None) -> dict | None:
    """Worst max path from the same OpenSTA arrivals JSON. None if missing."""
    if path is None or not Path(path).is_file():
        return None
    blob = json.loads(Path(path).read_text())
    wp = blob.get("worst_path")
    if not wp or not wp.get("stages"):
        return None
    return wp


def apply_sta_t50(events: list[dict], arrivals: dict, period_s: float) -> dict:
    """Overwrite t50 from OpenSTA rise (else fall) arrival, folded into one period."""
    n = 0
    for ev in events:
        rec = arrivals.get(norm_inst(ev.get("inst")))
        if not rec:
            rec = hier_lookup(ev.get("inst"), arrivals)
        if not rec:
            continue
        t_ns = rec.get("rise_ns")
        if t_ns is None:
            t_ns = rec.get("fall_ns")
        if t_ns is None:
            continue
        t = float(t_ns) * 1e-9
        if period_s > 0:
            t = t % period_s
        ev["t50_s"] = t
        ev["t50_via"] = "sta_arrival"
        ev["sta_pin"] = rec.get("full") or rec.get("pin")
        n += 1
    return {
        "status": "READY" if n else "GAP",
        "n_applied": n,
        "n_events": len(events),
        "via": "OpenSTA report_arrival rise (folded into the SDC period)",
    }


def t50_via_counts(events: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {"synthetic": 0, "sta_arrival": 0, "vcd_name_join": 0}
    for ev in events:
        k = str(ev.get("t50_via") or "synthetic")
        out[k] = out.get(k, 0) + 1
    return out


def hier_lookup(inst: str | None, table: dict):
    """Join ODB instance name to a hierarchical key. No silent RTL→ITerm map."""
    inst_n = norm_inst(inst)
    if not inst_n or not table:
        return None
    keyed = {norm_inst(k).replace("/", "."): v for k, v in table.items()}
    inst_flat = inst_n.replace("/", ".")
    if inst_flat in keyed:
        return keyed[inst_flat]
    inst_last = inst_flat.split(".")[-1]
    for kk, vv in keyed.items():
        if kk.endswith("." + inst_flat):
            return vv
        last = kk.split(".")[-1]
        if last == inst_flat or last == inst_last:
            return vv
    return None


def vcd_edge_time(inst: str | None, edges: dict[str, float]) -> float | None:
    """Join ODB instance name to a VCD hier/scope key. No silent RTL→ITerm map."""
    t = hier_lookup(inst, edges)
    return None if t is None else float(t)


def apply_vcd_t50(events: list[dict], vcd: dict, period_s: float) -> dict:
    """Overwrite t50 only when VCD hier/inst names match the ODB instance."""
    edges = vcd.get("first_edge_s") or {}
    if not edges:
        return {"status": "GAP", "n_matched": 0, "n_events": len(events), "via": "no VCD edges"}
    n = 0
    for ev in events:
        t = vcd_edge_time(ev.get("inst"), edges)
        if t is None:
            continue
        if period_s > 0:
            t = t % period_s
        ev["t50_s"] = t
        ev["t50_via"] = "vcd_name_join"
        n += 1
    return {
        "status": "READY" if n else "GAP",
        "n_matched": n,
        "n_events": len(events),
        "n_vcd_edges": len(edges),
        "via": "VCD first 0↔1 edge joined by instance name (no silent RTL map)",
    }


_SAIF_ATOM = re.compile(r'"[^"]*"|[()]|[^\s()]+')


def _saif_atom(tok: str) -> str:
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return tok[1:-1]
    return tok


def _saif_tree(tokens: list[str]):
    i = 0
    n = len(tokens)

    def parse():
        nonlocal i
        if i >= n:
            return None
        if tokens[i] != "(":
            v = _saif_atom(tokens[i])
            i += 1
            return v
        i += 1
        items = []
        while i < n and tokens[i] != ")":
            items.append(parse())
        if i < n and tokens[i] == ")":
            i += 1
        return items

    roots = []
    while i < n:
        if tokens[i] == "(":
            roots.append(parse())
        else:
            i += 1
    if len(roots) == 1:
        return roots[0]
    return roots


def _saif_timescale(node: list) -> float | None:
    if len(node) >= 3:
        try:
            return _timescale_s(float(node[1]), str(node[2]))
        except (TypeError, ValueError):
            pass
    if len(node) >= 2:
        raw = str(node[1]).strip()
        m = re.match(r"^([0-9.]+)\s*([fpnum]?s)$", raw, re.I)
        if m:
            return _timescale_s(float(m.group(1)), m.group(2))
    return None


def _saif_net_tc(net) -> int:
    if not isinstance(net, list) or len(net) < 2:
        return 0
    for item in net[1:]:
        if isinstance(item, list) and item and str(item[0]).upper() == "TC":
            try:
                return int(float(item[1]))
            except (IndexError, TypeError, ValueError):
                return 0
    return 0


def parse_saif(path: Path) -> dict:
    """IEEE SAIF → instance-path toggle counts. Does not invent edge times."""
    text = Path(path).read_text(errors="replace")
    tree = _saif_tree(_SAIF_ATOM.findall(text))
    timescale_s = 1e-12
    duration_units = None
    toggle: dict[str, int] = {}
    n_nets = 0

    def walk(node, inst_path: list[str]) -> None:
        nonlocal timescale_s, duration_units, n_nets
        if not isinstance(node, list) or not node:
            return
        tag = str(node[0] or "").upper()
        if tag == "TIMESCALE":
            ts = _saif_timescale(node)
            if ts:
                timescale_s = ts
            return
        if tag == "DURATION":
            try:
                duration_units = float(node[1])
            except (IndexError, TypeError, ValueError):
                duration_units = None
            return
        if tag == "INSTANCE":
            name = str(node[1]) if len(node) > 1 and not isinstance(node[1], list) else ""
            child = inst_path + ([name] if name else [])
            max_tc = 0
            saw_net = False
            for ch in node[2:]:
                if not isinstance(ch, list) or not ch:
                    continue
                ctag = str(ch[0] or "").upper()
                if ctag in ("NET", "PORT"):
                    for net in ch[1:]:
                        if not isinstance(net, list):
                            continue
                        saw_net = True
                        n_nets += 1
                        max_tc = max(max_tc, _saif_net_tc(net))
                else:
                    walk(ch, child)
            if saw_net and child:
                toggle["/".join(child)] = max_tc
                toggle[".".join(child)] = max_tc
            return
        for ch in node[1:]:
            if isinstance(ch, list):
                walk(ch, inst_path)

    if isinstance(tree, list):
        walk(tree, [])
    duration_s = None if duration_units is None else duration_units * timescale_s
    return {
        "timescale_s": timescale_s,
        "duration_s": duration_s,
        "n_nets": n_nets,
        "n_inst": len({k.replace("/", ".") for k in toggle}),
        "toggle_count": toggle,
    }


def apply_saif_activity(events: list[dict], saif: dict) -> dict:
    """Idle-zero ITerm pulses from SAIF TC. Never invent t50; never rescale I_avg.

    VCD name-join already matched → do not idle-zero (edge times win).
    TC>0 keeps STA/synthetic/VCD t50 and the existing triangle charge.
    """
    toggles = saif.get("toggle_count") or {}
    if not toggles:
        return {
            "status": "GAP",
            "n_matched": 0,
            "n_idle": 0,
            "n_toggled": 0,
            "n_events": len(events),
            "via": "no SAIF toggle counts",
        }
    n_idle = n_toggled = n_skip_vcd = 0
    for ev in events:
        tc = hier_lookup(ev.get("inst"), toggles)
        if tc is None:
            continue
        ev["saif_tc"] = int(tc)
        if ev.get("t50_via") == "vcd_name_join":
            n_skip_vcd += 1
            continue
        if int(tc) == 0:
            leak = float(ev.get("i_leak") or 0.0)
            ev["i_pulse"] = 0.0
            ev["i_peak"] = leak
            ev["saif_idle"] = True
            n_idle += 1
        else:
            ev["saif_idle"] = False
            n_toggled += 1
    n_matched = n_idle + n_toggled + n_skip_vcd
    return {
        "status": "READY" if n_matched else "GAP",
        "n_matched": n_matched,
        "n_idle": n_idle,
        "n_toggled": n_toggled,
        "n_skip_vcd": n_skip_vcd,
        "n_events": len(events),
        "n_saif_inst": saif.get("n_inst") or 0,
        "via": "SAIF TC name-join (idle zeros pulse; no t50 from SAIF; no I_avg rescale from TC)",
    }


def probe_activity_trace(path: Path | None, insts: list | None = None) -> dict:
    """What a VCD/SAIF/FSDB file can (not) drive. Does not invent pin times."""
    if path is None or not Path(path).is_file():
        return {
            "status": "GAP",
            "kind": "missing",
            "path": None,
            "n_matched": 0,
            "note": "no VCD/SAIF/FSDB — synthetic or STA t50",
        }
    p = Path(path)
    head = p.read_bytes()[:4096]
    kind = "unknown"
    if head.startswith(b"$date") or b"$var" in head:
        kind = "vcd"
    elif b"(SAIF" in head or b"(SAIFILE" in head:
        kind = "saif"
    elif p.suffix.lower() in {".fsdb", ".vf"}:
        kind = "fsdb"
    n_match = 0
    n_sig = 0
    extra: dict = {}
    if kind == "vcd" and insts:
        parsed = parse_vcd(p)
        n_sig = parsed.get("n_signals") or 0
        edges = parsed.get("first_edge_s") or {}
        inst_keys = {norm_inst(i.get("name")) for i in insts if i.get("name")}
        n_match = sum(1 for k in inst_keys if k and vcd_edge_time(k, edges) is not None)
    elif kind == "saif":
        parsed = parse_saif(p)
        n_sig = parsed.get("n_nets") or 0
        extra["n_inst"] = parsed.get("n_inst") or 0
        extra["duration_s"] = parsed.get("duration_s")
        if insts:
            toggles = parsed.get("toggle_count") or {}
            inst_keys = {norm_inst(i.get("name")) for i in insts if i.get("name")}
            n_match = sum(1 for k in inst_keys if k and hier_lookup(k, toggles) is not None)
    elif kind == "fsdb":
        extra["note_fsdb"] = "FSDB is proprietary binary — no decoder in this tree"
    status = "READY" if n_match else "GAP"
    if n_match:
        note = f"{kind} name-join {n_match} instances"
    elif kind == "fsdb":
        note = "FSDB present but proprietary; no silent pin mapping"
    else:
        note = f"{kind} present but names do not match gate instances; no silent pin mapping"
    out = {
        "status": status,
        "kind": kind,
        "path": str(p),
        "n_matched": n_match,
        "n_signals": n_sig,
        "note": note,
    }
    out.update(extra)
    return out


def itot_from_events(events, dt: float, t_end: float) -> tuple[list[float], list[float]]:
    """Cheap I_tot(t) from triangles — no PDN solve."""
    from pdn_current import triangle_above_leak

    steps = max(2, int(math.ceil(t_end / dt)))
    ts, it = [], []
    for s in range(steps):
        t = s * dt
        acc = 0.0
        for ev in events:
            acc += float(ev.get("i_leak") or 0.0)
            acc += triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
        ts.append(t)
        it.append(acc)
    return ts, it


def windows_from_itot(wave_t, wave_itot, frac: float = 0.5) -> list[dict]:
    if not wave_itot:
        return []
    peak = max(wave_itot)
    thresh = frac * peak
    out: list[dict] = []
    in_win = False
    t0 = peak_t = 0.0
    peak_i = 0.0
    for t, i in zip(wave_t, wave_itot):
        if i >= thresh:
            if not in_win:
                in_win = True
                t0 = t
                peak_t, peak_i = t, i
            elif i > peak_i:
                peak_t, peak_i = t, i
        elif in_win:
            out.append(
                {
                    "t_start_s": t0,
                    "t_end_s": t,
                    "t_peak_s": peak_t,
                    "i_peak_a": peak_i,
                    "threshold_frac": frac,
                }
            )
            in_win = False
    if in_win and wave_t:
        out.append(
            {
                "t_start_s": t0,
                "t_end_s": wave_t[-1],
                "t_peak_s": peak_t,
                "i_peak_a": peak_i,
                "threshold_frac": frac,
            }
        )
    return out


def expand_windows(wins: list[dict], pad_s: float, t_end: float) -> list[dict]:
    """Merge overlapping windows after padding. Isolated pulses stay separate."""
    if not wins:
        return []
    padded = []
    for w in wins:
        padded.append(
            {
                **w,
                "t_start_s": max(0.0, w["t_start_s"] - pad_s),
                "t_end_s": min(t_end, w["t_end_s"] + pad_s),
            }
        )
    padded.sort(key=lambda w: w["t_start_s"])
    merged = [dict(padded[0])]
    for w in padded[1:]:
        if w["t_start_s"] <= merged[-1]["t_end_s"]:
            merged[-1]["t_end_s"] = max(merged[-1]["t_end_s"], w["t_end_s"])
            if w["i_peak_a"] > merged[-1]["i_peak_a"]:
                merged[-1]["i_peak_a"] = w["i_peak_a"]
                merged[-1]["t_peak_s"] = w["t_peak_s"]
        else:
            merged.append(dict(w))
    return merged


def shift_events_to_window(events, t0: float, t1: float) -> list[dict]:
    """Events overlapping [t0, t1], t50 shifted so the window starts at 0."""
    out = []
    for ev in events:
        t50 = float(ev["t50_s"])
        half = 0.5 * float(ev["dur_s"])
        if t50 + half < t0 or t50 - half > t1:
            continue
        e = dict(ev)
        e["t50_s"] = t50 - t0
        out.append(e)
    return out


def plan_events(
    currents: dict[str, float],
    idx: dict[str, int],
    insts: list[dict],
    *,
    mode: str,
    peak_factor: float,
    leak_frac: float,
    period_s: float,
    dur_s: float,
    t50_s: float,
    sta_arrivals: dict | None = None,
    vcd: dict | None = None,
    saif: dict | None = None,
) -> list[dict]:
    """t50: synthetic, then STA arrivals (clock mode), then VCD name-join.

    SAIF (after VCD) idle-zeros unmatched-idle pulses. Does not invent t50.
    Ranking extra I(t) must not pass STA/VCD/SAIF — those stay synthetic.
    """
    loads = [(n, i) for n, i in currents.items() if n != "0" and n in idx and i > 0]
    xs = []
    for n, _ in loads:
        xy = node_xy(n)
        xs.append(xy[0] if xy else 0.0)
    xmin, xmax = (min(xs), max(xs)) if xs else (0.0, 1.0)
    span = max(xmax - xmin, 1.0)

    events = []
    for n, i_avg in loads:
        xy = node_xy(n)
        inst = nearest_inst(xy[0], xy[1], insts) if xy else None
        seq = bool(inst and inst.get("seq"))
        leak = leak_frac * i_avg
        q_switch = max(0.0, (i_avg - leak) * period_s)
        i_from_q = (2.0 * q_switch / dur_s) if dur_s > 0 else 0.0
        i_pulse = min(peak_factor * i_avg, i_from_q if i_from_q > 0 else peak_factor * i_avg)
        i_pulse = max(i_pulse, 0.0)
        via = "synthetic"
        if mode == "simultaneous":
            t50 = t50_s
        elif mode == "spatial":
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            t50 = t50_s + nx * 0.35 * period_s
        else:
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            if seq:
                t50 = t50_s
            else:
                t50 = t50_s + 0.22 * period_s + nx * 0.25 * period_s
        events.append(
            {
                "node": n,
                "idx": idx[n],
                "i_avg": i_avg,
                "i_leak": leak,
                "i_peak": leak + i_pulse,
                "i_pulse": i_pulse,
                "t50_s": t50,
                "dur_s": dur_s,
                "seq": seq,
                "cell": (inst or {}).get("cell"),
                "inst": (inst or {}).get("name"),
                "t50_via": via,
                "x": xy[0] if xy else None,
                "y": xy[1] if xy else None,
            }
        )
    if sta_arrivals and mode == "clock":
        apply_sta_t50(events, sta_arrivals, period_s)
    if vcd:
        apply_vcd_t50(events, vcd, period_s)
    if saif:
        apply_saif_activity(events, saif)
    return events
