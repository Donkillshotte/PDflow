# Lab ASAP7 kit

Research track only. Predictive 7 nm FinFET. Not manufacturable.
Does not decide product wins. Does not replace the Nangate45 course.

## RTL → GDS

```bash
# default: gcd, typical corner, RVT, NLDM, 7.5-track
FLOW_VARIANT=lab_asap7_gcd_tc_rvt_nldm_7p5 \
  ./scripts/run_lab_asap7.sh finish

# slow corner (wrapper defaults CORE_UTILIZATION=40; 65% overflows CTS)
CORNER=WC ./scripts/run_lab_asap7.sh finish

# multi-VT (primary + extra)
ASAP7_USE_VT="RVT LVT" ./scripts/run_lab_asap7.sh finish

# CCS (RVT + BC in the slim pack; TC/WC when extras are fetched)
LAB_ASAP7_DESIGN=gcd-ccs CORNER=BC LIB_MODEL=CCS ./scripts/run_lab_asap7.sh finish
LIB_MODEL=CCS CORNER=TC ./scripts/run_lab_asap7.sh finish

# multi-bit FF clustering (uses *_FAKE.lib)
CLUSTER_FLOPS=1 ./scripts/run_lab_asap7.sh finish

# uart (slang.so leftover — wrapper uses Yosys when slang.so is missing)
LAB_ASAP7_DESIGN=uart ./scripts/run_lab_asap7.sh finish

# relaxed clock (tags the variant so it does not overwrite the 310 ps GDS)
# 430 ps stayed open (WNS −23). 480 ps closed on this image (WNS +5.4).
LAB_CLK_PS=480 ./scripts/run_lab_asap7.sh finish
```

Variant names are `lab_asap7_*`. `flowlab` / `learn` / `base` are refused.

## Corners and leftover

| Knob | Values | Leftover |
|---|---|---|
| `CORNER` | BC / TC / WC | — |
| `ASAP7_USE_VT` | RVT LVT SLVT SRAM | — |
| `LIB_MODEL` | NLDM / CCS | CCS TC/WC need fetched extras; LVT/SLVT CCS stays refused |
| `ASAP7_TRACK` | 7p5 / 6 | 6T is fetch-gated, not a finish |
| `CLUSTER_FLOPS` | 0 / 1 | `*_FAKE.lib` |
| FakeRAM designs | `riscv32i-mock-sram` | blackbox SRAM |

6-track views (optional, not in git): `learn/scripts/fetch_asap7_sc6t.sh`.
`minimal` skips `6_report` metrics (`SKIP_REPORT_METRICS=1`).
`riscv32i-mock-sram` is FakeRAM + a real core — not a gcd-scale e2e.
AES stays refused without `ALLOW_HEAVY_ANALYSIS=1`.

IR on this track is a new mesh. `comparable_to_gold_ir` is false.
Gold Dynamic IR stays **45.298 mV** on Nangate `gcd/flowlab`.

## Live runs (no gold stamp)

`learn/sim/reports/lab_asap7.json` is the last run. It is gitignored.
`learn/sim/reports/lab_asap7_folio.json` lists every live `lab_asap7_*` GDS.
Do not freeze numbers, do not copy `6_report.json` into `learn/sim/reports/`.
Check live GDS with `python3 learn/scripts/test_asap7_e2e.py`.
CCS/CDL extras (not Calibre): `learn/scripts/fetch_asap7_libextras.sh`.
Layer-1 public PDK (HSpice `.pm`, placeholder Calibre):
`learn/scripts/run_lab_asap7_pdk.sh` (fetch + inventory +
Xyce inverter, `level 72→107`). Never `.lvs.ok`.
Cell-vs-CDL: `python3 learn/scripts/lab_asap7_lvs.py` (never `.lvs.ok`).
Setup WC / hold BC on one netlist: `python3 learn/scripts/lab_asap7_mmmc.py`.

See [`docs/asap7_research.md`](../../../docs/asap7_research.md).
Close paths (three-layer kit, not leftover-free):
[`docs/asap7_close_plan.md`](../../../docs/asap7_close_plan.md).
