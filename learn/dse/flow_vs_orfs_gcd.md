# Standard ORFS flow vs DSE (GCD, nangate45, SDC 0.46 ns)

On-disk comparison, not marketing. Same design (`gcd` FlowLab), same PDK.
The standard flow is **one recipe** `make finish`. DSE is **layered search** on the
same toolchain (Yosys / OpenSTA / OpenROAD), with memory and
Pareto. It is not a signoff substitute.

Sources: `tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json`
and `3_5_place_dp.json`; DSE memory `learn/sim/dse/memory_flowlab.jsonl`
(140 rows, 137 ok); finish DirectLU `learn/sim/reports/dynamic_ir_flowlab_direct.json`
(`n_r=5816`).

## One-line verdict

ORFS wins the **closed chip** (timing after repair). DSE wins the **search
ORFS does not do**: architecture, per-cone ABC, PDN on the same extract, and
attributes (IR combo on `dpath` → local ABC, no longer ABC on the chip).

## Finish bake-off (run 2026-09-01)

Same `make finish`, DSE netlist only. Detail:
[`handoff_finish_bakeoff.md`](handoff_finish_bakeoff.md).

**A stays.** B smaller but WNS −338 ps. C “fast” WNS −187 ps and 198
repair buffers. Place A was +12 ps; B and C already late at DP.

## What is not comparable

| Pair | Why not |
|---|---|
| DSE mapped 407.5 µm² vs finish stdcell 940.3 µm² | Finish includes CTS, 132 timing-repair buffers (130 µm²), fill/tap. Yosys mapped ≠ legal die. |
| F5-lite WNS −641 ps vs finish WNS −37 ps | F5 is 2 DRT iter + SPEF, **without** `repair_timing`. Explicit contract: not `make finish`. |
| Catalog IR 1.705 mV vs DirectLU finish 6.075 mV | Different mesh (strap/EM `n_r≈3.6k`, knobs `pkg_l`). Not a finish win. |
| Leftover decap 3.942 mV vs finish 6.075 mV | Candidate extract `n_r=3432`, not the finish graph. |
| Ingest F2 ORFS (area 858.9, WNS cost 0.039, HPWL 2810) | Old snapshot. Live `6_report.json` is the finish source. |
| OpenROAD PSM 6.667 mV vs DirectLU 6.075 mV | Same order of magnitude, **different oracles**. |

Historical gold **45.298 mV** remains `reference_run` (sentinel). Current-run
DirectLU on finish is **6.075 mV**. Do not restamp gold.

## Table (same design, different axes)

| Axis | ORFS `make finish` | DSE (best honest) | Who wins |
|---|---|---|---|
| Setup WNS | **−37.2 ps** (signoff-ish, 38 viol) | Ideal STA **−114 ps** (`abc_speed` @ 619 µm²). F5-lite **−641 ps**. F5-local **−157 ps** (size-up, not a chip). | **ORFS** on chip. DSE finds ABC ORFS does not search, but does not close timing. |
| TNS setup | −595 ps | F1 `tns_cost` 6.67 (different units; not finish TNS) | **ORFS** (signoff metric). |
| Stdcell area | Place 684 µm² (604 inst, WNS **+12 ps**). Finish **940 µm²** (680 inst). | Arch mapped **407.5** (`sub_twos_complement`). Flatten 409.1. GPL liberty_default **450** (248 cells). | Arch DSE is a real axis but **not** finish. Place ORFS already closed; finish pays +256 µm² CTS/repair. |
| Timing-repair buf | **132** (130 µm²) + 7 clk buf | F5-CTS: 6 clk buf, **0** repair | ORFS buys slack. DSE F5 does not have that budget. |
| Total power | 3.93 mW (leak 25.6 µW) | Mapped flatten 1.26 mW (leak ~8.6 µW at GRT) | Different netlists. Do not declare a power win. |
| Core util | 54.9% (die 1970, core 1712) | GPL at util 35 (floorplan contract) | Different recipes. |
| HPWL | Historical ingest 2810 µm (not remeasured) | DSE GPL **1071 µm** on liberty_default | Same order only if GPL is rerun on same netlist. Today different netlists. |
| Dynamic IR, **same finish extract** (`n_r=5816`) | OpenROAD PSM **6.667 mV**. DSE DirectLU **6.075 mV**. | Decap 200 fF **4.156 mV** (same graph). | **DSE PDN**: −1.92 mV vs DirectLU, without restamping gold. |
| Dynamic IR, **other** mesh | — | Catalog strap 1.705 mV; leftover 3.942 mV | Real PDN search, **not** comparable to finish. |
| Coverage | 1 recipe | 140 candidates (F0–F5), Pareto per level, HV campaign 257.09→257.79 | **DSE** as search engine. |

Place DP ORFS was **already meeting** (+12 ps). Finish is −37 ps: CTS + route
worsen, 132 buffers do not recover all. Green `make finish` ≠ timing
closed at 2.17 GHz (finish fmax ≈ 2.01 GHz).

## Real DSE strengths

1. **Layered search, not a flat vector.** ABC ≠ util ≠ density ≠ PDN.
   EHVI acquires; does not replace the front. Fingerprint skips duplicates.
2. **PDN ORFS does not do like DSE.** Same finish extract: DirectLU 6.075 →
   decap 4.156 mV. Then leftover/region/strap as *other* graphs, labeled
   “not gold”. Attribution: hotspot combo on `dpath` → cone ABC, no longer
   ABC on chip.
3. **Multi-fidelity.** F1/F3/GPL/F5-lite without launching `make finish` every
   shot. Campaign: stop on HV (`hv_eps`), do not burn wall.
4. **E-graph architecture.** 407.512 vs flatten 409.108 µm² (small delta on
   GCD, axis exists). Equiv PASS.
5. **ABC beyond ORFS recipe.** `abc_speed` −114 ps @ 619 µm² vs flatten
   −522 ps @ 409 µm². `boils_balance` (`dpath` cone) `wns_cost` **0.2088** @
   553 µm² — ORFS does not explore that script on the cone.
6. **Operational honesty.** Gold 45.298 unrestamped. F5 ≠ finish. AES Krylov on
   ~73k-R refused. Missing ≠ 0.

## Where the standard flow stays ahead

- Signoff timing and a complete ODB (CTS + repair + fill + route).
- Repeatable industrial recipe: one `make finish`.
- GCD is small (~250–680 cells). AES F4 dynamic on 73k-R is still GAP
  (DirectLU refuse, AMG timeout).
- HV campaign on GCD moved little (+0.70). Default ceilings are a tour,
  not a tapeout budget.
- DSE **is not** a better Yosys and **does not** replace `repair_timing`.

## What it would take to “beat finish” on WNS

Take a DSE winner (arch + ABC + optional PDN) and pay an ORFS-like budget
of timing repair / full CTS. Today that is **out of contract** for F5-lite.
Without that step, comparing −641 ps with −37 ps is a category error.

## Numbers still not to use in a slide

- IR 1.705 mV as “better than finish 6.075”
- Mapped 407 vs finish 940 as “half area”
- Ingest `wns_cost` −0.0435 (gold snapshot) as DSE WNS
- Mapped vs finish leakage without same netlist
