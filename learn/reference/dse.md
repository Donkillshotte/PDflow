# Physics-aware DSE

This document is the **lab** (e-graph, F4, refine). Product wins live in
[`win_rule.py`](../dse/win_rule.py). Index:
[`docs/README.md`](../../docs/README.md) · lab: [`docs/lab.md`](../../docs/lab.md).

This is not a blind synth→P&R loop. The controller searches **one level at a time**, keeps
experiment memory, and uses Dynamic IR as an **F4 oracle**, not as a scalar
penalty.

```text
RTL
 → e-graph datapath (IR cone, e.g. dpath)
 → F1 Yosys+ABC (BOiLS alphabet, GP+SSK, append DRiLLS) + equiv
 → F1 synthesis: ORFS `abc_speed.script` (ABC_AREA=0, `-D 460`) — not `-fast`, not `abc_ops`
   chip = flatten-first (teacher area 409.108 µm²)
   dpath cone = ABC only on datapath modules; leftover = known modules − paid cone
   ctrl cone = ABC on FSM+RegRst (first class, not leftover from dpath); `mapped_hier.v`
   write_verilog -noattr -noexpr  (liberty cells, not assign soup)
 → F2-fast netgraph (anchored centroid + HPWL + RUDY)
 → F2 OpenROAD GPL -skip_io (one shot at budget, not finish)
 → F3 OpenSTA on the *candidate* (ideal; hierarchical paths `dpath/sub/…` on the cone), **interleaved** after every F1
 → F2 routing: place_pins + GPL + global_route + `write_sdf` (not SPEF)
 → F3 OpenSTA + SDF GRT (same GRT `mapped.v` — not OpenRCX)
 → F5-lite: `detailed_route` (2 iter, no CTS) + OpenRCX + OpenSTA `read_spef` (ideal clock)
 → F3 OpenSTA + SPEF OpenRCX (same SPEF as F5-lite, without a second DRT)
 → F5-CTS: `clock_tree_synthesis` + DRT + OpenRCX + OpenSTA `set_propagated_clock` on post-CTS netlist (paid shot, does not replace F5-lite, not `make finish`)
 → F5-local: OpenRCX SPEF on cell/net netlist — residual F3→F5, not the F1 SPEF, not `make finish`
 → active learning: residual F3→F5-lite orders host cell vs net; residual F3→F5-local + uncertainty picks next level (another SPEF, or cell/net on the SPEF path) — not a mixed vector
 → F2 physical catalog: one AutoDMP point (util/density) measured with GPL, not just RUDY proxy
 → F2 region: `create_blockage -max_density` on the IR bin (rXY / hotspot dbu) + GPL
 → F4 extract region: `write_pg_spice` under the same cap — new mesh, not gold
 → F2 ingest place / GRT of the current layout
 → F3 ingest STA signoff
 → F4 extract candidate (`write_pg_spice` after place_pins+GPL+DP+pdngen) + `report_arrival`
 → F3 `report_arrival` on the attributed host (t50 for I(t), not STA of the synth extract)
 → F4 host extract (`write_pg_spice` on attributed netlist — own mesh, not synth)
 → F4 host extract-region (density cap on the host IR bin, e.g. r02 — not r31 gold on synth)
 → F4 host-IR-steer: winning family on host-region mesh, then pkg L on the free host (not candidate IR-steer)
 → F4 I-scale-win: I(t)×P on the winning host PDN extract (after host-IR-steer, not the first I-scale)
 → F3 IR-cell: I-scale-win hotspot → geometric ODB join → module drive-up (ctrl, not dpath STA path)
 → F4 I-scale-champ: I(t)×P on the `winning_ir_pdn` extract (IR-cell-region-PDN, not host-win; STA of the extract, not host arrivals)
 → F3 IR-cell-champ: I-scale-champ hotspot → ODB join on the sample extract → drive-up (dpath, not the first ctrl set)
 → F4 extract IR-cell-champ (`write_pg_spice` on dpath-sized netlist — residual vs extract IR-cell, not host)
 → F4 IR-cell-champ-PDN: winning family on the dpath-sized mesh (not host-IR-steer)
 → F4 AMG-champ / RAS-champ / Krylov-champ: residual solver on the `winning_ir_pdn` extract (same DirectLU knobs, not candidate AMG, not gold)
 → F4 static-IR-steer: `winning_static_pdn` (separate 1× ranking) pays `pkg_r` — decap/pkg L do not move DC, not Dynamic IR-steer, not gold
 → F4 static-mesh: residual null `pkg_r` (ideal bump V) pays denser bumps on the same ODB — not a new GPL, not gold
 → F4 restamp DirectLU / SA-AMG / RAS / Krylov-MOR (PDN knobs / attributed host I(t)×power / **static IR**) on the named extract
 → F4 ingest gold (45.298 mV unrestamped)
 → hotspot attribute → region → cells/nets → RTL module (dpath/ctrl)
 → F3 cell-local: drive-up on the cells of the worst path (module scope, not ABC)
 → F3 net-local: `BUF_X2` on the hops of the worst path (same module)
 → F3 port-net: `BUF_X2` on port net to parent (ctrl↔dpath hop; not mixed with intra-module hops)
 → F0 surrogate (SSK-GP, residual F1→F2, GNN HPWL; F1→F4 only if coupled)
 → Pareto at each level
 → next candidate / extract
```

