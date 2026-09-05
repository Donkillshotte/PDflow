#!/usr/bin/env python3
"""Lab ASAP7 kit: corners / VT / CCS refuses. Does not cook."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from dse.asap7_lab import (
    LabAsap7Refuse,
    LabAsap7Spec,
    ccs_ready,
    collect_report,
    result_dir,
    scan_folio,
    spec_from_env,
    validate,
    write_constraint_sdc,
)

ROOT = Path(__file__).resolve().parents[2]


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> None:
    spec = validate(LabAsap7Spec())
    check(spec.variant.startswith("lab_asap7_"), f"default variant {spec.variant}")
    check(spec.variant == "lab_asap7_gcd_tc_rvt_nldm_7p5", spec.variant)
    check("flowlab" not in spec.variant, "variant is not flowlab")
    check(str(result_dir(spec, ROOT)).endswith("asap7/gcd/lab_asap7_gcd_tc_rvt_nldm_7p5"), "write path is asap7")
    check("nangate45/gcd/flowlab" not in str(result_dir(spec, ROOT)), "does not write locked FlowLab")

    for bad in (
        LabAsap7Spec(corner="XX"),
        LabAsap7Spec(lib_model="CCS", vt=("LVT",)),
        LabAsap7Spec(track="6"),
        LabAsap7Spec(design="aes"),
    ):
        try:
            validate(bad, root=ROOT, allow_heavy=False)
        except LabAsap7Refuse as exc:
            check("REFUSED" in str(exc), f"refuse {bad}")
        else:
            raise SystemExit(f"FAIL expected refuse {bad}")

    wc_ccs = LabAsap7Spec(lib_model="CCS", corner="WC")
    if ccs_ready("WC", "RVT", ROOT):
        validate(wc_ccs, root=ROOT, allow_heavy=False)
        check(True, "CCS WC accepted after leftover extras")
    else:
        try:
            validate(wc_ccs, root=ROOT, allow_heavy=False)
        except LabAsap7Refuse as exc:
            check("REFUSED" in str(exc), "CCS WC refused without extras")
        else:
            raise SystemExit("FAIL expected CCS WC refuse without extras")

    multi = validate(LabAsap7Spec(vt=("RVT", "LVT"), corner="WC"))
    check(multi.variant.endswith("wc_rvt+lvt_nldm_7p5"), multi.variant)

    ccs = validate(LabAsap7Spec(design="gcd-ccs", corner="BC", lib_model="CCS"))
    check("ccs" in ccs.variant and ccs.nickname == "gcd-ccs", ccs.variant)

    mb = validate(LabAsap7Spec(cluster_flops=True))
    check(mb.variant.endswith("mbff"), mb.variant)

    closed = validate(LabAsap7Spec(clk_ps=430))
    check(closed.variant == "lab_asap7_gcd_tc_rvt_nldm_7p5_430ps", closed.variant)
    same_clk = validate(LabAsap7Spec(clk_ps=310))
    check(same_clk.variant == "lab_asap7_gcd_tc_rvt_nldm_7p5", same_clk.variant)

    env_spec = spec_from_env({"CORNER": "BC", "ASAP7_USE_VT": "SLVT", "LIB_MODEL": "NLDM"})
    check(env_spec.corner == "BC" and env_spec.primary_vt == "SLVT", "env parse")

    wrap = ROOT / "scripts" / "run_lab_asap7.sh"
    check(wrap.is_file(), "run_lab_asap7.sh exists")
    text = wrap.read_text()
    check("run_signoff_all" not in text, "wrapper does not invoke the signoff orchestrator")
    check("nangate45/gcd-tutorial" not in text, "wrapper does not use Nangate tutorial")
    check("CORE_UTILIZATION" in text, "wrapper can pass a larger die without a design branch")
    check("CORE_UTILIZATION=40" in text, "wrapper defaults WC die to 40")
    check("slang.so" in text, "wrapper gates slang leftover on slang.so")
    check("current_design gcd" not in text, "wrapper does not hardcode current_design gcd")
    check("write_constraint_sdc" in text, "wrapper writes SDC in Python under set -u")
    sdc = write_constraint_sdc(ROOT / "learn/sim/dse/sdc/_test_asap7_430.sdc", 430, "uart")
    sdc_txt = sdc.read_text()
    check("current_design uart" in sdc_txt, "SDC uses the spec nickname")
    check("set clk_period 430" in sdc_txt, "SDC period is 430 ps")
    sdc.unlink()
    check("if design ==" not in text, "wrapper has no design-name branch")
    check("Live metrics only" in (ROOT / "learn/dse/asap7_lab.py").read_text(), "lab report is live, not gold")
    check((ROOT / "learn/scripts/fetch_asap7_libextras.sh").is_file(), "CCS/CDL fetch script exists")

    env = {**os.environ, "FLOW_VARIANT": "flowlab", "PYTHONPATH": f"{ROOT}/learn:{ROOT}/learn/scripts"}
    # Locked name cannot be forced: Python rebuilds the variant. Call wrapper with TRACK=6.
    r = subprocess.run(
        ["bash", str(wrap), "finish"],
        cwd=str(ROOT),
        env={**os.environ, "ASAP7_TRACK": "6", "PYTHONPATH": f"{ROOT}/learn:{ROOT}/learn/scripts"},
        text=True,
        capture_output=True,
    )
    check(r.returncode == 2 and "REFUSED" in (r.stderr + r.stdout), f"wrapper refuses 6T ({r.returncode})")

    gold = ROOT / "learn/sim/reports/dynamic_ir_flowlab.json"
    check(gold.is_file(), "gold IR report still on disk")
    locked = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds"
    check(locked.is_file(), "locked FlowLab GDS still on disk")

    payload = collect_report(spec, root=ROOT)
    check(payload["product_win"] is False, "report is not a product win")
    check(payload["comparable_to_gold_ir"] is False, "IR not comparable to Nangate gold")
    check("gold_ir_mv" not in payload, "report has no gold_ir_mv")
    check("45.298" not in json.dumps(payload), "report has no 45.298")
    stamped = ROOT / "learn/sim/reports/lab_asap7.json"
    if stamped.is_file():
        live = json.loads(stamped.read_text())
        check(live.get("product_win") is False, "stamped report is not a product win")
        check("gold_ir_mv" not in live, "stamped report has no gold_ir_mv")
        check("45.298" not in stamped.read_text(), "stamped report has no 45.298")
        if live.get("ok"):
            check(live.get("gds"), "cooked report names GDS")
            check(live.get("qor", {}).get("wns_ps") is not None, "cooked report has WNS")
    gds = result_dir(spec, ROOT) / "6_final.gds"
    if gds.is_file():
        rows = scan_folio(ROOT)
        check(any(r["variant"] == spec.variant for r in rows), "folio lists live default cook")
        check(all("45.298" not in json.dumps(r) for r in rows), "folio has no 45.298")
        check(all("gold_ir_mv" not in r for r in rows), "folio has no gold_ir_mv")
    print("ALL test_asap7_lab PASSED")


if __name__ == "__main__":
    main()
