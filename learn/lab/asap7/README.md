# Lab ASAP7 kit

Research track only. Predictive 7 nm FinFET. Not manufacturable.
Does not decide product wins. Does not replace the Nangate45 course.

## Cook (RTL → GDS)

```bash
# default: gcd, typical corner, RVT, NLDM, 7.5-track
FLOW_VARIANT=lab_asap7_gcd_tc_rvt_nldm_7p5 \
  ./scripts/run_lab_asap7.sh finish

# slow corner
CORNER=WC ./scripts/run_lab_asap7.sh finish

# multi-VT (primary + extra)
ASAP7_USE_VT="RVT LVT" ./scripts/run_lab_asap7.sh finish

# CCS (RVT + BC only in this ORFS pack)
LAB_ASAP7_DESIGN=gcd-ccs CORNER=BC LIB_MODEL=CCS ./scripts/run_lab_asap7.sh finish

# multi-bit FF clustering (uses *_FAKE.lib)
CLUSTER_FLOPS=1 ./scripts/run_lab_asap7.sh finish
```

Variant names are `lab_asap7_*`. `flowlab` / `learn` / `base` are refused.

## Corners and leftover

| Knob | Values | Leftover |
|---|---|---|
| `CORNER` | BC / TC / WC | — |
| `ASAP7_USE_VT` | RVT LVT SLVT SRAM | — |
| `LIB_MODEL` | NLDM / CCS | CCS is RVT+FF only |
| `ASAP7_TRACK` | 7p5 / 6 | 6T is fetch-gated, not a finish |
| `CLUSTER_FLOPS` | 0 / 1 | `*_FAKE.lib` |
| FakeRAM designs | `riscv32i-mock-sram` | blackbox SRAM |

6-track views (optional, not in git): `learn/scripts/fetch_asap7_sc6t.sh`.

IR on this track is a new mesh. `comparable_to_gold_ir` is false.
Gold Dynamic IR stays **45.298 mV** on Nangate `gcd/flowlab`.

See [`docs/asap7_research.md`](../../../docs/asap7_research.md).