## Levels (not a single vector)

| Level | What is searched | Status |
|---|---|---|
| **architecture** | equivalent e-graph extracts on the `dpath` cone (ROVER/ASPEN-shaped) | READY F1 + equiv |
| **logic** | ABC sequences `{rewrite, refactor, resub, balance, …}` (BOiLS STD) | READY F1 · GP+**EHVI(area,WNS)** / EI · insert |
| **synthesis** | `ABC_AREA` ORFS (`abc_speed.script` + `-D 460`) | F0 catalog + **F1 measured** (not mixed with ABC ops) |
| **cell** | drive-up of instances on the worst STA path | READY F3 — module scope, not `abc_ops` |
| **net** | `BUF` on the attributed hops of the worst path | READY F3 — module scope **and** port scope (parent) on ctrl↔dpath crossings; not a cell drive-up |
| **physical** | util, density, **IR region**, candidate netlist | F0 proxy + F2-fast + **GPL** + catalog + **density cap on IR bin** + ingest — does not launch finish |
| **routing** | GRT after place_pins + F5-lite DRT/OpenRCX + F5-CTS | READY F2 GRT + F5-lite SPEF (ideal clock) + F5-CTS SPEF (propagated clock) — not `make finish` |
| **pdn** | `c_decap`, pkg L, **pkg_r (static IR)**, **bump pitch (on-die static)**, I(t)×power, candidate/host mesh, MF solver | ingest gold + extract candidate + **host extract** + **host extract-region** + DirectLU/AMG/RAS/Krylov + **AMG/RAS/Krylov on winning_ir_pdn** + **pkg_r on winning_static_pdn** + **bump restamp on the same ODB** (not gold) |

Concatenating `rewrite` and `coreUtilization` in a single box is **forbidden** (`knobs_fp` includes the level).

## Fidelity

| F | Role | Status |
|---|---|---|
| F0 | SSK-GP area ± std; congestion RUDY-class; skip F1 if optimistic is already worse | READY — **not** IR |
| F1 | Yosys synth + ABC (script *file*) + `equiv_*` + `write_verilog -noexpr` | READY · chip flatten-first **or** cone-local ABC **or** ORFS `abc_speed` (synthesis) |
| F2 | place / GRT / finish ORFS **ingest** · F2-fast netgraph · GPL `-skip_io` · GRT+SDF | READY (GPL/GRT budgeted) |
| F3 | ideal OpenSTA (hier on the cone) + OpenSTA+SDF GRT + OpenSTA+SPEF OpenRCX + ingest | READY — F5-lite SPEF is ideal clock; F5-CTS uses `set_propagated_clock` |
| F4 | Dynamic IR/EM (libdpn A/B/C/D) + static IR on the same extract | ingest gold + **extract candidate** + arrivals + **host extract** + **host extract-region** + restamp DirectLU/AMG/RAS/Krylov — **does not** replace the 45.298 gold |
| F5 | DRT + OpenRCX SPEF + OpenSTA `read_spef` | READY F5-lite (ideal clock) **and** F5-CTS (propagated clock) **and** F5-local on cell/net netlist — the controller **does not** launch `make finish` |

F2-fast HPWL is in **grid units**; GPL HPWL is in **µm**. They do not share the same Pareto axis.
F2-fast congestion is `rudy_excess/(1+rudy_excess)` ∈ [0,1) — it is not GRT overflow.

