"""DSE metric contracts: dominates, gated Pareto, HV, EHVI.

Extracted from test_dse.py head (passo D.1). test_dse.main() still calls this.
Same check() messages as the inlined block.
"""
from __future__ import annotations

from dse.metrics import (
    QoR,
    dominates,
    dominates_with_fidelity,
    merge_sta_into_qor,
    pareto_front,
    pareto_front_gated,
    qor_delta,
    tns_cost_from_tns_ns,
    wns_cost_from_slack_ns,
)
from dse.mo import ehvi_2d, hypervolume_2d
from dse.sta_f3 import parse_sta_power


def check_metrics(check) -> None:
    a = QoR(area_um2=10, dynamic_ir_mv=40)
    b = QoR(area_um2=12, dynamic_ir_mv=40)
    c = QoR(area_um2=11, dynamic_ir_mv=30)
    check(dominates(a, b), "smaller area dominates equal IR")
    check(not dominates(b, a), "worse area does not dominate")
    check(not dominates(a, c), "trade-off is not domination")
    check(not dominates(c, a), "the other side of the trade-off neither")
    gap = QoR(area_um2=1.0)
    only_ir = QoR(dynamic_ir_mv=1.0)
    check(not dominates(gap, only_ir), "disjoint metrics do not dominate")
    rich = QoR(area_um2=12, dynamic_ir_mv=50)
    ir_only = QoR(dynamic_ir_mv=40)
    check(not dominates(ir_only, rich), "sparser F4 must not dominate a richer F2 point")
    check(wns_cost_from_slack_ns(0.04) == -0.04, "positive slack is a lower wns_cost")
    check(tns_cost_from_tns_ns(-1.2) == 1.2, "more negative TNS is a higher tns_cost")
    log = (
        "Group            Internal  Switching    Leakage      Total\n"
        "Sequential       1.00e-05   2.00e-06    3.00e-07   1.23e-05\n"
        "Combinational    4.00e-05   5.00e-06    6.00e-07   4.56e-05\n"
        "Total            5.00e-05   7.00e-06    9.00e-07   5.79e-05\n"
    )
    pwr = parse_sta_power(log)
    check(abs(pwr["leakage_w"] - 9.00e-07) < 1e-15, f"parse leakage, got {pwr}")
    check(abs(pwr["power_w"] - 5.79e-05) < 1e-15, f"parse total, got {pwr}")
    check(abs(pwr["internal_power_w"] - 5.00e-05) < 1e-15, "parse internal")
    check(abs(pwr["switching_power_w"] - 7.00e-06) < 1e-15, "parse switching")
    check(parse_sta_power("no table") == {}, "missing power table is empty, not invented")
    q_sta = merge_sta_into_qor(
        QoR(area_um2=409.108, n_cells=248, fidelity="F3"),
        {"wns_ns": -0.52, "tns_ns": -2.1, **pwr},
    )
    check(q_sta.tns_cost == 2.1 and q_sta.leakage_w == 9.00e-07, "merge_sta stamps TNS and leakage")
    d_leak = qor_delta(
        QoR(leakage_w=1e-6, power_w=1e-4, fidelity="F3"),
        QoR(leakage_w=2e-6, power_w=1e-4, fidelity="F3"),
    )
    check(abs(d_leak["leakage_w"] - (-1e-6)) < 1e-18, "leakage improvement is signed delta")
    check("internal_power_w" not in d_leak, "internal/switching are not Pareto delta axes")
    split_a = QoR(power_w=1.0, leakage_w=0.4, internal_power_w=0.1, switching_power_w=0.5)
    split_b = QoR(power_w=1.0, leakage_w=0.4, internal_power_w=0.9, switching_power_w=0.1)
    check(
        not dominates(split_a, split_b) and not dominates(split_b, split_a),
        "internal/switching split is observation, not a Pareto axis",
    )
    check(
        dominates(QoR(power_w=1.0, leakage_w=0.1), QoR(power_w=1.0, leakage_w=0.5)),
        "lower leakage dominates equal total power",
    )
    check(
        not dominates(QoR(area_um2=10, hpwl_um=100), QoR(area_um2=12)),
        "HPWL-only vs area-only do not dominate (missing ≠ better)",
    )
    f1_leak = QoR(area_um2=10, leakage_w=1e-7, fidelity="F1")
    f5_leak = QoR(area_um2=10, leakage_w=2e-7, fidelity="F5")
    check(not dominates_with_fidelity(f1_leak, f5_leak), "F1 better leakage does not dominate F5")
    front = pareto_front([("a", a), ("b", b), ("c", c)])
    check(set(front) == {"a", "c"}, f"Pareto is a and c, got {front}")
    f1_wns = QoR(area_um2=10, wns_cost=0.1, fidelity="F1")
    f5_wns = QoR(area_um2=10, wns_cost=1.0, fidelity="F5")
    check(not dominates_with_fidelity(f1_wns, f5_wns), "F1 better WNS does not dominate F5")
    check(dominates_with_fidelity(QoR(area_um2=10, wns_cost=1.0, fidelity="F5"), QoR(area_um2=10, wns_cost=1.0, fidelity="F1")), "F5 dominates F1 at equal axes")
    check(dominates_with_fidelity(QoR(area_um2=8, fidelity="F1"), QoR(area_um2=12, fidelity="F5")), "area stays comparable across fidelity")
    check(set(pareto_front_gated([("f1", f1_wns), ("f5", f5_wns)])) == {"f1", "f5"}, "gated front keeps F1 and F5")

    hv = hypervolume_2d([(1.0, 5.0), (3.0, 2.0)], (10.0, 10.0))
    hv_dom = hypervolume_2d([(1.0, 5.0), (3.0, 2.0), (4.0, 6.0)], (10.0, 10.0))
    check(hv > 50.0, f"2-D HV of a known front, got {hv}")
    check(abs(hv - hv_dom) < 1e-9, "dominated point does not change HV")
    front_aw = [(400.0, 0.52), (410.0, 0.40)]
    ehvi_good = ehvi_2d(390.0, 5.0, 0.38, 0.02, front_aw, seed=1)
    ehvi_bad = ehvi_2d(430.0, 5.0, 0.70, 0.02, front_aw, seed=1)
    check(ehvi_good > ehvi_bad, f"EHVI prefers a point that can grow the front ({ehvi_good} vs {ehvi_bad})")
