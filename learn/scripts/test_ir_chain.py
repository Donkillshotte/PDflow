#!/usr/bin/env python3
"""Static / dynamic IR and EM stay on their own meshes. Gold is not restamped."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
GOLD_MV = 45.298


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def load(name: str) -> dict:
    path = REPORTS / name
    check(path.is_file(), f"{name} exists")
    return json.loads(path.read_text())


def main() -> int:
    gold = load("dynamic_ir_flowlab.json")
    check(gold.get("gold") is True, "dynamic IR gold sentinel")
    check(abs(float(gold["worst_droop_mv"]) - GOLD_MV) < 0.02, "gold 45.298")

    chip = load("pdn_chip_ir_flowlab.json")
    static_v = float((chip.get("static") or {}).get("worst_ir") or 0)
    static_mv = static_v * 1000.0
    check(0.1 < static_mv < 50.0, f"chip static IR rail-scale ({static_mv:.3f} mV)")
    check(abs(static_mv - GOLD_MV) > 1.0, "chip static is not gold 45.298")
    tran_mv = float((chip.get("transient") or {}).get("worst_droop") or 0) * 1000.0
    check(tran_mv > 0, f"chip transient droop {tran_mv:.3f} mV")

    pwr = load("power_signoff_flowlab.json")
    check(pwr.get("ok") is True, "power signoff ok")
    sys_mv = float((pwr.get("power") or {}).get("system_droop_mv") or 0)
    check(sys_mv > 0, f"system droop {sys_mv:.3f} mV")
    ledger = pwr.get("ir_mesh_ledger") or {}
    check(ledger.get("comparable") is False, "IR mesh ledger is not comparable")
    meshes = {m.get("id"): m for m in (ledger.get("meshes") or [])}
    check("gold_dynamic_ir" in meshes, "ledger names gold Dynamic IR")
    check(abs(float(meshes["gold_dynamic_ir"]["dynamic_mv"]) - GOLD_MV) < 0.02, "ledger gold is 45.298")
    check(meshes["gold_dynamic_ir"].get("gold") is True, "ledger gold flag")
    check("chip_pdn" in meshes, "ledger names chip PDN")
    check(abs(float(meshes["chip_pdn"]["static_mv"]) - GOLD_MV) > 1.0, "ledger chip is not gold")
    check("current_run_dynamic_ir" in meshes, "ledger names current_run")
    check(meshes["current_run_dynamic_ir"].get("gold") is False, "current_run is not gold")
    check("vyges_em_ir" in meshes, "ledger names vyges")
    check(meshes["vyges_em_ir"].get("em_checked") == 0, "ledger EM stays unchecked")
    check("system_pdn" in meshes, "ledger names system PDN")
    gold_v = float(meshes["gold_dynamic_ir"]["dynamic_mv"])
    chip_v = float(meshes["chip_pdn"]["static_mv"])
    cur_v = float(meshes["current_run_dynamic_ir"]["dynamic_mv"])
    vy_v = float(meshes["vyges_em_ir"]["static_mv"])
    check(len({round(gold_v, 2), round(chip_v, 2), round(cur_v, 2), round(vy_v, 2)}) == 4, "ledger meshes stay distinct")

    em = REPORTS / "vyges_em_ir_flowlab.json"
    if em.is_file():
        blob = json.loads(em.read_text())
        check(blob.get("ok") is True, "vyges-em-ir ok")
        drop = ((blob.get("vyges") or {}).get("worst_ir") or {}).get("drop")
        if drop is not None:
            drop_mv = float(drop) * 1000.0
            check(drop_mv > 0, f"vyges static drop {drop_mv:.2f} mV")
            check(abs(drop_mv - GOLD_MV) > 1.0, "vyges mesh is not gold 45.298")
        em_checked = (blob.get("vyges") or {}).get("em_checked")
        if em_checked is not None:
            check(int(em_checked) == 0, "Nangate45 has no emlimit; EM stays unchecked")
        check(blob.get("limits_met") is False, "vyges limits_met stays false without emlimit")
        check("em_checked 0" in str(blob.get("summary")), "vyges summary names unchecked EM")

    print("ALL test_ir_chain PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