## E-graph / extract

On the GCD datapath we saturate equalities:

- `a-b` ≡ `a+(~b+1)`
- `(x==0)` ≡ `~(|x)`
- unsigned `a<b` ≡ borrow of `{0,a}-{0,b}`

The greedy extract (structural cost) prefers the native operator; forced
extracts are measured at F1 and immediately at F3 (EDA feedback, ASPEN idea). Softmax on −cost/T is
inspired by SmoothE, without a GPU loop. If the IR hotspot is on `dpath`, only
**that cone** is rewritten — no chip restart. A worse extract on WNS
(e.g. `lt_borrow` at −0.59 ns vs baseline −0.52) is **deprioritized**, not
repeated as if area were the only axis.

After the teacher chip (`liberty_default` flatten-first, 409.108 µm²), BOiLS
proposals with IR focus `dpath` receive `scope=logic_cone` + `cone=dpath` +
`cone_module` (`knobs_fp` distinguishes them from flatten-first). ABC runs on
datapath modules (`GcdUnitDpathRTL`, `sub`, `a_reg`/`b_reg`, …); leftover = inverse
of the paid cone. If STA lists `ctrl/` hops, one **logic_ctrl** shot maps
`GcdUnitCtrlRTL`+`RegRst` (is not leftover from dpath and does not restart from chip).
STA on `mapped_hier.v` sees `dpath/b_reg/…` and `ctrl/_07_` without inherit.
The flattened netlist goes to P&R/GRT/F4.

## Attributes (chip → block → region → cone → cell → net)

The GCD OpenSTA path (`dpath.a_reg…`) and the ITerm hotspot (`x_dbu`, `y_dbu`)
become `scope=logic_cone`, `modules=[dpath]`, `region=r31`. We record
`transform + context → ΔQoR`, not just `design → QoR`.

## Optimizers (one per problem)

The **planner** reads `combo_frac`, the module, the region, and F3 WNS: IR combo on
`dpath` names the extracts (`lt_borrow` → `sub` → `eqz`) and does not restart from chip.
After every F1 STA it recalculates the order: extracts measured worse on slack
go to the bottom. High GRT congestion or region focus shifts budget to the
physical level. ABC knobs and `coreUtilization` remain distinct fingerprints.

- **BOiLS** — SSK kernel + GP + **EHVI(area, WNS)**; EHVI(area, IR) is secondary when ≥2 F4 extracts — never a single box with util/pkg L
- **DRiLLS** — UCB on the next ABC op given (last op, IR focus); reward area+WNS
- **e-graph** — saturation + extract, not random RTL
- **GNN** — 2 layer mean-aggregate + ridge on F2-fast HPWL; high uncertainty if n&lt;4
- **AutoDMP-shaped** — util/density catalog: F0 is only a prior; **one point is GPL**
- **OpenROAD GPL** — `-skip_io` shot on the F1 winner + catalog shot (not F5)
- **LLM** — optional proposer (`DSE_LLM_URL`); symbolic fallback; **not** the optimizer

## Swappable layers

`learn/dse/layers.py` registers extraction / power / activity / current / DSE /
surrogate / solver / physical_fast / physical_gpl / routing / timing.
Extraction is `write_pg_spice` on the legalized candidate **or** ingest of finish.
Activity is OpenSTA `report_arrival` on the candidate (t50), not an invented RTL→ITerm map.
Solver is `make_solver(direct|amg|bicg|ras)` — AMG is residual MF, not the gold.
The GCD gold 45.298 mV is not restamped. EM J is `em_thermal_snapshot` on V_worst.

## Commands

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_dse.sh
# DSE_F1_MAX=6 DSE_BUDGET_S=90 DSE_FRESH=1
python3 learn/scripts/test_dse.py
```

Report: `learn/sim/reports/dse_flowlab.json` · memory: `learn/sim/dse/memory_flowlab.jsonl`.

Studio: action `dse` · `/strumenti?tab=run&action=dse` · panel on `/pkg` and FlowLab signoff.

References (not forks): BOiLS DATE’22 / HEBO ActionSimple, DRiLLS, AutoDMP ISPD’23,
ROVER/ASPEN/SmoothE as form (ROVER/ASPEN are not OSS), MAVIREC, EMSim split A/B,
Raptor/MATEX/ESPSim in existing PI solver.
