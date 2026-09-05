#!/usr/bin/env python3
"""Serial ASAP7 lab e2e runner. One heavy cook at a time. Not a product win.

Resume: skip live GDS unless --force. Never writes nangate45/gcd/flowlab.
Never restamps gold Dynamic IR 45.298 mV. Never launches AES by default.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dse.asap7_lab import (
    DESIGNS,
    LabAsap7Refuse,
    LabAsap7Spec,
    VARIANT_PREFIX,
    assert_nangate_gold_untouched,
    ccs_ready,
    cdl_ready,
    collect_report,
    default_plan_specs,
    make_env,
    plan_refuse,
    result_dir,
    uart_relaxed_spec,
    write_folio,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "learn" / "scripts"
WRAPPER = ROOT / "scripts" / "run_lab_asap7.sh"
REPORTS = ROOT / "learn" / "sim" / "reports"


def _clk_of(spec: LabAsap7Spec):
    return spec.clk_ps if spec.clk_ps is not None else DESIGNS[spec.design].get("clk_ps")


def all_plan_specs(root: Path) -> list[LabAsap7Spec]:
    return [*default_plan_specs(), uart_relaxed_spec(root)]


def planned_rows(root: Path) -> list[dict]:
    rows: list[dict] = []
    for spec in all_plan_specs(root):
        refuse = plan_refuse(spec, root)
        gds = result_dir(spec, root) / "6_final.gds"
        row = {
            "variant": spec.variant,
            "design": spec.design,
            "corner": spec.corner,
            "lib_model": spec.lib_model,
            "clk_ps": _clk_of(spec),
            "live": gds.is_file(),
            "refuse": refuse,
            "would_cook": refuse is None and not gds.is_file(),
        }
        if spec.design == "uart" and spec.clk_ps is not None:
            row["kind"] = "uart_relaxed"
        rows.append(row)
    return rows


def specs_from_only(name: str, root: Path) -> list[LabAsap7Spec]:
    name = name.strip()
    out = [s for s in all_plan_specs(root) if s.variant == name or s.design == name]
    if out:
        return out
    raise LabAsap7Refuse(f"REFUSED: --only {name} is not in the default ASAP7 e2e plan")


def cook_one(spec: LabAsap7Spec, *, force: bool) -> dict:
    gds = result_dir(spec, ROOT) / "6_final.gds"
    refuse = plan_refuse(spec, ROOT)
    if refuse:
        return {"variant": spec.variant, "action": "refuse", "reason": refuse, "ok": False}
    if gds.is_file() and not force:
        payload = collect_report(spec, root=ROOT)
        return {
            "variant": spec.variant,
            "action": "resume",
            "ok": bool(payload.get("gds_live")),
            "gds": payload.get("gds"),
        }
    proc = subprocess.run(
        ["bash", str(WRAPPER), "finish"],
        cwd=str(ROOT),
        env=make_env(spec),
        text=True,
    )
    payload = collect_report(spec, root=ROOT, extra={"exit_code": proc.returncode})
    write_report(payload, ROOT)
    return {
        "variant": spec.variant,
        "action": "cook",
        "ok": bool(payload.get("ok")),
        "exit_code": proc.returncode,
        "gds": payload.get("gds"),
        "stopped_at": payload.get("stopped_at"),
    }


def run_py(script: str, args: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'learn'}:{ROOT / 'learn' / 'scripts'}"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=str(ROOT),
        env=env,
    ).returncode


def run_analysis(closed_variants: list[str], drc_specs: list[LabAsap7Spec]) -> dict:
    analysis: dict = {"drc": {}, "lvs": {}, "mmmc": {}, "layer1": {}}
    if not (ROOT / "learn/lab/asap7/pdk").is_dir():
        analysis["layer1"] = {
            "status": "GAP",
            "reason": "learn/lab/asap7/pdk/ missing — run learn/scripts/fetch_asap7_pdk.sh",
        }
    else:
        run_py("lab_asap7_pdk.py", [])
        if (SCRIPTS / "lab_asap7_spice.py").is_file():
            run_py("lab_asap7_spice.py", [])
        analysis["layer1"] = {
            "status": "ran",
            "pdk": (REPORTS / "lab_asap7_pdk.json").is_file(),
            "spice": (REPORTS / "lab_asap7_spice.json").is_file(),
        }

    if not cdl_ready(ROOT):
        analysis["lvs"] = {
            "status": "GAP",
            "reason": "CDL not fetched — run learn/scripts/fetch_asap7_libextras.sh",
        }
    elif closed_variants:
        run_py("lab_asap7_lvs.py", ["--variant", closed_variants[0]])
        analysis["lvs"] = {"status": "ran", "variant": closed_variants[0]}
    else:
        analysis["lvs"] = {"status": "skip", "reason": "no closed finish yet"}

    for spec in drc_specs:
        if (result_dir(spec, ROOT) / "6_final.gds").is_file():
            run_py("lab_asap7_drc.py", ["--variant", spec.variant])
            analysis["drc"][spec.variant] = {"status": "ran"}

    if not closed_variants:
        analysis["mmmc"] = {"status": "skip", "reason": "no closed finish"}
    else:
        mmmc: dict = {}
        for variant in closed_variants:
            rc = run_py("lab_asap7_mmmc.py", ["--variant", variant])
            mmmc[variant] = {"status": "ran" if rc == 0 else "fail"}
        analysis["mmmc"] = mmmc
    return analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serial lab ASAP7 e2e. Not a product win.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--max-cooks", type=int, default=0, help="0 = no cap")
    parser.add_argument("--force", action="store_true", help="Recook live GDS (still refuses locked names)")
    parser.add_argument("--skip-analysis", action="store_true")
    args = parser.parse_args(argv)

    gold = assert_nangate_gold_untouched(ROOT, require_orfs=False)
    print(
        f"nangate gold untouched={gold['untouched']} lock_absent={gold['nangate_lock_absent']}",
        flush=True,
    )

    specs = specs_from_only(args.only, ROOT) if args.only else all_plan_specs(ROOT)
    plan = planned_rows(ROOT)
    if args.dry_run:
        payload = {
            "ok": True,
            "dry_run": True,
            "surface": "lab",
            "product_win": False,
            "comparable_to_gold_ir": False,
            "nangate_lock_absent": gold["nangate_lock_absent"],
            "ccs_tc_ready": ccs_ready("TC", "RVT", ROOT),
            "ccs_wc_ready": ccs_ready("WC", "RVT", ROOT),
            "plan": plan,
            "n_plan": len(plan),
            "note": "ASAP7 e2e dry-run. Live metrics only — no gold stamp.",
        }
        print(json.dumps(payload, indent=2))
        return 0

    cooked = 0
    results = []
    for spec in specs:
        if not spec.variant.startswith(VARIANT_PREFIX):
            results.append({"variant": spec.variant, "action": "refuse", "reason": "bad prefix", "ok": False})
            continue
        refuse = plan_refuse(spec, ROOT)
        live = (result_dir(spec, ROOT) / "6_final.gds").is_file()
        if refuse:
            results.append({"variant": spec.variant, "action": "refuse", "reason": refuse, "ok": False})
            continue
        if live and not args.force:
            results.append(cook_one(spec, force=False))
            continue
        if args.max_cooks and cooked >= args.max_cooks:
            results.append({"variant": spec.variant, "action": "budget", "reason": "max-cooks", "ok": False})
            continue
        row = cook_one(spec, force=args.force)
        results.append(row)
        if row.get("action") == "cook":
            cooked += 1

    closed = [
        spec.variant
        for spec in specs
        if (collect_report(spec, root=ROOT).get("qor") or {}).get("timing_closed")
    ]
    analysis: dict = {}
    if not args.skip_analysis:
        smoke = LabAsap7Spec()
        closed480 = LabAsap7Spec(clk_ps=480)
        drc_specs = [
            s
            for s in (smoke, closed480)
            if (result_dir(s, ROOT) / "6_final.gds").is_file()
        ]
        analysis = run_analysis(closed, drc_specs)

    folio = write_folio(ROOT)
    blob = json.loads(folio.read_text())
    blob["analysis"] = analysis
    blob["e2e"] = {
        "product_win": False,
        "comparable_to_gold_ir": False,
        "results": results,
        "nangate_lock_absent": gold["nangate_lock_absent"],
    }
    folio.write_text(json.dumps(blob, indent=2) + "\n")
    gold2 = assert_nangate_gold_untouched(ROOT, require_orfs=False)
    print(
        f"folio {folio} cooks={len(blob.get('cooks') or [])} gold_untouched={gold2['untouched']}",
        flush=True,
    )
    failed = [r for r in results if r.get("action") == "cook" and not r.get("ok")]
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabAsap7Refuse as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
