#!/usr/bin/env python3
"""Build a live package-interface manifest for the selected finish.

The manifest is deliberately separate from Product signoff.  It makes the
package boundary inspectable: finish interface, configured bump map, observed
RDL sidecar topology, compact electrical model, and the exact input hashes
used by the package analysis.

This is an educational package adapter.  It does not claim a foundry bump
map, JEDEC C4 qualification, board S-parameters, or Ansys/Calibre signoff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
COURSE_VARIANTS = {"flowlab", "learn", "eco_scratch"}
LAB_VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")
# Isolated native acceptance runs use a Nangate45 result tree with a
# user-visible variant name. Keep the namespace deliberately narrow so a
# package request cannot turn the variant into an arbitrary path component.
E2E_VARIANT_RE = re.compile(r"^(?:e2e|enterprise-e2e|native-e2e|installer-e2e)[a-z0-9_.-]*$")


def validate_variant(value: str) -> str:
    variant = str(value).strip()
    if (
        variant in COURSE_VARIANTS
        or LAB_VARIANT_RE.fullmatch(variant)
        or (E2E_VARIANT_RE.fullmatch(variant) and ".." not in variant)
    ):
        return variant
    raise ValueError("invalid or unsafe package variant")


def is_lab_variant(variant: str) -> bool:
    return bool(LAB_VARIANT_RE.fullmatch(variant))


def results_dir(root: Path, variant: str) -> Path:
    tree = "asap7" if is_lab_variant(variant) else "nangate45"
    return root / "tools" / "OpenROAD-flow-scripts" / "flow" / "results" / tree / "gcd" / variant


def config_path(root: Path, variant: str) -> Path:
    if is_lab_variant(variant):
        return root / "learn" / "lab" / "asap7" / "pkg" / "asap7_system_pdn.json"
    return root / "learn" / "system_pdn" / "default.json"


def bump_lef_path(root: Path, variant: str) -> Path:
    if is_lab_variant(variant):
        return root / "learn" / "lab" / "asap7" / "pkg" / "dummy_bump_gcd.lef"
    return root / "learn" / "platforms" / "nangate45" / "pkg" / "dummy_bump_gcd.lef"


def system_report_path(root: Path, variant: str) -> Path:
    if is_lab_variant(variant):
        return root / "learn" / "sim" / "reports" / "lab_asap7_system_pdn.json"
    return root / "learn" / "sim" / "reports" / f"system_pdn_{variant}.json"


def default_output_path(root: Path, variant: str) -> Path:
    return root / "learn" / "sim" / "reports" / f"pkg_manifest_{variant}.json"


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def hash_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def artifact(root: Path, role: str, path: Path, authority: str) -> dict[str, Any]:
    exists = path.is_file()
    try:
        size = path.stat().st_size if exists else 0
    except OSError:
        size = 0
    return {
        "role": role,
        "path": relative_path(root, path),
        "exists": exists,
        "bytes": int(size),
        "sha256": hash_file(path) if exists else None,
        "authority": authority,
    }


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def section(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^\s*{re.escape(name)}\s+\d+\s*;\s*(.*?)^\s*END\s+{re.escape(name)}\s*$",
        text,
    )
    return match.group(1) if match else ""


def statements(block: str) -> Iterable[tuple[str, str]]:
    for match in re.finditer(r"(?ms)^\s*-\s+(\S+)(.*?;)", block):
        yield match.group(1), match.group(2)


def dbu_per_micron(def_text: str) -> float:
    match = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", def_text)
    return float(match.group(1)) if match else 1.0


def number_pair(value: str) -> tuple[float, float] | None:
    match = re.search(r"\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)", value)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def parse_interface(def_text: str) -> dict[str, Any]:
    dbu = dbu_per_micron(def_text)
    die_match = re.search(
        r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)",
        def_text,
    )
    die = None
    if die_match:
        values = [int(value) / dbu for value in die_match.groups()]
        die = {
            "lower_left_um": [values[0], values[1]],
            "upper_right_um": [values[2], values[3]],
            "width_um": values[2] - values[0],
            "height_um": values[3] - values[1],
        }

    ports: list[dict[str, Any]] = []
    for name, body in statements(section(def_text, "PINS")):
        net_match = re.search(r"\+\s+NET\s+(\S+)", body)
        if not net_match:
            continue
        direction_match = re.search(r"\+\s+DIRECTION\s+(\S+)", body)
        use_match = re.search(r"\+\s+USE\s+(\S+)", body)
        ports.append(
            {
                "name": name,
                "net": net_match.group(1),
                "direction": direction_match.group(1) if direction_match else None,
                "use": use_match.group(1) if use_match else "SIGNAL",
                "layers": sorted(set(re.findall(r"\+\s+LAYER\s+(\S+)", body))),
            }
        )

    power_nets = sorted(
        {
            port["net"]
            for port in ports
            if str(port.get("use", "")).upper() in {"POWER", "GROUND"}
        }
    )
    specialnet_nets = sorted(
        {name for name, _ in statements(section(def_text, "SPECIALNETS"))}
    )
    return {
        "die": die,
        "database_units_per_micron": dbu,
        "ports": ports,
        "port_count": len(ports),
        "power_nets_from_def": power_nets,
        "specialnet_nets": specialnet_nets,
        "signal_port_count": sum(
            1 for port in ports if str(port.get("use", "")).upper() == "SIGNAL"
        ),
    }


def parse_bump_components(def_text: str) -> list[dict[str, Any]]:
    dbu = dbu_per_micron(def_text)
    bumps: list[dict[str, Any]] = []
    for name, body in statements(section(def_text, "COMPONENTS")):
        match = re.fullmatch(r"BUMP_(\d+)_(\d+)", name)
        if not match:
            continue
        position = re.search(
            r"\+\s+(?:FIXED|PLACED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", body
        )
        if not position:
            continue
        bumps.append(
            {
                "instance": name,
                "row": int(match.group(1)),
                "column": int(match.group(2)),
                "master": body.split()[0] if body.split() else None,
                "x_um": int(position.group(1)) / dbu,
                "y_um": int(position.group(2)) / dbu,
                "placement": "FIXED" if "+ FIXED" in body else "PLACED",
            }
        )
    return sorted(bumps, key=lambda item: (item["row"], item["column"]))


def _route_length_um(body: str, dbu: float) -> float:
    points = [
        (float(x), float(y))
        for x, y in re.findall(r"\(\s*(-?\d+)\s+(-?\d+)\s*\)", body)
    ]
    if len(points) < 2:
        return 0.0
    return sum(abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in zip(points, points[1:])) / dbu


def parse_rdl(
    def_text: str, *, rdl_layers: Iterable[str] | None = None
) -> dict[str, Any]:
    dbu = dbu_per_micron(def_text)
    allowed_layers = {str(layer) for layer in rdl_layers} if rdl_layers else None
    net_rows: list[dict[str, Any]] = []
    bump_to_net: dict[str, str] = {}
    layers: set[str] = set()
    for net, body in statements(section(def_text, "SPECIALNETS")):
        bump_refs = sorted(set(re.findall(r"\bBUMP_\d+_\d+\b", body)))
        all_route_layers = re.findall(r"\b(?:ROUTED|NEW)\s+(\S+)", body)
        route_layers = (
            [layer for layer in all_route_layers if layer in allowed_layers]
            if allowed_layers is not None
            else all_route_layers
        )
        route_segments = len(route_layers)
        for bump in bump_refs:
            bump_to_net[bump] = net
        layers.update(route_layers)
        net_rows.append(
            {
                "net": net,
                "bump_instances": bump_refs,
                "route_layers": sorted(set(route_layers)),
                "route_segments": route_segments,
                "route_length_um_est": round(_route_length_um(body, dbu), 6),
                "routed": route_segments > 0,
                "use": (
                    "POWER"
                    if "+ USE POWER" in body
                    else "GROUND"
                    if "+ USE GROUND" in body
                    else "SIGNAL"
                ),
            }
        )
    return {
        "nets": net_rows,
        "net_count": len(net_rows),
        "layers": sorted(layers),
        "bump_to_net": bump_to_net,
        "route_segments": sum(int(row["route_segments"]) for row in net_rows),
        "route_length_um_est": round(sum(float(row["route_length_um_est"]) for row in net_rows), 6),
    }


def _configured_interface(cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    interface = cfg.get("package_interface")
    if not isinstance(interface, dict):
        interface = {}
    array = interface.get("bump_array")
    if not isinstance(array, dict):
        array = cfg.get("bump_array") if isinstance(cfg.get("bump_array"), dict) else {}
    raw_map = interface.get("bump_map")
    if not isinstance(raw_map, list):
        raw_map = cfg.get("bump_map") if isinstance(cfg.get("bump_map"), list) else []
    normalized: list[dict[str, Any]] = []
    for row in raw_map:
        if not isinstance(row, dict):
            continue
        try:
            bump = str(row.get("instance") or row.get("bump") or "")
            if not bump:
                bump = f"BUMP_{int(row['row'])}_{int(row['column'])}"
            m = re.fullmatch(r"BUMP_(\d+)_(\d+)", bump)
            if not m:
                continue
            net = str(row.get("net") or "").strip()
            if not net:
                continue
            klass = str(row.get("class") or "signal").lower()
            if klass not in {"power", "ground", "signal", "reserved"}:
                klass = "signal"
            normalized.append(
                {
                    "instance": bump,
                    "row": int(m.group(1)),
                    "column": int(m.group(2)),
                    "net": net,
                    "class": klass,
                    "role": row.get("role") or net,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return array, sorted(normalized, key=lambda item: (item["row"], item["column"]))


def _net_class(net: str) -> str:
    upper = net.upper()
    if upper in {"VDD", "VCC", "AVDD", "DVDD"} or upper.endswith("_VDD"):
        return "power"
    if upper in {"VSS", "GND", "AGND", "DGND"} or upper.endswith("_VSS"):
        return "ground"
    return "signal"


def build_manifest(
    root: Path,
    variant: str,
    *,
    config: dict[str, Any] | None = None,
    finish_dir: Path | None = None,
    rdl_def: Path | None = None,
    rdl_odb: Path | None = None,
) -> dict[str, Any]:
    variant = validate_variant(variant)
    finish = finish_dir or results_dir(root, variant)
    cfg_path = config_path(root, variant)
    cfg = config if config is not None else (read_json(cfg_path) or {})
    finish_odb = finish / "6_final.odb"
    finish_def = finish / "6_final.def"
    rdl_def = rdl_def or (finish / "pkg_rdl_sidecar" / "rdl.def")
    rdl_odb = rdl_odb or (finish / "pkg_rdl_sidecar" / "rdl.odb")
    finish_text = finish_def.read_text(errors="replace") if finish_def.is_file() else ""
    rdl_text = rdl_def.read_text(errors="replace") if rdl_def.is_file() else ""
    interface = parse_interface(finish_text) if finish_text else {
        "die": None,
        "database_units_per_micron": None,
        "ports": [],
        "port_count": 0,
        "power_nets_from_def": [],
        "specialnet_nets": [],
        "signal_port_count": 0,
    }
    observed_bumps = parse_bump_components(rdl_text) if rdl_text else []
    array, configured_map = _configured_interface(cfg)
    rdl_layers = {
        str(array.get("power_layer") or ""),
        str(array.get("signal_layer") or ""),
    }
    rdl_layers.discard("")
    observed_rdl = parse_rdl(rdl_text, rdl_layers=rdl_layers) if rdl_text else {
        "nets": [],
        "net_count": 0,
        "layers": [],
        "bump_to_net": {},
        "route_segments": 0,
        "route_length_um_est": 0.0,
    }
    configured_by_bump = {row["instance"]: row for row in configured_map}
    observed_by_bump = {row["instance"]: row for row in observed_bumps}
    observed_by_net = observed_rdl["bump_to_net"]

    try:
        array_rows = int(array.get("rows") or 0)
        array_columns = int(array.get("columns") or 0)
    except (TypeError, ValueError):
        array_rows = array_columns = 0
    coordinates_ok = bool(array_rows > 0 and array_columns > 0) and all(
        0 <= row["row"] < array_rows and 0 <= row["column"] < array_columns
        for row in configured_map
    )

    bump_names = sorted(set(configured_by_bump) | set(observed_by_bump))
    bump_rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, str]] = []
    for name in bump_names:
        configured = configured_by_bump.get(name)
        observed = observed_by_bump.get(name, {})
        configured_net = configured.get("net") if configured else None
        observed_net = observed_by_net.get(name)
        if configured_net and observed_net and configured_net != observed_net:
            conflicts.append(
                {"instance": name, "configured_net": configured_net, "observed_net": observed_net}
            )
        source = {**(configured or {}), **(observed or {})}
        net = observed_net or configured_net
        bump_rows.append(
            {
                "instance": name,
                "row": source.get("row"),
                "column": source.get("column"),
                "x_um": source.get("x_um"),
                "y_um": source.get("y_um"),
                "master": source.get("master"),
                "net": net,
                "configured_net": configured_net,
                "observed_net": observed_net,
                "class": configured.get("class") if configured else _net_class(str(net or "")),
                "role": configured.get("role") if configured else net,
                "assigned": bool(net),
                "observed": name in observed_by_bump or name in observed_by_net,
            }
        )

    required_nets = sorted({row["net"] for row in configured_map if row["class"] != "reserved"})
    finish_port_nets = {
        str(port.get("net"))
        for port in interface.get("ports", [])
        if port.get("net")
    }
    finish_specialnet_nets = {
        str(net)
        for net in interface.get("specialnet_nets", [])
        if net
    }
    finish_boundary_nets = finish_port_nets | finish_specialnet_nets
    missing_interface_nets = sorted(set(required_nets) - finish_boundary_nets)
    interface_net_coverage = bool(required_nets) and not missing_interface_nets
    interface["package_nets"] = required_nets
    interface["boundary_nets"] = sorted(finish_boundary_nets)
    interface["missing_package_nets"] = missing_interface_nets
    observed_routes = {
        row["net"]: row for row in observed_rdl["nets"] if row.get("net") in required_nets
    }
    routed_nets = sorted(
        net
        for net in required_nets
        if observed_routes.get(net, {}).get("routed") is True
    )
    mapped_nets = sorted({str(row["observed_net"]) for row in bump_rows if row.get("observed_net")})
    unique_configured = len({row["instance"] for row in configured_map}) == len(configured_map)
    power_map = [row for row in configured_map if row["class"] == "power"]
    ground_map = [row for row in configured_map if row["class"] == "ground"]
    signal_map = [row for row in configured_map if row["class"] == "signal"]
    configured_observed_count = sum(
        1
        for row in configured_map
        if row["instance"] in observed_by_bump
        and observed_by_net.get(row["instance"]) == row["net"]
    )
    mapping_complete = bool(configured_map) and (
        configured_observed_count == len(configured_map)
    )

    package = cfg.get("package") if isinstance(cfg.get("package"), dict) else {}
    n_supply_bumps = max(int(package.get("n_bumps") or 0), 0)
    r_bump = float(package.get("r_bump") or 0.0)
    l_bump = float(package.get("l_bump") or 0.0)
    r_pkg = float(package.get("r_pkg") or 0.0)
    l_pkg = float(package.get("l_pkg") or 0.0)
    c_pkg = float(package.get("c_pkg") or 0.0)
    effective_r = r_pkg + (r_bump / n_supply_bumps if n_supply_bumps else 0.0)
    effective_l = l_pkg + (l_bump / n_supply_bumps if n_supply_bumps else 0.0)
    resonance_hz = (
        1.0 / (2.0 * math.pi * math.sqrt(effective_l * c_pkg))
        if effective_l > 0 and c_pkg > 0
        else None
    )

    system_path = system_report_path(root, variant)
    system = read_json(system_path) or {}
    transient = system.get("transient") if isinstance(system.get("transient"), dict) else {}
    impedance = system.get("impedance") if isinstance(system.get("impedance"), dict) else {}
    system_ok = system.get("ok") is True
    rdl_ready = bool(rdl_def.is_file() and rdl_odb.is_file())
    rdl_coverage_ok = bool(required_nets) and len(routed_nets) == len(required_nets)
    finish_ok = finish_odb.is_file() and finish_def.is_file()
    model_ok = bool(cfg) and bool(array) and bool(configured_map)
    bump_structure_ok = (
        unique_configured
        and coordinates_ok
        and bool(power_map)
        and bool(ground_map)
        and bool(signal_map)
    )
    bump_ok = bump_structure_ok and mapping_complete and not conflicts
    evidence_ok = (
        finish_ok
        and model_ok
        and interface_net_coverage
        and bump_ok
        and rdl_ready
        and rdl_coverage_ok
        and system_ok
    )

    if (
        not finish_ok
        or not model_ok
        or not interface_net_coverage
        or not bump_structure_ok
        or not mapping_complete
    ):
        overall = "GAP"
    elif not rdl_ready or not system_ok:
        overall = "GAP"
    elif not rdl_coverage_ok or conflicts:
        overall = "FAIL"
    else:
        overall = "PROXY"

    provenance = [
        artifact(root, "finish_odb", finish_odb, "finish"),
        artifact(root, "finish_def", finish_def, "finish"),
        artifact(root, "finish_spef", finish / "6_final.spef", "finish"),
        artifact(root, "package_config", cfg_path, "source"),
        artifact(root, "bump_lef", bump_lef_path(root, variant), "source"),
        artifact(
            root,
            "rdl_script",
            root / "learn" / "scripts" / ("lab_asap7_pkg_rdl.tcl" if is_lab_variant(variant) else "pkg_rdl_sidecar.tcl"),
            "source",
        ),
        artifact(root, "rdl_odb", rdl_odb, "generated"),
        artifact(root, "rdl_def", rdl_def, "generated"),
        artifact(root, "system_pdn_report", system_path, "generated"),
    ]
    fingerprint_material = [
        f"variant={variant}",
        json.dumps(array, sort_keys=True),
        json.dumps(configured_map, sort_keys=True),
    ] + [f"{row['role']}={row['sha256'] or 'missing'}" for row in provenance]
    input_fingerprint = hashlib.sha256("\n".join(fingerprint_material).encode()).hexdigest()

    checks = [
        {
            "id": "finish_checkpoint",
            "label": "Finish ODB + DEF",
            "status": "PASS" if finish_ok else "GAP",
            "ok": finish_ok,
            "required": True,
            "detail": relative_path(root, finish),
        },
        {
            "id": "package_model",
            "label": "Versioned package model",
            "status": "PASS" if model_ok else "GAP",
            "ok": model_ok,
            "required": True,
            "detail": relative_path(root, cfg_path),
        },
        {
            "id": "finish_interface_nets",
            "label": "Configured package nets present in finish boundary",
            "status": "PASS" if interface_net_coverage else "GAP",
            "ok": interface_net_coverage,
            "required": True,
            "detail": f"{len(required_nets) - len(missing_interface_nets)}/{len(required_nets)} configured nets found in finish PINS/SPECIALNETS",
            "missing_nets": missing_interface_nets,
        },
        {
            "id": "bump_map_unique",
            "label": "Unique bump assignment",
            "status": "PASS" if unique_configured and not conflicts else "FAIL",
            "ok": unique_configured and not conflicts,
            "required": True,
            "detail": f"{len(configured_map)} configured · power {len(power_map)} · ground {len(ground_map)} · signal {len(signal_map)}",
        },
        {
            "id": "bump_map_observed",
            "label": "Configured bumps observed and net-matched",
            "status": "PASS" if mapping_complete else "GAP",
            "ok": mapping_complete,
            "required": True,
            "detail": f"{configured_observed_count}/{len(configured_map)} configured bumps observed with expected nets",
            "coordinates_ok": coordinates_ok,
        },
        {
            "id": "power_return_pair",
            "label": "Power / return mapping",
            "status": "PASS" if power_map and ground_map else "GAP",
            "ok": bool(power_map and ground_map),
            "required": True,
            "detail": "VDD/VSS are assigned to distinct bump instances" if power_map and ground_map else "power or ground bump missing",
        },
        {
            "id": "rdl_net_coverage",
            "label": "RDL route coverage per net",
            "status": "PASS" if rdl_coverage_ok else "GAP" if not rdl_ready else "FAIL",
            "honesty": "PROXY" if rdl_coverage_ok else "GAP" if not rdl_ready else "PARTIAL",
            "ok": rdl_coverage_ok,
            "evidence_ok": rdl_coverage_ok,
            "required": True,
            "detail": f"{len(routed_nets)}/{len(required_nets)} required nets routed",
            "routed_nets": routed_nets,
            "missing_nets": sorted(set(required_nets) - set(routed_nets)),
        },
        {
            "id": "system_pdn_live",
            "label": "Live System PDN",
            "status": "PASS" if system_ok else "GAP",
            "ok": system_ok,
            "required": True,
            "detail": relative_path(root, system_path),
        },
        {
            "id": "product_boundary",
            "label": "Product signoff boundary",
            "status": "WARN",
            "honesty": "PROXY",
            "ok": False,
            "required": False,
            "detail": "Dummy bump/RDL and compact ladder cannot close Product signoff",
        },
    ]

    status_axis = "pass" if evidence_ok else "fail" if overall == "FAIL" else "blocked"
    lab_contract = {}
    if is_lab_variant(variant):
        tool_status = status_axis
        honesty = "PROXY" if overall == "PROXY" else "PARTIAL" if overall == "FAIL" else "GAP"
        lab_contract = {
            # `status` remains the historical manifest vocabulary for callers
            # that consume package manifests. `status_axis` is the frozen
            # Lab tool outcome; PROXY belongs on honesty, never on that axis.
            "surface": "lab_asap7",
            "track": "asap7",
            "mesh_id": "asap7_pkg_tier_c",
            "topology": "pkg",
            "status_axis": tool_status,
            "honesty": honesty,
            "honesty_reason": "Community dummy bump/RDL/compact package evidence; not C4 or foundry signoff.",
            "ok_claim": False,
            "product_win": False,
            "productWin": False,
            "win_eligible": False,
            "comparable_to_gold_ir": False,
            "run_id": variant,
            "report_id": f"asap7-pkg-manifest-{variant}",
            "report_paths": [relative_path(root, default_output_path(root, variant))],
            "results_dir": relative_path(root, finish),
            "tool_id": "community_package_ladder",
            "license_class": "community-open-source",
            "mesh_fingerprint": f"sha256:{input_fingerprint}",
            "leftovers": [
                {"id": "dummy_bump", "message": "Dummy bump model is not JEDEC C4."},
                {"id": "rdl_sidecar", "message": "RDL output remains a sidecar and never replaces 6_final.odb."},
                {"id": "thermal_model_missing", "message": "No compact thermal model is included."},
            ],
            "pillars": {
                "pkg": {
                    "status": tool_status,
                    "honesty": honesty,
                    "honesty_reason": "Community package ladder; not foundry signoff.",
                    "leftovers": [
                        {"id": "dummy_bump", "message": "Dummy bump model is not JEDEC C4."},
                        {"id": "rdl_sidecar", "message": "RDL output remains a sidecar."},
                    ],
                },
                "thermal": {
                    "status": "not_run",
                    "honesty": "GAP",
                    "honesty_reason": "No compact thermal model is included.",
                    "leftovers": [{"id": "thermal_model_missing", "message": "Thermal evidence is not run."}],
                },
            },
            "signoff_all": {"ok": False, "reason": "Package Lab evidence is not Product signoff."},
        }

    report_status = status_axis if is_lab_variant(variant) else overall
    return {
        "schema_version": 2,
        "kind": "package_manifest",
        "scope": "package",
        "variant": variant,
        "design": "gcd",
        "checkpoint": {
            "stage": "finish",
            "result_dir": relative_path(root, finish),
            "finish_immutable": True,
            "ready": finish_ok,
        },
        "status": report_status,
        "legacy_status": overall if is_lab_variant(variant) else None,
        "evidence_ok": evidence_ok,
        "product_signoff": False,
        "comparison_scope": "same-live-invocation",
        "oracle": "current-finish-snapshot",
        "interface": interface,
        "bump_array": {
            "master": array.get("master"),
            "rows": array.get("rows"),
            "columns": array.get("columns"),
            "origin_um": array.get("origin_um") or array.get("origin"),
            "pitch_um": array.get("pitch_um") or array.get("pitch"),
            "configured_count": len(configured_map),
            "observed_component_count": len(observed_bumps),
            "configured_observed_count": configured_observed_count,
            "mapping_complete": mapping_complete,
            "coordinate_bounds_ok": coordinates_ok,
            "assigned_count": sum(1 for row in bump_rows if row.get("assigned")),
            "unassigned_instances": [row["instance"] for row in bump_rows if not row.get("assigned")],
            "map": bump_rows,
        },
        "rdl": {
            "input_odb": relative_path(root, finish_odb),
            "sidecar_odb": relative_path(root, rdl_odb),
            "sidecar_def": relative_path(root, rdl_def),
            "ready": rdl_ready,
            "layers": observed_rdl["layers"],
            "route_segments": observed_rdl["route_segments"],
            "route_length_um_est": observed_rdl["route_length_um_est"],
            "required_nets": required_nets,
            "routed_nets": routed_nets,
            "missing_nets": sorted(set(required_nets) - set(routed_nets)),
            "mapped_nets": mapped_nets,
            "conflicts": conflicts,
            "nets": observed_rdl["nets"],
        },
        "electrical_model": {
            "vdd": cfg.get("vdd"),
            "n_supply_bumps": n_supply_bumps,
            "mapped_power_bumps": len(power_map),
            "mapped_ground_bumps": len(ground_map),
            "sparse_breakout": len(power_map) < n_supply_bumps,
            "r_bump_ohm": r_bump,
            "l_bump_h": l_bump,
            "r_pkg_ohm": r_pkg,
            "l_pkg_h": l_pkg,
            "c_pkg_f": c_pkg,
            "effective_supply_r_ohm": effective_r,
            "effective_supply_l_h": effective_l,
            "series_resonance_hz_est": resonance_hz,
            "model_kind": "lumped-vrm-board-package-die",
            "qualification": "educational compact model; no board S-parameter",
        },
        "system_pdn": {
            "report": relative_path(root, system_path),
            "ok": system_ok,
            "engine": system.get("engine"),
            "i_die_avg_a": system.get("i_die_avg_a"),
            "droop_mv": transient.get("droop_mv"),
            "droop_pct": transient.get("droop_pct"),
            "z_max_mohm": impedance.get("z_max_mohm"),
            "f_at_zmax_hz": impedance.get("f_at_zmax_hz"),
            "z_target_mohm": impedance.get("z_target_mohm"),
            "pass_target": impedance.get("pass_target"),
        },
        "checks": checks,
        "provenance": {
            "input_fingerprint": input_fingerprint,
            "artifacts": provenance,
        },
        "limits": {
            "bump_model": "dummy LEF; not JEDEC C4 or foundry bump qualification",
            "rdl_model": "OpenROAD rdl_route sidecar; not a tapeout redistribution stack",
            "system_model": "lumped RLC ladder; not Touchstone/Ansys CPA",
            "signoff": "package evidence never creates a Product badge",
        },
        "summary": (
            f"PKG {overall} · bumps {len(configured_map)} configured/{len(observed_bumps)} observed · "
            f"RDL {len(routed_nets)}/{len(required_nets)} nets · "
            f"System droop {float(transient.get('droop_mv') or 0.0):.2f} mV"
        ),
        **lab_contract,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a live PKG interface manifest")
    parser.add_argument("--variant", default="flowlab")
    parser.add_argument("--out")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    variant = validate_variant(args.variant)
    manifest = build_manifest(root, variant)
    output = Path(args.out).resolve() if args.out else default_output_path(root, variant)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PKG_MANIFEST_JSON {output}")
    print(manifest["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
