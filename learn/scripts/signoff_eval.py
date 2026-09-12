#!/usr/bin/env python3
"""Evaluate current-run evidence against an explicit requirement policy.

Measurement validity and requirement closure are different facts. A native
tool can emit a finite WNS of -0.15 ns and 43 setup violations; the
measurement is parseable, but the timing requirement is not met. This module
therefore never treats finite numbers as a signoff pass.

Policies live in config/pdflow/requirements.json and are selected by the
design/PDK profile. Missing or null requirements produce GAP rather than an
invented threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _check(
    checks: list[dict],
    *,
    key: str,
    label: str,
    value,
    evidence_ok: bool,
    requirement_ok: bool | None,
    target,
    note: str,
) -> None:
    status = (
        "GAP"
        if not evidence_ok or requirement_ok is None
        else "PASS"
        if requirement_ok
        else "FAIL"
    )
    checks.append(
        {
            "id": key,
            "label": label,
            "actual": value,
            "target": target,
            "evidence_ok": bool(evidence_ok),
            "requirement_ok": requirement_ok,
            "status": status,
            "ok": bool(evidence_ok and requirement_ok is True),
            "note": note,
        }
    )


def _pillar_result(
    checks: list[dict],
    *,
    policy_source: str,
    missing: list[str] | None = None,
) -> dict:
    missing = missing or []
    if missing:
        return {
            "basis": "live-run",
            "status": "GAP",
            "checks": checks,
            "missing": missing,
            "evidence_ok": False,
            "requirement_ok": None,
            "ok": False,
            "policy_source": policy_source,
        }
    statuses = [str(check.get("status")) for check in checks]
    status = (
        "FAIL"
        if "FAIL" in statuses
        else "GAP"
        if "GAP" in statuses
        else "WARN"
        if "WARN" in statuses
        else "PASS"
    )
    return {
        "basis": "live-run",
        "status": status,
        "checks": checks,
        "evidence_ok": all(check.get("evidence_ok") is True for check in checks),
        "requirement_ok": status == "PASS",
        "ok": status == "PASS",
        "policy_source": policy_source,
    }


def evaluate_timing(metrics: dict, context: dict | None = None) -> dict:
    context = context or {}
    policy = context.get("policy") or {}
    checks: list[dict] = []
    missing: list[str] = []
    required = {
        "wns_ns": ("WNS (ns)", "wns_ns_min", "minimum"),
        "tns": ("TNS", "tns_min", "minimum"),
        "setup_violations": ("Setup violations", "setup_violations_max", "maximum"),
    }
    for key, (label, policy_key, direction) in required.items():
        if key not in metrics or metrics[key] is None:
            missing.append(key)
            continue
        value = _number(metrics[key])
        target = policy.get(policy_key)
        evidence_ok = value is not None and (
            key != "setup_violations" or value.is_integer()
        )
        requirement_ok = None
        if evidence_ok and target is not None:
            requirement_ok = (
                value >= float(target)
                if direction == "minimum"
                else value <= float(target)
            )
        _check(
            checks,
            key=key,
            label=label,
            value=(
                int(value)
                if key == "setup_violations" and value is not None and value.is_integer()
                else value
            ),
            evidence_ok=evidence_ok,
            requirement_ok=requirement_ok,
            target=target,
            note=(
                "WNS and TNS must meet the declared timing target"
                if key in {"wns_ns", "tns"}
                else "mandatory setup violations must meet the configured maximum"
            ),
        )

    if "period_min_ns" in metrics and metrics["period_min_ns"] is not None:
        value = _number(metrics["period_min_ns"])
        target = policy.get("period_min_ns_min")
        _check(
            checks,
            key="period_min_ns",
            label="period_min (ns)",
            value=value,
            evidence_ok=value is not None,
            requirement_ok=(
                None
                if value is None or target is None
                else value >= float(target)
            ),
            target=target,
            note="period_min qualifies only against the selected policy",
        )
    return _pillar_result(
        checks,
        policy_source=str(context.get("policy_source") or "missing policy"),
        missing=missing,
    )


def evaluate_geometry(metrics: dict, context: dict | None = None) -> dict:
    context = context or {}
    policy = context.get("policy") or {}
    checks: list[dict] = []
    missing: list[str] = []
    route_key = (
        "route_drc_violations"
        if "route_drc_violations" in metrics
        else "route_drc_lines"
    )
    for key, label, policy_key in (
        (route_key, "Route DRC violations", "route_drc_violations_max"),
        ("gds_drc_violations", "KLayout GDS DRC violations", "gds_drc_violations_max"),
    ):
        if key not in metrics:
            missing.append(key)
            continue
        value = _number(metrics[key])
        evidence_ok = value is not None and value.is_integer() and value >= 0
        _check(
            checks,
            key=key,
            label=label,
            value=int(value) if evidence_ok else value,
            evidence_ok=evidence_ok,
            requirement_ok=(
                None
                if not evidence_ok or policy.get(policy_key) is None
                else value <= float(policy[policy_key])
            ),
            target=policy.get(policy_key),
            note="mandatory geometry violations must meet the selected deck policy",
        )
    return _pillar_result(
        checks,
        policy_source=str(context.get("policy_source") or "missing policy"),
        missing=missing,
    )


def evaluate_equivalence(metrics: dict, context: dict | None = None) -> dict:
    context = context or {}
    policy = context.get("policy") or {}
    if "lvs_pass" not in metrics:
        return _pillar_result(
            [],
            policy_source=str(context.get("policy_source") or "missing policy"),
            missing=["lvs_pass"],
        )
    value = metrics["lvs_pass"]
    evidence_ok = isinstance(value, bool)
    target = policy.get("lvs_pass_required")
    checks: list[dict] = []
    _check(
        checks,
        key="lvs_pass",
        label="KLayout match",
        value=value,
        evidence_ok=evidence_ok,
        requirement_ok=None if not evidence_ok or target is None else value is bool(target),
        target=target,
        note="validated from the current layout/netlist comparison",
    )
    return _pillar_result(
        checks,
        policy_source=str(context.get("policy_source") or "missing policy"),
    )


def evaluate_power(metrics: dict, context: dict | None = None) -> dict:
    context = context or {}
    policy = context.get("policy") or {}
    checks: list[dict] = []
    for key, label, policy_key in (
        ("chip_static_ir_mv", "Chip static IR (mV)", "chip_static_ir_mv_max"),
        ("chip_transient_droop_mv", "Chip transient droop (mV)", "chip_transient_droop_mv_max"),
        ("system_droop_mv", "System droop (mV)", "system_droop_mv_max"),
        ("system_zmax_mohm", "System Zmax (mΩ)", "system_zmax_mohm_max"),
    ):
        if key not in metrics or metrics[key] is None:
            continue
        value = _number(metrics[key])
        target = policy.get(policy_key)
        _check(
            checks,
            key=key,
            label=label,
            value=value,
            evidence_ok=value is not None and value >= 0,
            requirement_ok=(
                None
                if value is None or target is None
                else value <= float(target)
            ),
            target=target,
            note="a configured limit is required for Product power signoff",
        )
    if not checks:
        return _pillar_result(
            checks,
            policy_source=str(context.get("policy_source") or "missing policy"),
            missing=["power metrics"],
        )
    return _pillar_result(
        checks,
        policy_source=str(context.get("policy_source") or "missing policy"),
    )


def load_policy(repo: Path, profile: str) -> tuple[dict, str]:
    path = repo / "config" / "pdflow" / "requirements.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"requirements policy unavailable: {path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), dict):
        raise ValueError("requirements policy has no profiles")
    selected = raw["profiles"].get(profile)
    if not isinstance(selected, dict):
        raise ValueError(f"requirements profile is not defined: {profile}")
    return selected, str(path.relative_to(repo))


def profile_for(metrics: dict, requested: str | None) -> str:
    if requested:
        return requested
    raw = str(metrics.get("profile") or "")
    if raw:
        return raw
    variant = str(metrics.get("variant") or "")
    return "asap7/gcd" if variant.startswith("lab_asap7_") else "nangate45/gcd"


def evaluate_pillar(name: str, metrics: dict, context: dict) -> dict:
    evaluators = {
        "timing": evaluate_timing,
        "geometry": evaluate_geometry,
        "equivalence": evaluate_equivalence,
        "power": evaluate_power,
    }
    return evaluators[name](metrics, context)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument(
        "--pillar",
        choices=["timing", "geometry", "equivalence", "power", "all"],
        required=True,
    )
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--profile", help="requirements profile, for example asap7/gcd")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    metrics = json.loads(args.metrics.read_text())
    if not isinstance(metrics, dict):
        raise ValueError("metrics JSON must be an object")
    profile = profile_for(metrics, args.profile)
    policy, policy_source = load_policy(args.repo, profile)
    names = ("timing", "geometry", "equivalence", "power")
    pillars = list(names) if args.pillar == "all" else [args.pillar]
    result = {
        "schema_version": 2,
        "pillar": args.pillar,
        "basis": "live-run",
        "profile": profile,
        "policy_source": policy_source,
        "pillars": {},
    }
    for pillar in pillars:
        pillar_policy = policy.get(pillar)
        result["pillars"][pillar] = evaluate_pillar(
            pillar,
            metrics.get(pillar, metrics),
            {
                "policy": pillar_policy if isinstance(pillar_policy, dict) else {},
                "policy_source": policy_source,
            },
        )
    result["status"] = (
        "FAIL"
        if any(item.get("status") == "FAIL" for item in result["pillars"].values())
        else "GAP"
        if any(item.get("status") == "GAP" for item in result["pillars"].values())
        else "PASS"
    )
    result["ok"] = result["status"] == "PASS"
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
