#!/usr/bin/env python3
"""
Hierarchical *System* PDN analysis with ngspice.

Domains (not chip PDNSim):
  VRM → board plane/decap → package RLC/bumps → die C + current load

The model is intentionally a compact, lumped RLC model. Each decoupling
capacitor is a shunt branch (ESR, optional ESL, C) connected to the relevant
power node; it is not placed in series with the forward supply path. This is
the useful abstraction for a FlowLab/package experiment, not a board
S-parameter or tapeout signoff model.

Outputs:
  - SPICE netlists (TRAN + AC), isolated per invocation
  - AC impedance Z(f) seen at the die, including complex Z and resonances
  - Transient voltages under a die load-step, including per-domain drops
  - A current-run JSON report for /pkg System PDN / system_pdn

Requires: ngspice
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
NODE_ALIASES = {
    "vrm": "n_vrm_l",
    "vrm_out": "n_vrm_l",
    "board": "n_board",
    "board_out": "n_board_out",
    "package": "n_pkg_l",
    "pkg": "n_pkg_l",
    "pkg_out": "n_pkg_l",
    "die": "n_die",
}
ALLOWED_NODES = {"n_vrm_l", "n_board", "n_board_out", "n_pkg_l", "n_die"}
NODE_VECTOR_NAMES = ("vrm", "board", "package", "die")
VARIANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")


class ConfigError(ValueError):
    """Raised when a System PDN configuration cannot be simulated safely."""


def _validate_variant(value: Any) -> str:
    variant = str(value).strip()
    if not VARIANT_RE.fullmatch(variant):
        raise ConfigError(
            "variant must start with a letter or digit and contain only "
            "letters, digits, '.', '+', '_' or '-'")
    return variant


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ConfigError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise ConfigError(f"{label} must be >= {minimum:g}")
    return result


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    result = _number(value, label)
    if not result.is_integer() or int(result) < minimum:
        raise ConfigError(f"{label} must be an integer >= {minimum}")
    return int(result)


def _fmt(value: float) -> str:
    """Format a value for a SPICE card without locale-dependent notation."""
    return f"{float(value):.12g}"


def _safe_component(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", str(value)).strip("_")
    if not result:
        raise ConfigError("component name cannot be empty")
    if result[0].isdigit():
        result = "N_" + result
    return result.upper()


def load_cfg(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"missing System PDN config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in System PDN config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError("System PDN config must be a JSON object")
    return value


def _section(cfg: dict, name: str) -> dict:
    value = cfg.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"missing or invalid config section: {name}")
    return value


def _node(value: Any, default: str) -> str:
    raw = str(value or default)
    node = NODE_ALIASES.get(raw.lower(), raw)
    if node not in ALLOWED_NODES:
        raise ConfigError(
            f"decap node {raw!r} is not allowed; use one of {sorted(ALLOWED_NODES)}"
        )
    return node


def _normalise_decap(
    raw: dict,
    *,
    domain: str,
    index: int,
    default_name: str,
    default_node: str,
    default_label: str,
) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"{domain}.decaps[{index}] must be an object")
    name = str(raw.get("name") or default_name)
    c_value = raw.get("c_f", raw.get("capacitance_f"))
    if c_value is None:
        raise ConfigError(f"{domain}.decaps[{index}] is missing c_f")
    c_f = _number(c_value, f"{domain}.decaps[{index}].c_f", minimum=0.0)
    if c_f <= 0.0:
        raise ConfigError(f"{domain}.decaps[{index}].c_f must be > 0")
    esr = _number(
        raw.get("esr_ohm", raw.get("r_ohm", raw.get("esr", 0.0))),
        f"{domain}.decaps[{index}].esr_ohm",
        minimum=0.0,
    )
    esl = _number(
        raw.get("esl_h", raw.get("l_h", raw.get("inductance_h", 0.0))),
        f"{domain}.decaps[{index}].esl_h",
        minimum=0.0,
    )
    label = _safe_component(str(raw.get("spice_label") or f"{default_label}_{name}"))
    return {
        "domain": domain,
        "name": name,
        "node": _node(raw.get("node"), default_node),
        "c_f": c_f,
        "esr_ohm": esr,
        "esl_h": esl,
        "spice_label": label,
    }


def _decap_specs(cfg: dict) -> dict[str, list[dict]]:
    """Return normalized shunt decap branches while accepting the legacy schema."""
    vrm = _section(cfg, "vrm")
    board = _section(cfg, "board")
    package = _section(cfg, "package")
    die = _section(cfg, "die")

    legacy = {
        "vrm": (
            vrm,
            [
                {
                    "name": "cout",
                    "c_f": vrm.get("c_out"),
                    "esr_ohm": vrm.get("esr_cout", 0.0),
                    "node": "n_vrm_l",
                    "spice_label": "VRM",
                }
            ],
            "n_vrm_l",
        ),
        "board": (
            board,
            [
                {
                    "name": "bulk",
                    "c_f": board.get("c_bulk"),
                    "esr_ohm": board.get("esr_bulk", 0.0),
                    "node": "n_board",
                    "spice_label": "BULK",
                },
                {
                    "name": "hf",
                    "c_f": board.get("c_hf"),
                    "esr_ohm": board.get("esr_hf", 0.0),
                    "node": "n_board_out",
                    "spice_label": "HF",
                },
            ],
            "n_board",
        ),
        "package": (
            package,
            [
                {
                    "name": "pkg",
                    "c_f": package.get("c_pkg"),
                    "esr_ohm": package.get("esr_cpkg", package.get("esr_pkg", 0.0)),
                    "node": "n_pkg_l",
                    "spice_label": "PKG",
                }
            ],
            "n_pkg_l",
        ),
        "die": (
            die,
            [
                {
                    "name": "die",
                    "c_f": die.get("c_die"),
                    "esr_ohm": die.get("esr_cdie", die.get("esr_die", 0.0)),
                    "node": "n_die",
                    "spice_label": "DIE",
                }
            ],
            "n_die",
        ),
    }
    result: dict[str, list[dict]] = {}
    used_labels: set[str] = set()
    for domain, (section, fallback, default_node) in legacy.items():
        raw_specs = section.get("decaps")
        if raw_specs is None:
            raw_specs = fallback
        if not isinstance(raw_specs, list) or not raw_specs:
            raise ConfigError(f"{domain}.decaps must be a non-empty array")
        rows: list[dict] = []
        for index, raw in enumerate(raw_specs):
            fallback_row = fallback[min(index, len(fallback) - 1)]
            row = _normalise_decap(
                raw,
                domain=domain,
                index=index,
                default_name=str(fallback_row.get("name") or f"decap{index}"),
                default_node=str(fallback_row.get("node") or default_node),
                default_label=str(fallback_row.get("spice_label") or domain),
            )
            if row["spice_label"] in used_labels:
                raise ConfigError(
                    f"duplicate SPICE decap label: {row['spice_label']}"
                )
            used_labels.add(row["spice_label"])
            rows.append(row)
        result[domain] = rows
    return result


def validate_config(cfg: dict) -> list[str]:
    """Validate the electrical model and return non-fatal modeling warnings."""
    warnings: list[str] = []
    if "schema_version" in cfg:
        schema_version = _integer(cfg["schema_version"], "schema_version", minimum=1)
        if schema_version not in {1, SCHEMA_VERSION}:
            raise ConfigError(
                f"unsupported System PDN schema_version {schema_version}; supported: 1, {SCHEMA_VERSION}"
            )
    vdd = _number(cfg.get("vdd"), "vdd", minimum=0.0)
    if vdd <= 0.0:
        raise ConfigError("vdd must be > 0")

    vrm = _section(cfg, "vrm")
    board = _section(cfg, "board")
    package = _section(cfg, "package")
    die = _section(cfg, "die")
    for section_name, section, fields in (
        ("vrm", vrm, ("r_out", "l_out", "c_out", "esr_cout")),
        ("board", board, ("r_plane", "l_plane", "c_bulk", "esr_bulk", "c_hf", "esr_hf", "l_via_to_pkg")),
        ("package", package, ("r_pkg", "l_pkg", "c_pkg")),
        ("die", die, ("c_die",)),
    ):
        for field in fields:
            if field in section:
                _number(section[field], f"{section_name}.{field}", minimum=0.0)
    n_bumps = _integer(package.get("n_bumps", 1), "package.n_bumps", minimum=1)
    if n_bumps < 1:
        raise ConfigError("package.n_bumps must be >= 1")

    required_path_fields = {
        "vrm": ("r_out", "l_out"),
        "board": ("r_plane", "l_plane", "l_via_to_pkg"),
        "package": ("r_pkg", "l_pkg", "r_bump", "l_bump"),
    }
    for section_name, fields in required_path_fields.items():
        section = _section(cfg, section_name)
        for field in fields:
            if field not in section:
                raise ConfigError(f"missing required path parameter: {section_name}.{field}")

    for path, r_value, l_value in (
        ("vrm path", vrm.get("r_out"), vrm.get("l_out")),
        ("board plane", board.get("r_plane"), board.get("l_plane")),
        ("package path", package.get("r_pkg"), package.get("l_pkg")),
        ("bump path", package.get("r_bump"), package.get("l_bump")),
    ):
        if r_value is not None:
            _number(r_value, f"{path} resistance", minimum=0.0)
        if l_value is not None:
            _number(l_value, f"{path} inductance", minimum=0.0)
        if r_value is not None and l_value is not None and float(r_value) == 0.0 and float(l_value) == 0.0:
            raise ConfigError(f"{path} cannot have both R and L equal to zero")

    specs = _decap_specs(cfg)
    if not any(row["esr_ohm"] > 0.0 or row["esl_h"] > 0.0 for rows in specs.values() for row in rows):
        warnings.append("all decap branches are ideal C; anti-resonance damping is not modeled")
    if not any(row["esl_h"] > 0.0 for rows in specs.values() for row in rows):
        warnings.append("no capacitor ESL is specified; package/board mounting inductance is represented only by path L")
    if "v_nom" in vrm and abs(_number(vrm["v_nom"], "vrm.v_nom") - vdd) > 1e-9:
        warnings.append("vrm.v_nom differs from top-level vdd; top-level vdd drives the source")

    ac = _section(cfg, "ac")
    f_start = _number(ac.get("f_start"), "ac.f_start", minimum=0.0)
    f_stop = _number(ac.get("f_stop"), "ac.f_stop", minimum=0.0)
    if f_start <= 0.0 or f_stop <= f_start:
        raise ConfigError("ac requires 0 < f_start < f_stop")
    if _integer(ac.get("points_per_decade"), "ac.points_per_decade", minimum=1) < 1:
        raise ConfigError("ac.points_per_decade must be >= 1")
    if "z_target_mohm" in ac:
        _number(ac["z_target_mohm"], "ac.z_target_mohm", minimum=0.0)

    tr = _section(cfg, "tran")
    t_step = _number(tr.get("t_step"), "tran.t_step", minimum=0.0)
    t_stop = _number(tr.get("t_stop"), "tran.t_stop", minimum=0.0)
    if t_step <= 0.0 or t_stop <= t_step:
        raise ConfigError("tran requires 0 < t_step < t_stop")
    for field in ("i_idle_factor", "i_peak_factor", "edge_ns"):
        if field in tr:
            _number(tr[field], f"tran.{field}", minimum=0.0)
    method = str(tr.get("method", "gear")).lower()
    if method not in {"gear", "trap", "trapezoidal"}:
        raise ConfigError("tran.method must be gear or trap")
    maxord = _integer(tr.get("maxord", 2), "tran.maxord", minimum=1)
    if maxord > 6:
        raise ConfigError("tran.maxord must be <= 6")
    if method == "gear" and maxord < 2:
        warnings.append("Gear maxord=1 is not portable; using maxord=2 in the generated deck")
    band = _number(tr.get("settling_band_pct", 1.0), "tran.settling_band_pct", minimum=0.0)
    if band == 0.0:
        warnings.append("settling_band_pct=0 makes settling detection exact and usually unattainable")
    edge_s = _time_parameter(tr, ("edge_s",), ("edge_ns",), 2e-9, "tran.edge")
    delay_s = _time_parameter(tr, ("delay_s", "t_delay_s"), ("delay_ns", "t_delay_ns"), 20e-9, "tran.delay")
    width_s = _time_parameter(tr, ("pulse_width_s", "width_s"), ("pulse_width_ns", "width_ns"), 80e-9, "tran.pulse_width")
    period_s = _time_parameter(tr, ("period_s",), ("period_ns",), 1.0, "tran.period")
    if edge_s < 0.0 or delay_s < 0.0:
        raise ConfigError("tran edge and delay must be >= 0")
    if width_s <= 0.0:
        raise ConfigError("tran pulse width must be > 0")
    if period_s <= 0.0:
        raise ConfigError("tran period must be > 0")
    if delay_s >= t_stop:
        warnings.append("tran delay is at or after t_stop; the load-step will not be observed")
    if delay_s + edge_s + width_s >= period_s:
        warnings.append("tran pulse reaches its period boundary; check PULSE timing")
    if _integer(tr.get("max_wave_points", 240), "tran.max_wave_points", minimum=20) < 20:
        raise ConfigError("tran.max_wave_points must be >= 20")

    target = cfg.get("target")
    if target is not None:
        if not isinstance(target, dict):
            raise ConfigError("target must be an object")
        for field in ("rail_ripple_pct", "vrm_regulation_pct", "allowed_ripple_mv", "droop_limit_mv"):
            if field in target and target[field] is not None:
                _number(target[field], f"target.{field}", minimum=0.0)
        if "rail_ripple_pct" in target and "vrm_regulation_pct" in target:
            if float(target["vrm_regulation_pct"]) > float(target["rail_ripple_pct"]):
                warnings.append("target VRM regulation budget exceeds rail ripple budget; derived Ztarget is unavailable")
    return warnings


def _append_series(
    lines: list[str],
    *,
    r_name: str,
    l_name: str,
    a: str,
    b: str,
    r_ohm: float,
    l_h: float,
    intermediate: str,
) -> None:
    """Append a series R/L path, omitting an explicitly zero element."""
    if r_ohm > 0.0 and l_h > 0.0:
        lines.append(f"R_{_safe_component(r_name)} {a} {intermediate} {_fmt(r_ohm)}")
        lines.append(f"L_{_safe_component(l_name)} {intermediate} {b} {_fmt(l_h)}")
    elif r_ohm > 0.0:
        lines.append(f"R_{_safe_component(r_name)} {a} {b} {_fmt(r_ohm)}")
    elif l_h > 0.0:
        lines.append(f"L_{_safe_component(l_name)} {a} {b} {_fmt(l_h)}")
    else:
        raise ConfigError(f"series path {r_name}/{l_name} has no impedance")


def _append_decap(lines: list[str], spec: dict) -> None:
    label = _safe_component(spec["spice_label"])
    current = spec["node"]
    if spec["esr_ohm"] > 0.0:
        r_node = f"{current}_{label.lower()}_esr"
        lines.append(f"R_ESR_{label} {current} {r_node} {_fmt(spec['esr_ohm'])}")
        current = r_node
    if spec["esl_h"] > 0.0:
        l_node = f"{current}_{label.lower()}_esl"
        lines.append(f"L_ESL_{label} {current} {l_node} {_fmt(spec['esl_h'])}")
        current = l_node
    lines.append(f"C_{label} {current} 0 {_fmt(spec['c_f'])}")


def _ladder(cfg: dict) -> list[str]:
    """Shared passive ladder: source path plus shunt decoupling branches."""
    v = _number(cfg["vdd"], "vdd", minimum=0.0)
    vrm = _section(cfg, "vrm")
    board = _section(cfg, "board")
    package = _section(cfg, "package")
    specs = _decap_specs(cfg)
    n_bumps = _integer(package.get("n_bumps", 1), "package.n_bumps", minimum=1)
    r_bump = _number(package["r_bump"], "package.r_bump", minimum=0.0) / n_bumps
    l_bump = _number(package["l_bump"], "package.l_bump", minimum=0.0) / n_bumps

    lines = [
        "* System PDN passive ladder — VRM -> board -> package -> die",
        "* Decaps are shunt ESR/ESL/C branches; parallel bumps use R/n and L/n.",
        f"V_VRM n_vrm_src 0 DC {_fmt(v)}",
    ]
    _append_series(
        lines,
        r_name="VRM",
        l_name="VRM",
        a="n_vrm_src",
        b="n_vrm_l",
        r_ohm=_number(vrm["r_out"], "vrm.r_out", minimum=0.0),
        l_h=_number(vrm["l_out"], "vrm.l_out", minimum=0.0),
        intermediate="n_vrm",
    )
    for spec in specs["vrm"]:
        _append_decap(lines, spec)

    _append_series(
        lines,
        r_name="PLANE",
        l_name="PLANE",
        a="n_vrm_l",
        b="n_board_out",
        r_ohm=_number(board["r_plane"], "board.r_plane", minimum=0.0),
        l_h=_number(board["l_plane"], "board.l_plane", minimum=0.0),
        intermediate="n_board",
    )
    for spec in specs["board"]:
        _append_decap(lines, spec)

    _append_series(
        lines,
        r_name="VIA",
        l_name="VIA",
        a="n_board_out",
        b="n_pkg_in",
        r_ohm=0.0,
        l_h=_number(board["l_via_to_pkg"], "board.l_via_to_pkg", minimum=0.0),
        intermediate="n_pkg_via",
    )
    _append_series(
        lines,
        r_name="PKG",
        l_name="PKG",
        a="n_pkg_in",
        b="n_pkg_l",
        r_ohm=_number(package["r_pkg"], "package.r_pkg", minimum=0.0),
        l_h=_number(package["l_pkg"], "package.l_pkg", minimum=0.0),
        intermediate="n_pkg",
    )
    for spec in specs["package"]:
        _append_decap(lines, spec)

    _append_series(
        lines,
        r_name="BUMP",
        l_name="BUMP",
        a="n_pkg_l",
        b="n_die",
        r_ohm=r_bump,
        l_h=l_bump,
        intermediate="n_die_pre",
    )
    for spec in specs["die"]:
        _append_decap(lines, spec)
    return lines


def _time_parameter(section: dict, seconds_keys: tuple[str, ...], ns_keys: tuple[str, ...], default: float, label: str) -> float:
    for key in seconds_keys:
        if key in section:
            return _number(section[key], label, minimum=0.0)
    for key in ns_keys:
        if key in section:
            return _number(section[key], label, minimum=0.0) * 1e-9
    return default


def _tran_parameters(cfg: dict) -> dict:
    tr = _section(cfg, "tran")
    t_step = _number(tr["t_step"], "tran.t_step", minimum=0.0)
    t_stop = _number(tr["t_stop"], "tran.t_stop", minimum=0.0)
    edge_s = _time_parameter(tr, ("edge_s",), ("edge_ns",), 2e-9, "tran.edge")
    delay_s = _time_parameter(tr, ("delay_s", "t_delay_s"), ("delay_ns", "t_delay_ns"), 20e-9, "tran.delay")
    width_s = _time_parameter(tr, ("pulse_width_s", "width_s"), ("pulse_width_ns", "width_ns"), 80e-9, "tran.pulse_width")
    period_s = _time_parameter(tr, ("period_s",), ("period_ns",), 1.0, "tran.period")
    if edge_s <= 0.0:
        edge_s = t_step
    method = str(tr.get("method", "gear")).lower()
    if method == "trapezoidal":
        method = "trap"
    maxord = _integer(tr.get("maxord", 2), "tran.maxord", minimum=1)
    if method == "gear":
        maxord = max(maxord, 2)
    return {
        "t_step": t_step,
        "t_stop": t_stop,
        "edge_s": edge_s,
        "delay_s": delay_s,
        "pulse_width_s": width_s,
        "period_s": period_s,
        "i_idle_factor": _number(tr.get("i_idle_factor", 0.3), "tran.i_idle_factor", minimum=0.0),
        "i_peak_factor": _number(tr.get("i_peak_factor", 4.0), "tran.i_peak_factor", minimum=0.0),
        "method": method,
        "maxord": maxord,
        "settling_band_pct": _number(tr.get("settling_band_pct", 1.0), "tran.settling_band_pct", minimum=0.0),
        "max_wave_points": _integer(tr.get("max_wave_points", 240), "tran.max_wave_points", minimum=20),
    }


def write_tran_netlist(cfg: dict, i_die_avg: float, out: Path) -> dict:
    params = _tran_parameters(cfg)
    i_die_avg = _number(i_die_avg, "i_die_avg", minimum=0.0)
    i_idle = i_die_avg * params["i_idle_factor"]
    i_peak = i_die_avg * params["i_peak_factor"]
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "* System PDN TRAN — VRM / board / package / die load-step",
        f"* I_avg={i_die_avg:.6e} idle={i_idle:.6e} peak={i_peak:.6e}",
        f"* delay={params['delay_s']:.6e} edge={params['edge_s']:.6e} width={params['pulse_width_s']:.6e}",
        "",
        *_ladder(cfg),
        "",
        "I_DIE n_die 0 PULSE("
        f"{_fmt(i_idle)} {_fmt(i_peak)} {_fmt(params['delay_s'])} "
        f"{_fmt(params['edge_s'])} {_fmt(params['edge_s'])} "
        f"{_fmt(params['pulse_width_s'])} {_fmt(params['period_s'])})",
        "",
        f".options method={params['method']} maxord={params['maxord']}",
        ".control",
        "set filetype=ascii",
        f"tran {_fmt(params['t_step'])} {_fmt(params['t_stop'])}",
        "wrdata __TRAN__ v(n_vrm_l) v(n_board_out) v(n_pkg_l) v(n_die)",
        "quit",
        ".endc",
        ".end",
        "",
    ]
    out.write_text("\n".join(lines))
    return {
        **params,
        "i_die_avg_a": i_die_avg,
        "i_idle_a": i_idle,
        "i_peak_a": i_peak,
        "i_step_a": i_peak - i_idle,
    }


def write_ac_netlist(cfg: dict, out: Path) -> dict:
    ac = _section(cfg, "ac")
    f_start = _number(ac["f_start"], "ac.f_start", minimum=0.0)
    f_stop = _number(ac["f_stop"], "ac.f_stop", minimum=0.0)
    points = _integer(ac["points_per_decade"], "ac.points_per_decade", minimum=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "* System PDN AC — die driving-point impedance (I_AC=1A)",
        "* wrdata emits frequency, real(Z), imag(Z), frequency, |Z|.",
        "",
        *_ladder(cfg),
        "",
        "I_AC n_die 0 DC 0 AC 1",
        "",
        ".control",
        "set filetype=ascii",
        f"ac dec {points} {_fmt(f_start)} {_fmt(f_stop)}",
        "let zmag = abs(v(n_die))",
        "wrdata __AC__ v(n_die) zmag",
        "quit",
        ".endc",
        ".end",
        "",
    ]
    out.write_text("\n".join(lines))
    return {"f_start_hz": f_start, "f_stop_hz": f_stop, "points_per_decade": points}


def parse_wrdata(path: Path) -> list[list[float]]:
    """Parse ngspice wrdata ASCII rows, ignoring headers and malformed rows."""
    rows: list[list[float]] = []
    if not path.exists():
        return rows
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return rows
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        try:
            values = [float(token) for token in line.split()]
        except ValueError:
            continue
        if values and all(math.isfinite(value) for value in values):
            rows.append(values)
    return rows


def _decode_tran(rows: list[list[float]], n_vectors: int = 4) -> list[dict]:
    decoded: list[dict] = []
    for row in rows:
        if len(row) >= 2 * n_vectors:
            values = [row[2 * index + 1] for index in range(n_vectors)]
            time_s = row[0]
        elif len(row) >= n_vectors + 1:
            time_s = row[0]
            values = row[1 : n_vectors + 1]
        else:
            continue
        if not math.isfinite(time_s) or any(not math.isfinite(value) for value in values):
            continue
        decoded.append({"t_s": float(time_s), "values": [float(value) for value in values]})
    decoded.sort(key=lambda row: row["t_s"])
    return decoded


def _decode_ac(rows: list[list[float]]) -> list[dict]:
    decoded: list[dict] = []
    for row in rows:
        if len(row) >= 5:
            frequency = row[0]
            real_z = row[1]
            imag_z = row[2]
            magnitude = row[4]
        elif len(row) >= 3:
            frequency = row[0]
            real_z = row[1]
            imag_z = row[2]
            magnitude = math.hypot(real_z, imag_z)
        elif len(row) >= 2:
            frequency = row[0]
            real_z = row[1]
            imag_z = 0.0
            magnitude = abs(row[1])
        else:
            continue
        if frequency <= 0.0 or not all(math.isfinite(value) for value in (frequency, real_z, imag_z, magnitude)):
            continue
        decoded.append(
            {
                "f_hz": float(frequency),
                "z_real_ohm": float(real_z),
                "z_imag_ohm": float(imag_z),
                "z_ohm": float(max(magnitude, math.hypot(real_z, imag_z))),
            }
        )
    decoded.sort(key=lambda row: row["f_hz"])
    return decoded


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _window(samples: list[dict], start: float, stop: float) -> list[dict]:
    return [row for row in samples if start <= row["t_s"] <= stop]


def _node_metrics(samples: list[dict], index: int, vdd: float, params: dict) -> dict:
    if not samples:
        return {
            "v_baseline": None,
            "v_min": None,
            "v_max": None,
            "droop_v": None,
            "droop_mv": None,
            "droop_pct": None,
            "peak_droop_at_s": None,
            "v_settled": None,
            "settling_time_s": None,
            "settled": False,
        }
    delay = params["delay_s"]
    rise_end = delay + params["edge_s"]
    high_end = min(rise_end + params["pulse_width_s"], params["t_stop"])
    pre = [row["values"][index] for row in samples if row["t_s"] < delay]
    if not pre:
        pre = [row["values"][index] for row in samples[: max(1, len(samples) // 10)]]
    baseline = _mean(pre)
    event = _window(samples, delay, high_end if high_end > delay else params["t_stop"])
    if not event:
        event = samples
    values = [row["values"][index] for row in event]
    min_value = min(values)
    max_value = max(values)
    min_row = min(event, key=lambda row: row["values"][index])
    band_v = max(abs(vdd) * params["settling_band_pct"] / 100.0, 1e-15)
    settle_window = _window(samples, delay + params["edge_s"] + 0.75 * params["pulse_width_s"], high_end)
    if not settle_window:
        settle_window = event[-max(1, len(event) // 10) :]
    settled_reference = _mean([row["values"][index] for row in settle_window])
    settling_time: float | None = None
    settled = False
    if settled_reference is not None:
        for position, row in enumerate(event):
            if row["t_s"] < rise_end:
                continue
            tail = event[position:]
            if tail and all(abs(item["values"][index] - settled_reference) <= band_v for item in tail):
                settling_time = row["t_s"]
                settled = True
                break
    baseline_value = baseline if baseline is not None else vdd
    droop = baseline_value - min_value
    return {
        "v_baseline": baseline,
        "v_min": min_value,
        "v_max": max_value,
        "droop_v": droop,
        "droop_mv": droop * 1e3,
        "droop_pct": 100.0 * droop / vdd if vdd else None,
        "peak_droop_at_s": min_row["t_s"],
        "v_settled": settled_reference,
        "settling_time_s": settling_time,
        "settled": settled,
        "settling_band_v": band_v,
        "event_start_s": delay,
        "event_end_s": high_end,
    }


def _target_impedance(cfg: dict, i_step_a: float) -> dict:
    ac = _section(cfg, "ac")
    configured = _number(ac.get("z_target_mohm", 0.0), "ac.z_target_mohm", minimum=0.0)
    target = cfg.get("target") if isinstance(cfg.get("target"), dict) else {}
    vdd = _number(cfg["vdd"], "vdd", minimum=0.0)
    allowed_mv: float | None = None
    source = "none"
    if target.get("allowed_ripple_mv") is not None:
        allowed_mv = _number(target["allowed_ripple_mv"], "target.allowed_ripple_mv", minimum=0.0)
        source = "target.allowed_ripple_mv"
    elif target.get("rail_ripple_pct") is not None:
        rail = _number(target["rail_ripple_pct"], "target.rail_ripple_pct", minimum=0.0)
        vrm = _number(target.get("vrm_regulation_pct", 0.0), "target.vrm_regulation_pct", minimum=0.0)
        allowed_mv = max(vdd * (rail - vrm) * 1e3, 0.0)
        source = "target.rail_ripple_pct minus target.vrm_regulation_pct"
    derived_mohm = None
    if allowed_mv is not None and abs(i_step_a) > 0.0:
        derived_mohm = allowed_mv / abs(i_step_a)
    targets = [value for value in (configured if configured > 0.0 else None, derived_mohm) if value is not None]
    if configured > 0.0 and derived_mohm is not None:
        target_source = "ac.z_target_mohm and derived ripple/current budget"
    elif derived_mohm is not None:
        target_source = source
    elif configured > 0.0:
        target_source = "ac.z_target_mohm"
    else:
        target_source = "none"
    return {
        "configured_z_target_mohm": configured if configured > 0.0 else None,
        "derived_z_target_mohm": derived_mohm,
        "effective_z_target_mohm": min(targets) if targets else None,
        "allowed_ripple_mv": allowed_mv,
        "step_current_a": i_step_a,
        "source": target_source,
        "formula": "Ztarget = allowed_ripple / abs(I_peak - I_idle)",
    }


def _resonance_peaks(curve: list[dict], limit: int = 8) -> list[dict]:
    candidates: list[dict] = []
    for index in range(1, len(curve) - 1):
        current = curve[index]
        if current["z_ohm"] >= curve[index - 1]["z_ohm"] and current["z_ohm"] >= curve[index + 1]["z_ohm"]:
            candidates.append(
                {
                    "f_hz": current["f_hz"],
                    "z_ohm": current["z_ohm"],
                    "z_mohm": current["z_ohm"] * 1e3,
                    "kind": "local_maximum",
                }
            )
    candidates.sort(key=lambda row: row["z_ohm"], reverse=True)
    selected: list[dict] = []
    for row in candidates:
        if any(abs(math.log10(row["f_hz"] / other["f_hz"])) < 0.04 for other in selected):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    selected.sort(key=lambda row: row["f_hz"])
    return selected


def _artifact(path: Path, repo: Path) -> dict:
    resolved = path.resolve()
    try:
        relative = str(resolved.relative_to(repo.resolve()))
    except ValueError:
        relative = str(resolved)
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "relative_path": relative,
        "sha256": digest,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _config_fingerprint(cfg: dict) -> str:
    canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _engine_version(executable: str) -> str | None:
    try:
        proc = subprocess.run([executable, "-v"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        line = line.strip()
        if line:
            return line
    return None


def _current_source(repo: Path, variant: str, explicit: bool, i_die: float, vdd: float) -> dict:
    if explicit:
        return {"kind": "explicit", "value_a": i_die}
    reports = repo / "learn" / "sim" / "reports"
    for name in (f"activity_power_{variant}.log", "activity_power.log"):
        path = reports / name
        if not path.is_file():
            continue
        matches = re.findall(
            r"Total\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+([-+0-9.eE]+)",
            path.read_text(errors="replace"),
        )
        if matches:
            power_w = _number(matches[-1], f"{name} total power", minimum=0.0)
            if power_w > 0.0:
                return {
                    "kind": "activity_power",
                    "path": str(path),
                    "power_w": power_w,
                    "vdd_v": vdd,
                    "value_a": power_w / vdd,
                }
    report = reports / f"pdn_chip_ir_{variant}.json"
    if not report.is_file():
        report = reports / f"pdn_transient_{variant}.json"
    if report.is_file():
        try:
            blob = json.loads(report.read_text())
            current = float((blob.get("static") or {}).get("total_current_a") or 0.0)
            if math.isfinite(current) and current > 0.0:
                return {"kind": "chip_pdn_report", "path": str(report), "value_a": current}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return {
        "kind": "default_fallback",
        "value_a": i_die,
        "reason": "no current-bearing live activity artifact was found",
    }


def guess_die_current(repo: Path, variant: str, fallback: float, vdd: float = 1.1) -> float:
    """Backward-compatible current lookup used by callers outside this script."""
    source = _current_source(repo, variant, False, fallback, vdd)
    return float(source.get("value_a") or fallback)


def _run_one(
    netlist_src: Path,
    work: Path,
    tag: str,
    placeholder: str,
    executable: str,
    timeout_s: int,
) -> dict:
    text = netlist_src.read_text().replace(placeholder, str(work / tag))
    netlist = work / f"{tag}.sp"
    netlist.write_text(text)
    log = work / f"{tag}.ngspice.log"
    result: dict[str, Any] = {
        "netlist": netlist,
        "log": log,
        "returncode": None,
        "timed_out": False,
    }
    try:
        proc = subprocess.run(
            [executable, "-b", "-o", str(log), str(netlist)],
            check=False,
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        result["returncode"] = proc.returncode
        result["stdout_tail"] = (proc.stdout or "")[-1000:]
        result["stderr_tail"] = (proc.stderr or "")[-1000:]
    except subprocess.TimeoutExpired as exc:
        result["timed_out"] = True
        result["stdout_tail"] = str(exc.stdout or "")[-1000:]
        result["stderr_tail"] = str(exc.stderr or "")[-1000:]
    except OSError as exc:
        result["error"] = str(exc)
        result["stdout_tail"] = ""
        result["stderr_tail"] = str(exc)
    candidates = [work / tag, work / f"{tag}.data", work / f"{tag}.txt"]
    result["data"] = next((candidate for candidate in candidates if candidate.is_file()), None)
    return result


def run_one(netlist_src: Path, work: Path, tag: str, placeholder: str) -> Path:
    """Compatibility wrapper retained for small external smoke tests."""
    executable = os.environ.get("NGSPICE_EXE") or shutil.which("ngspice") or "ngspice"
    result = _run_one(netlist_src, work, tag, placeholder, executable, 600)
    return result["data"] if result.get("data") is not None else work / tag


def _metric_value(node: dict, key: str) -> float | None:
    value = node.get(key)
    return float(value) if isinstance(value, (float, int)) and math.isfinite(float(value)) else None


def analyze(cfg: dict, tran_rows: list, ac_rows: list, i_die_avg: float, *, run_id: str | None = None) -> dict:
    """Analyze wrdata rows and retain the legacy report fields."""
    vdd = _number(cfg["vdd"], "vdd", minimum=0.0)
    params = _tran_parameters(cfg)
    tran = _decode_tran(tran_rows)
    ac = _decode_ac(ac_rows)
    i_die_avg = _number(i_die_avg, "i_die_avg", minimum=0.0)
    i_idle = i_die_avg * params["i_idle_factor"]
    i_peak = i_die_avg * params["i_peak_factor"]
    i_step = i_peak - i_idle

    node_metrics = {
        name: _node_metrics(tran, index, vdd, params)
        for index, name in enumerate(NODE_VECTOR_NAMES)
    }
    die_metrics = node_metrics["die"]
    die_min = _metric_value(die_metrics, "v_min")
    die_droop = _metric_value(die_metrics, "droop_v")
    peak_row = None
    if tran and die_min is not None:
        peak_row = min(tran, key=lambda row: abs(row["values"][3] - die_min))
    peak_values = peak_row["values"] if peak_row else None
    path_drops = None
    if peak_values:
        path_drops = {
            "source_to_vrm_mv": (vdd - peak_values[0]) * 1e3,
            "vrm_to_board_mv": (peak_values[0] - peak_values[1]) * 1e3,
            "board_to_package_mv": (peak_values[1] - peak_values[2]) * 1e3,
            "package_to_die_mv": (peak_values[2] - peak_values[3]) * 1e3,
            "source_to_die_mv": (vdd - peak_values[3]) * 1e3,
        }

    curve: list[dict] = []
    z_max = 0.0
    f_at_zmax = 0.0
    for row in ac:
        curve.append(row)
        if row["z_ohm"] > z_max:
            z_max = row["z_ohm"]
            f_at_zmax = row["f_hz"]
    target = _target_impedance(cfg, i_step)
    configured_target = target["configured_z_target_mohm"]
    derived_target = target["derived_z_target_mohm"]
    over_configured = [row for row in curve if configured_target is not None and row["z_ohm"] * 1e3 > configured_target]
    over_derived = [row for row in curve if derived_target is not None and row["z_ohm"] * 1e3 > derived_target]
    configured_pass = None if configured_target is None or not curve else not over_configured
    derived_pass = None if derived_target is None or not curve else not over_derived
    target["configured_pass"] = configured_pass
    target["derived_pass"] = derived_pass
    target["configured_exceedance_ratio"] = z_max * 1e3 / configured_target if configured_target and z_max else None
    target["derived_exceedance_ratio"] = z_max * 1e3 / derived_target if derived_target and z_max else None

    droop_limit_mv = None
    target_cfg = cfg.get("target") if isinstance(cfg.get("target"), dict) else {}
    if target_cfg.get("droop_limit_mv") is not None:
        droop_limit_mv = _number(target_cfg["droop_limit_mv"], "target.droop_limit_mv", minimum=0.0)
    droop_pass = None if droop_limit_mv is None or die_droop is None else die_droop * 1e3 <= droop_limit_mv
    requirements = [value for value in (configured_pass, derived_pass, droop_pass) if value is not None]
    requirement_ok = all(requirements) if requirements else None
    evidence_ok = bool(tran and ac)
    if not evidence_ok:
        status = "FAIL"
    elif requirement_ok is True:
        status = "PASS"
    elif requirement_ok is False:
        # The compact model ran and exposed a requirement miss. It is a
        # warning at the product boundary because this report is not product
        # signoff and the board is not an extracted model.
        status = "WARN"
    else:
        status = "PARTIAL"

    wave_step = max(1, len(tran) // params["max_wave_points"])
    wave = [
        {
            "t_s": row["t_s"],
            "vrm_v": row["values"][0],
            "board_v": row["values"][1],
            "package_v": row["values"][2],
            "die_v": row["values"][3],
        }
        for row in tran[::wave_step]
    ]
    z_step = max(1, len(curve) // 160) if curve else 1
    curve_sample = [
        {
            **row,
            "phase_deg": math.degrees(math.atan2(row["z_imag_ohm"], row["z_real_ohm"])),
        }
        for row in curve[::z_step]
    ]
    if die_droop is None:
        summary = "System PDN · no valid transient measurement"
    else:
        summary = (
            f"System PDN · die droop {die_droop * 1e3:.2f} mV "
            f"({100 * die_droop / vdd:.2f}%) · Zmax {z_max * 1e3:.2f} mΩ "
            f"@ {f_at_zmax:.3e} Hz · Iavg {i_die_avg * 1e3:.3f} mA · {status}"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "system_pdn",
        "engine": "ngspice-hierarchical",
        "scope": "package",
        "status": status,
        "ok": evidence_ok,
        "evidence_ok": evidence_ok,
        "evidence_class": "PROXY" if evidence_ok else "GAP",
        "oracle": "ngspice-live-hierarchical",
        "requirement_ok": requirement_ok,
        "product_signoff": False,
        "product_signoff_reason": "System PDN is a compact package/board analysis, not Product signoff",
        "run_id": run_id,
        "comparison_scope": "same-live-invocation",
        "domains": ["VRM", "board", "package", "die"],
        "vdd": vdd,
        "i_die_avg_a": i_die_avg,
        "load_step": {
            "i_idle_a": i_idle,
            "i_peak_a": i_peak,
            "i_step_a": i_step,
            "delay_s": params["delay_s"],
            "rise_time_s": params["edge_s"],
            "pulse_width_s": params["pulse_width_s"],
            "period_s": params["period_s"],
        },
        "transient": {
            "ok": bool(tran),
            "v_die_min": die_min,
            "droop_v": die_droop,
            "droop_mv": die_droop * 1e3 if die_droop is not None else None,
            "droop_pct": 100.0 * die_droop / vdd if die_droop is not None and vdd else None,
            "peak_at_s": die_metrics.get("peak_droop_at_s"),
            "settled": die_metrics.get("settled"),
            "settling_time_s": die_metrics.get("settling_time_s"),
            "nodes": node_metrics,
            "path_drops_at_peak_mv": path_drops,
            "wave": wave,
            "wave_die": [{"t_s": row["t_s"], "v": row["die_v"]} for row in wave],
        },
        "impedance": {
            "ok": bool(curve),
            "z_max_ohm": z_max if curve else None,
            "z_max_mohm": z_max * 1e3 if curve else None,
            "f_at_zmax_hz": f_at_zmax if curve else None,
            "z_dc_ohm": curve[0]["z_ohm"] if curve else None,
            "z_target_mohm": configured_target,
            "z_target_effective_mohm": target["effective_z_target_mohm"],
            "pass_target": configured_pass,
            "pass_target_configured": configured_pass,
            "pass_target_derived": derived_pass,
            "pass_target_effective": configured_pass if configured_pass is not None else derived_pass,
            "n_points": len(curve),
            "n_over_configured_target": len(over_configured),
            "n_over_derived_target": len(over_derived),
            "first_over_configured_hz": over_configured[0]["f_hz"] if over_configured else None,
            "first_over_derived_hz": over_derived[0]["f_hz"] if over_derived else None,
            "curve": curve_sample,
            "resonance_peaks": _resonance_peaks(curve),
        },
        "target_impedance": target,
        "model": {
            "representation": "lumped-rlc",
            "source": "ideal DC VRM source with finite R/L output path",
            "decoupling": "shunt series-ESR/optional-ESL capacitors at VRM/board/package/die nodes",
            "decaps": _decap_specs(cfg),
            "bumps": {
                "n_parallel": _integer(_section(cfg, "package").get("n_bumps", 1), "package.n_bumps", minimum=1),
                "r_and_l_scaled_by_parallel_count": True,
            },
            "ground": "ideal reference node 0",
            "not_modeled": [
                "distributed board plane modes",
                "Touchstone/S-parameter extraction",
                "package geometry",
                "VRM control-loop model",
                "temperature-dependent parasitics",
            ],
        },
        "evaluation": {
            "checks": [
                {"id": "ngspice_transient", "label": "TRAN measurement", "actual": bool(tran), "target": True, "evidence_ok": bool(tran), "ok": bool(tran)},
                {"id": "ngspice_ac", "label": "AC impedance measurement", "actual": bool(curve), "target": True, "evidence_ok": bool(curve), "ok": bool(curve)},
                {"id": "configured_target_impedance", "label": "Configured Ztarget", "actual": configured_pass, "target": True, "evidence_ok": bool(curve), "ok": configured_pass},
                {"id": "derived_target_impedance", "label": "Derived Ztarget budget", "actual": derived_pass, "target": True, "evidence_ok": bool(curve), "ok": derived_pass},
                {"id": "die_droop_limit", "label": "Die droop limit", "actual": droop_pass, "target": True, "evidence_ok": die_droop is not None, "ok": droop_pass},
            ],
            "status": status,
        },
        "summary": summary,
    }


def _write_failure_report(path: Path, *, variant: str, reason: str, run_id: str | None, status: str = "FAIL") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "system_pdn",
        "engine": "ngspice-hierarchical",
        "scope": "package",
        "variant": variant,
        "run_id": run_id,
        "comparison_scope": "same-live-invocation",
        "status": status,
        "ok": False,
        "evidence_ok": False,
        "evidence_class": "GAP" if status == "GAP" else "PARTIAL",
        "oracle": "ngspice-live-hierarchical",
        "requirement_ok": None,
        "product_signoff": False,
        "reason": reason,
        "summary": f"{status} System PDN · {reason}",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _publish_compatibility(invocation_dir: Path, out_dir: Path) -> dict[str, str]:
    """Keep legacy export paths while the report points at the isolated run."""
    mapping = {
        "system_pdn_tran.src.sp": "system_pdn_tran.src.sp",
        "system_pdn_ac.src.sp": "system_pdn_ac.src.sp",
        "tran.sp": "tran.sp",
        "ac.sp": "ac.sp",
        "tran": "tran",
        "ac": "ac",
        "tran.ngspice.log": "tran.ngspice.log",
        "ac.ngspice.log": "ac.ngspice.log",
    }
    published: dict[str, str] = {}
    for source_name, destination_name in mapping.items():
        source = invocation_dir / source_name
        if not source.is_file():
            continue
        destination = out_dir / destination_name
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        published[destination_name] = str(destination)
    return published


def main() -> int:
    ap = argparse.ArgumentParser(description="Hierarchical System PDN (ngspice)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out-dir", required=True, help="compatibility work directory; each invocation gets a child run directory")
    ap.add_argument("--report", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--i-die", type=float, default=0.0)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--run-dir", default=None, help="explicit isolated run directory; also honors PD_FLOW_RUN_DIR")
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("PD_FLOW_TIMEOUT_S", "600")))
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    report_path = Path(args.report).resolve()
    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    run_id_hint = str(args.run_id or os.environ.get("PD_FLOW_RUN_ID") or f"invalid-{uuid.uuid4().hex[:12]}")
    try:
        variant = _validate_variant(args.variant)
    except ConfigError as exc:
        _write_failure_report(report_path, variant=str(args.variant), run_id=run_id_hint, reason=str(exc))
        print(f"FAIL System PDN variant · {exc}", file=sys.stderr)
        return 2
    run_id = str(args.run_id or os.environ.get("PD_FLOW_RUN_ID") or f"{variant}-{uuid.uuid4().hex[:12]}")
    run_id_dir = _safe_component(run_id).lower()
    executable = os.environ.get("NGSPICE_EXE") or shutil.which("ngspice")
    if not executable:
        _write_failure_report(report_path, variant=variant, run_id=run_id, reason="ngspice is not installed; no hierarchical PDN measurement was executed", status="GAP")
        print("SYSTEM_PDN_GAP", variant, "· ngspice unavailable")
        return 2
    if args.timeout < 1 or args.timeout > 3600:
        _write_failure_report(report_path, variant=variant, run_id=run_id, reason="timeout must be in the range 1..3600 seconds")
        return 2

    try:
        cfg = load_cfg(config_path)
        warnings = validate_config(cfg)
        out_dir.mkdir(parents=True, exist_ok=True)
        explicit_run_dir = args.run_dir or os.environ.get("PD_FLOW_RUN_DIR")
        invocation_dir = Path(explicit_run_dir).resolve() if explicit_run_dir else out_dir / "runs" / run_id_dir
        if invocation_dir.exists() and not invocation_dir.is_dir():
            raise ConfigError(f"run directory is not a directory: {invocation_dir}")
        if invocation_dir.exists() and any(invocation_dir.iterdir()):
            raise ConfigError(
                f"run directory is not empty; refusing to overwrite an existing run: {invocation_dir}"
            )
        invocation_dir.mkdir(parents=True, exist_ok=True)
        i_explicit = args.i_die > 0.0
        vdd = _number(cfg["vdd"], "vdd", minimum=0.0)
        current_source = _current_source(repo, variant, i_explicit, args.i_die if i_explicit else 0.002, vdd)
        i_die = args.i_die if i_explicit else float(current_source.get("value_a") or 0.002)
        i_die = _number(i_die, "i_die_avg", minimum=0.0)

        tran_src = invocation_dir / "system_pdn_tran.src.sp"
        ac_src = invocation_dir / "system_pdn_ac.src.sp"
        tran_params = write_tran_netlist(cfg, i_die, tran_src)
        ac_params = write_ac_netlist(cfg, ac_src)
        tran_run = _run_one(tran_src, invocation_dir, "tran", "__TRAN__", executable, args.timeout)
        ac_run = _run_one(ac_src, invocation_dir, "ac", "__AC__", executable, args.timeout)
        tran_rows = parse_wrdata(tran_run["data"]) if tran_run.get("data") else []
        ac_rows = parse_wrdata(ac_run["data"]) if ac_run.get("data") else []
        report = analyze(cfg, tran_rows, ac_rows, i_die, run_id=run_id)
        execution_ok = (
            bool(tran_rows)
            and bool(ac_rows)
            and not tran_run.get("timed_out", False)
            and not ac_run.get("timed_out", False)
            and tran_run.get("returncode") == 0
            and ac_run.get("returncode") == 0
        )
        if not execution_ok:
            report["status"] = "FAIL"
            report["ok"] = False
            report["evidence_ok"] = False
            report["evidence_class"] = "GAP"
            report["requirement_ok"] = None
            report["evaluation"]["status"] = "FAIL"
            report["summary"] = "FAIL System PDN · ngspice execution incomplete or invalid"
        report.update(
            {
                "variant": variant,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "analysis_id": f"system-pdn-{run_id}",
                "config_fingerprint": _config_fingerprint(cfg),
                "engine_version": _engine_version(executable),
                "warnings": warnings,
                "current_source": current_source,
                "config": cfg,
                "run": {
                    "id": run_id,
                    "directory": str(invocation_dir),
                    "timeout_s": args.timeout,
                    "command": [executable, "-b", "-o", "<log>", "<netlist>"],
                    "tran_returncode": tran_run.get("returncode"),
                    "ac_returncode": ac_run.get("returncode"),
                    "tran_timed_out": tran_run.get("timed_out", False),
                    "ac_timed_out": ac_run.get("timed_out", False),
                },
                "netlist_parameters": {"tran": tran_params, "ac": ac_params},
                "files": {
                    "analysis_script": str(Path(__file__).resolve()),
                    "ngspice_executable": str(Path(executable).resolve()),
                    "tran_netlist": str(tran_run["netlist"]),
                    "ac_netlist": str(ac_run["netlist"]),
                    "tran_data": str(tran_run["data"]) if tran_run.get("data") else None,
                    "ac_data": str(ac_run["data"]) if ac_run.get("data") else None,
                    "tran_log": str(tran_run["log"]),
                    "ac_log": str(ac_run["log"]),
                    "config": str(config_path),
                },
            }
        )
        artifacts: list[dict] = []
        artifact_paths: list[Any] = [
            Path(__file__).resolve(),
            Path(executable).resolve(),
            config_path,
            tran_run.get("netlist"),
            ac_run.get("netlist"),
            tran_run.get("data"),
            ac_run.get("data"),
        ]
        if isinstance(current_source.get("path"), str):
            artifact_paths.append(Path(current_source["path"]))
        for path in artifact_paths:
            if isinstance(path, Path) and path.is_file():
                artifacts.append(_artifact(path, repo))
        finish_dir = repo / "tools" / "OpenROAD-flow-scripts" / "flow" / "results" / "nangate45" / "gcd" / variant
        for name in ("6_final.odb", "6_final.spef", "6_final.v", "6_final.gds"):
            path = finish_dir / name
            if path.is_file():
                artifacts.append(_artifact(path, repo))
        report["input_artifacts"] = artifacts
        topology = {
            "config_fingerprint": report["config_fingerprint"],
            "variant": variant,
            "domains": report["domains"],
            "model": report["model"],
        }
        report["mesh_id"] = hashlib.sha256(json.dumps(topology, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
        report["comparison"] = {
            "scope": "same-live-invocation",
            "inputs": [item["sha256"] for item in artifacts],
            "external_baseline_used": False,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        report["files"]["compatibility"] = _publish_compatibility(invocation_dir, out_dir)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print("SYSTEM_PDN_HIER_DONE")
        print(report["summary"])
        print(f"report → {report_path}")
        if not tran_rows:
            print("[warn] transient data empty — see tran.ngspice.log", file=sys.stderr)
            return 3
        if not ac_rows:
            print("[warn] AC Z(f) data empty — see ac.ngspice.log", file=sys.stderr)
            return 4
        if tran_run.get("returncode") not in (0, None) or ac_run.get("returncode") not in (0, None):
            print("[warn] ngspice returned a non-zero code; see run metadata", file=sys.stderr)
            return 5
        return 0
    except ConfigError as exc:
        _write_failure_report(report_path, variant=variant, run_id=run_id, reason=str(exc))
        print(f"FAIL System PDN config · {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as exc:
        _write_failure_report(report_path, variant=variant, run_id=run_id, reason=str(exc))
        print(f"FAIL System PDN · {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
