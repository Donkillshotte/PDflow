#!/usr/bin/env python3
"""Live ASAP7 RTL→GDS checks. No gold numbers. Does not recook unless asked."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from dse.asap7_lab import LabAsap7Spec, collect_report, result_dir, scan_folio, validate

ROOT = Path(__file__).resolve().parents[2]
GOLD_IR = ROOT / "learn/sim/reports/dynamic_ir_flowlab.json"
GOLD_GDS = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds"
GOLD_RPT = ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json"

# Locked Nangate hashes. If these change, someone restamped gold.
GOLD_IR_SHA = "938e122b1d25a3a4064134f0fa56a04357eb571d683ecedc67f089cf0dea850a"
GOLD_GDS_SHA = "439f5eba0de2abd61d6c14328c8ac4d966dee085e9c51687b8ee09182244bcb3"
GOLD_RPT_SHA = "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def assert_nangate_gold_untouched() -> None:
    check(GOLD_IR.is_file(), "Nangate gold IR file still exists")
    check(sha256(GOLD_IR) == GOLD_IR_SHA, "Nangate gold IR sha unchanged")
    check(GOLD_GDS.is_file(), "locked FlowLab GDS still exists")
    check(sha256(GOLD_GDS) == GOLD_GDS_SHA, "locked FlowLab GDS sha unchanged")
    check(GOLD_RPT.is_file(), "locked FlowLab 6_report still exists")
    check(sha256(GOLD_RPT) == GOLD_RPT_SHA, "locked FlowLab 6_report sha unchanged")
    text = GOLD_IR.read_text()
    check("45.298" in text, "Nangate gold still names 45.298")


def check_live_cook(spec: LabAsap7Spec, *, must_exist: bool) -> dict | None:
    spec = validate(spec)
    out = result_dir(spec, ROOT)
    gds = out / "6_final.gds"
    defn = out / "6_final.def"
    odb = out / "6_final.odb"
    log = (
        ROOT
        / "tools/OpenROAD-flow-scripts/flow/logs/asap7"
        / spec.nickname
        / spec.variant
        / "6_report.json"
    )
    if not gds.is_file():
        if must_exist:
            raise SystemExit(f"FAIL live GDS missing {gds}")
        print(f"skip live cook {spec.variant} (no GDS yet)")
        return None
    check(gds.stat().st_size > 10_000, f"{spec.variant} GDS has bytes ({gds.stat().st_size})")
    check(defn.is_file(), f"{spec.variant} DEF exists")
    check(odb.is_file(), f"{spec.variant} ODB exists")
    check(log.is_file(), f"{spec.variant} live 6_report.json in logs")
    metrics = json.loads(log.read_text())
    check("finish__timing__setup__ws" in metrics, f"{spec.variant} live WNS key")
    check("finish__design__instance__area__stdcell" in metrics, f"{spec.variant} live area key")
    check("finish__power__total" in metrics, f"{spec.variant} live power key")
    check("finish__power__leakage__total" in metrics, f"{spec.variant} live leakage key")
    check(
        "finish__design_powergrid__drop__worst__net:VDD__corner:default" in metrics,
        f"{spec.variant} live IR key",
    )
    payload = collect_report(spec, root=ROOT)
    check(payload["ok"] is True, f"{spec.variant} collect_report ok")
    check("gold_ir_mv" not in payload, f"{spec.variant} report has no gold_ir_mv")
    check("45.298" not in json.dumps(payload), f"{spec.variant} report has no 45.298")
    check(payload["comparable_to_gold_ir"] is False, f"{spec.variant} not comparable to Nangate IR")
    check(payload["product_win"] is False, f"{spec.variant} not a product win")
    qor = payload["qor"]
    check(qor.get("wns_ps") is not None, f"{spec.variant} WNS {qor.get('wns_ps')}")
    check(qor.get("area_um2") is not None, f"{spec.variant} area {qor.get('area_um2')}")
    check(qor.get("power_w") is not None, f"{spec.variant} power {qor.get('power_w')}")
    check(qor.get("leakage_w") is not None, f"{spec.variant} leakage {qor.get('leakage_w')}")
    check(qor.get("ir_vdd_worst_v") is not None, f"{spec.variant} IR {qor.get('ir_vdd_worst_v')}")
    check(qor.get("period_min_ps") is not None, f"{spec.variant} period_min {qor.get('period_min_ps')}")
    check(qor.get("fmax_ghz") is not None, f"{spec.variant} fmax {qor.get('fmax_ghz')}")
    print(
        f"live {spec.variant}: WNS {qor['wns_ps']} ps area {qor['area_um2']} "
        f"power {qor['power_w']} leak {qor['leakage_w']} IR {qor['ir_vdd_worst_v']}"
    )
    return payload


def main() -> None:
    assert_nangate_gold_untouched()
    frozen = ROOT / "learn/sim/reports/lab_asap7_gcd_6_report.json"
    check(not frozen.is_file(), "no frozen ASAP7 6_report golden copy")

    nldm = check_live_cook(LabAsap7Spec(), must_exist=True)
    check(nldm is not None, "NLDM TC GCD cook is live")

    ccs = check_live_cook(
        LabAsap7Spec(design="gcd-ccs", corner="BC", lib_model="CCS"),
        must_exist=True,
    )
    wc = check_live_cook(LabAsap7Spec(corner="WC"), must_exist=True)
    bc = check_live_cook(LabAsap7Spec(corner="BC"), must_exist=True)
    lvt = check_live_cook(LabAsap7Spec(vt=("RVT", "LVT")), must_exist=True)
    mbff = check_live_cook(LabAsap7Spec(cluster_flops=True), must_exist=True)
    uart = check_live_cook(LabAsap7Spec(design="uart"), must_exist=True)
    open430 = check_live_cook(LabAsap7Spec(clk_ps=430), must_exist=True)
    check(open430 is not None, "430 ps gcd TC GDS is live (may still be open)")
    closed = check_live_cook(LabAsap7Spec(clk_ps=480), must_exist=True)
    if closed is not None:
        check(closed["qor"].get("timing_closed") is True, "480 ps gcd TC is timing-closed")
        check(float(closed["qor"]["wns_ps"]) >= 0, f"480 ps WNS {closed['qor']['wns_ps']} >= 0")

    ccs_tc = check_live_cook(LabAsap7Spec(lib_model="CCS", corner="TC"), must_exist=True)
    ccs_wc = check_live_cook(LabAsap7Spec(lib_model="CCS", corner="WC"), must_exist=True)

    lvs_p = ROOT / "learn/sim/reports/lab_asap7_lvs.json"
    check(lvs_p.is_file(), "leftover-named ASAP7 LVS report exists")
    lvs = json.loads(lvs_p.read_text())
    check(lvs.get("lvs_closed") is False, "ASAP7 LVS is leftover-named, not closed")
    check(lvs.get("calibre") is False, "ASAP7 LVS is not Calibre")
    check(lvs.get("product_win") is False, "ASAP7 LVS is not a product win")
    check("gold_ir_mv" not in lvs, "ASAP7 LVS has no gold_ir_mv")
    check("45.298" not in lvs_p.read_text(), "ASAP7 LVS has no 45.298")
    check(float(lvs.get("match_pct") or 0) > 0, f"ASAP7 LVS match {lvs.get('match_pct')}")

    mmmc_p = ROOT / "learn/sim/reports/lab_asap7_mmmc.json"
    check(mmmc_p.is_file(), "ASAP7 setup/hold pair report exists")
    mmmc = json.loads(mmmc_p.read_text())
    check(mmmc.get("ok") is True, "ASAP7 MMMC pair ran")
    check(mmmc.get("product_win") is False, "ASAP7 MMMC is not a product win")
    check(mmmc.get("setup", {}).get("wns_ps") is not None, "ASAP7 setup WNS present")
    check(mmmc.get("hold", {}).get("wns_ps") is not None, "ASAP7 hold slack present")
    check("45.298" not in mmmc_p.read_text(), "ASAP7 MMMC has no 45.298")

    pdk_p = ROOT / "learn/sim/reports/lab_asap7_pdk.json"
    check(pdk_p.is_file(), "ASAP7 layer-1 PDK inventory exists")
    pdk = json.loads(pdk_p.read_text())
    check(pdk.get("ok") is True, "ASAP7 layer-1 public PDK is on disk")
    check(pdk.get("calibre_ready") is False, "ASAP7 Calibre decks are still gated")
    check(pdk.get("calibre_ran") is False, "ASAP7 layer-1 did not run Calibre")
    check(pdk.get("product_win") is False, "ASAP7 layer-1 is not a product win")
    check(int(pdk.get("n_pm") or 0) >= 3, f"ASAP7 layer-1 has HSpice cards ({pdk.get('n_pm')})")
    check("45.298" not in pdk_p.read_text(), "ASAP7 layer-1 inventory has no 45.298")

    folio = scan_folio(ROOT)
    check(len(folio) >= 8, f"folio has live cooks ({len(folio)})")
    check(all("gold_ir_mv" not in row for row in folio), "folio has no gold_ir_mv")
    check(all("45.298" not in json.dumps(row) for row in folio), "folio has no 45.298")
    check(any(row.get("timing_closed") for row in folio), "folio names a closed-timing cook")

    stamped = ROOT / "learn/sim/reports/lab_asap7.json"
    if stamped.is_file():
        live = json.loads(stamped.read_text())
        check("gold_ir_mv" not in live, "stamped lab report has no gold_ir_mv")
        check("45.298" not in stamped.read_text(), "stamped lab report has no 45.298")
        check(live.get("note") and "no gold stamp" in str(live["note"]).lower(), "live note denies gold stamp")

    tracked = subprocess.check_output(
        ["git", "ls-files", "--", "learn/sim/reports/lab_asap7.json", "learn/sim/reports/lab_asap7_gcd_6_report.json"],
        cwd=ROOT,
        text=True,
    ).strip()
    check(tracked == "", "no ASAP7 report is tracked as a golden")

    assert_nangate_gold_untouched()
    print(
        "ALL test_asap7_e2e PASSED "
        f"(ccs={'yes' if ccs else 'pending'} wc={'yes' if wc else 'pending'} "
        f"bc={'yes' if bc else 'pending'} lvt={'yes' if lvt else 'pending'} "
        f"mbff={'yes' if mbff else 'pending'} uart={'yes' if uart else 'pending'} "
        f"closed480={'yes' if closed else 'pending'} "
        f"ccs_tc={'yes' if ccs_tc else 'pending'} ccs_wc={'yes' if ccs_wc else 'pending'})"
    )


if __name__ == "__main__":
    main()
