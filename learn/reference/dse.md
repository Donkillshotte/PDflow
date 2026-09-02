# DSE fisico-aware

This documento is il **lab** (e-graph, F4, refine). Wins of
prodotto stanno in [`win_rule.py`](../dse/win_rule.py). Indice:
[`docs/README.md`](../../docs/README.md) · lab: [`docs/lab.md`](../../docs/lab.md).

This is not un loop cieco synth→P&R. Il controller search for **one level at a time**, keeps
an experiment memory e use Dynamic IR come **oracle F4**, not as a penalty
scalare.

```text
RTL
 → e-graph datapath (cono IR, es. dpath)
 → F1 Yosys+ABC (alfabeto BOiLS, GP+SSK, append DRiLLS) + equiv
 → F1 synthesis: ORFS `abc_speed.script` (ABC_AREA=0, `-D 460`) — non `-fast`, non `abc_ops`
   chip = flatten-first (teacher area 409.108 µm²)
   cono dpath = ABC solo sui modules del datapath; leftover = modules noti − cono pagato
   ctrl cone = ABC su FSM+RegRst (first class, non leftover from dpath); `mapped_hier.v`
   write_verilog -noattr -noexpr  (liberty cells, not assign soup)
 → F2-fast netgraph (baricentro ancorato + HPWL + RUDY)
 → F2 OpenROAD GPL -skip_io (one shot at budget, not finish)
 → F3 OpenSTA sul *candidate* (ideale; hierarchical paths `dpath/sub/…` on the cone), **interleaved** after every F1
 → F2 routing: place_pins + GPL + global_route + `write_sdf` (not SPEF)
 → F3 OpenSTA + SDF GRT (same GRT `mapped.v` — not OpenRCX)
 → F5-lite: `detailed_route` (2 iter, no CTS) + OpenRCX + OpenSTA `read_spef` (ideal clock)
 → F3 OpenSTA + SPEF OpenRCX (stesso SPEF F5-lite, senza un secondo DRT)
 → F5-CTS: `clock_tree_synthesis` + DRT + OpenRCX + OpenSTA `set_propagated_clock` on post-CTS netlist (paid shot, does not replace F5-lite, non `make finish`)
 → F5-local: OpenRCX SPEF on cell/net netlist — residual F3→F5, non il SPEF F1, non `make finish`
 → active learning: residual F3→F5-lite orders host cell vs net; residual F3→F5-local + uncertainty picks next level (another SPEF, o cell/net sul path SPEF) — not a mixed vector
 → F2 catalogo fisico: un punto AutoDMP (util/density) misurato con GPL, not just RUDY proxy
 → F2 regione: `create_blockage -max_density` sul bin IR (rXY / hotspot dbu) + GPL
 → F4 extract regione: `write_pg_spice` sotto the same cap — new mesh, not gold
 → F2 ingest place / GRT del layout corrente
 → F3 ingest STA signoff
 → F4 extract candidate (`write_pg_spice` after place_pins+GPL+DP+pdngen) + `report_arrival`
 → F3 `report_arrival` sull’host attribuito (t50 for I(t), non STA dell’extract synth)
 → F4 host extract (`write_pg_spice` on attributed netlist — own mesh, not synth)
 → F4 host extract-regione (density cap on IR bin dell’host, es. r02 — not r31 gold on synth)
 → F4 host-IR-steer: famiglia winning sul mesh host-regione, poi pkg L sull’host libero (not candidate IR-steer)
 → F4 I-scale-win: I(t)×P sull’extract PDN host winning (after host-IR-steer, not the first I-scale)
 → F3 IR-cell: I-scale-win hotspot → geometric ODB join → module drive-up (ctrl, not dpath STA path)
 → F4 I-scale-champ: I(t)×P sull’extract `winning_ir_pdn` (IR-cell-region-PDN, not host-win; STA dell’extract, not host arrivals)
 → F3 IR-cell-champ: hotspot I-scale-champ → join ODB sull’extract campione → drive-up (dpath, not the first ctrl set)
 → F4 extract IR-cell-champ (`write_pg_spice` on dpath-sized netlist — residual vs extract IR-cell, not host)
 → F4 IR-cell-champ-PDN: famiglia winning sul mesh dpath-sized (not host-IR-steer)
 → F4 AMG-champ / RAS-champ / Krylov-champ: residual solver sullo extract `winning_ir_pdn` (same DirectLU knobs, not candidate AMG, not gold)
 → F4 static-IR-steer: `winning_static_pdn` (separate 1× ranking) pays `pkg_r` — decap/pkg L do not move DC, not Dynamic IR-steer, not gold
 → F4 static-mesh: residual pkg_r nullo (ideal bump V) paga denser bumps on the same ODB — not a new GPL, not gold
 → F4 restamp DirectLU / SA-AMG / RAS / Krylov-MOR (knobs PDN / I(t)×power dell’host attribuito / **static IR**) sullo extract nominato
 → F4 ingest gold (45.298 mV unrestampato)
 → attributo hotspot → regione → celle/net → modulo RTL (dpath/ctrl)
 → F3 cell-local: drive-up on the cells del worst path (module scope, not ABC)
 → F3 net-local: `BUF_X2` sugli hop del worst path (stesso modulo)
 → F3 port-net: `BUF_X2` on port net to parent (hop ctrl↔dpath; not mixed with intra-module hops)
 → surrogato F0 (SSK-GP, residual F1→F2, GNN HPWL; F1→F4 solo se accoppiato)
 → Pareto per level
 → prossimo candidate / extract
```

## Levels (not a single vector)

| Livello | Cosa si search for | Status |
|---|---|---|
| **architecture** | extract e-graph equivalenti on the cone `dpath` (ROVER/ASPEN-shaped) | READY F1 + equiv |
| **logic** | sequenze ABC `{rewrite, refactor, resub, balance, …}` (BOiLS STD) | READY F1 · GP+**EHVI(area,WNS)** / EI · insert |
| **synthesis** | `ABC_AREA` ORFS (`abc_speed.script` + `-D 460`) | F0 catalogo + **F1 measured** (not mixed with ABC ops) |
| **cell** | drive-up delle istanze sul worst path STA | READY F3 — module scope, non `abc_ops` |
| **net** | `BUF` sugli hop attribuiti del worst path | READY F3 — module scope **e** port scope (parent) sui ctrl↔dpath crossing; not a cell drive-up |
| **physical** | util, density, **IR region**, netlist del candidate | F0 proxy + F2-fast + **GPL** + catalogo + **density cap on IR bin** + ingest — does not launch finish |
| **routing** | GRT after place_pins + F5-lite DRT/OpenRCX + F5-CTS | READY F2 GRT + F5-lite SPEF (ideal clock) + F5-CTS SPEF (propagated clock) — non `make finish` |
| **pdn** | `c_decap`, pkg L, **pkg_r (static IR)**, **bump pitch (on-die static)**, I(t)×power, mesh candidate/host, solver MF | ingest gold + extract candidate + **host extract** + **host extract-regione** + DirectLU/AMG/RAS/Krylov + **AMG/RAS/Krylov su winning_ir_pdn** + **pkg_r on winning_static_pdn** + **bump restamp on the same ODB** (not gold) |

Concatenating `rewrite` e `coreUtilization` in un unico box is **forbidsto** (`knobs_fp` includes the level).

## Fidelity

| F | Role | Status |
|---|---|---|
| F0 | SSK-GP area ± std; congestion RUDY-class; skip F1 if optimistic is already worse | READY — **not** IR |
| F1 | Yosys synth + ABC (script *file*) + `equiv_*` + `write_verilog -noexpr` | READY · chip flatten-first **o** cone-local ABC **o** ORFS `abc_speed` (synthesis) |
| F2 | place / GRT / finish ORFS **ingest** · F2-fast netgraph · GPL `-skip_io` · GRT+SDF | READY (GPL/GRT budgetati) |
| F3 | OpenSTA ideale (hier on the cone) + OpenSTA+SDF GRT + OpenSTA+SPEF OpenRCX + ingest | READY — SPEF F5-lite is ideal clock; F5-CTS use `set_propagated_clock` |
| F4 | Dynamic IR/EM (libdpn A/B/C/D) + static IR on the same extract | ingest gold + **extract candidate** + arrivals + **host extract** + **host extract-regione** + restamp DirectLU/AMG/RAS/Krylov — **non** sostituisce il gold 45.298 |
| F5 | DRT + OpenRCX SPEF + OpenSTA `read_spef` | READY F5-lite (ideal clock) **e** F5-CTS (propagated clock) **e** F5-local on cell/net netlist — il controller **non** lancia `make finish` |

F2-fast HPWL is in **grid units**; GPL HPWL is in **µm**. Non stanno on the same asse Pareto.
La congestion F2-fast is `rudy_excess/(1+rudy_excess)` ∈ [0,1) — is not l’overflow GRT.

## E-graph / extract

Sul datapath GCD saturiamo uguaglianze:

- `a-b` ≡ `a+(~b+1)`
- `(x==0)` ≡ `~(|x)`
- unsigned `a<b` ≡ borrow di `{0,a}-{0,b}`

L’extract greedy (costo structurele) preferisce l’operatore nativo; gli extract
forced are measured at F1 and immediately at F3 (EDA feedback, ASPEN idea). Softmax on −cost/T is
ispirato a SmoothE, senza loop GPU. Se l’hotspot IR is su `dpath`, si riscrive
**solo quel cono** — niente restart del chip. Un extract peggiore sul WNS
(es. `lt_borrow` a −0.59 ns vs baseline −0.52) viene **deprioritized**, non
ripetuto come se l’area fosse l’unico asse.

After il teacher chip (`liberty_default` flatten-first, 409.108 µm²) i proposal
BOiLS con focus IR `dpath` ricevono `scope=logic_cone` + `cone=dpath` +
`cone_module` (`knobs_fp` li distingue dal flatten-first). ABC gira sui modules
del datapath (`GcdUnitDpathRTL`, `sub`, `a_reg`/`b_reg`, …); leftover = inverse
of the paid cone. Se STA elenca hop `ctrl/`, one **logic_ctrl** shot maps
`GcdUnitCtrlRTL`+`RegRst` (is not leftover from dpath e does not restart from chip).
Lo STA sul `mapped_hier.v` vede `dpath/b_reg/…` e `ctrl/_07_` senza inherit.
Il netlist flattenato va a P&R/GRT/F4.

## Attributi (chip → block → region → cone → cell → net)

Il path OpenSTA del GCD (`dpath.a_reg…`) e l’hotspot ITerm (`x_dbu`, `y_dbu`)
diventano `scope=logic_cone`, `modules=[dpath]`, `region=r31`. Si registra
`transform + context → ΔQoR`, non solo `design → QoR`.

## Ottimizzatori (uno per problema)

Il **planner** legge `combo_frac`, il modulo, la regione e il WNS F3: IR combo su
`dpath` nomina gli extract (`lt_borrow` → `sub` → `eqz`) e does not restart from chip.
After every F1 STA ricalcola l’ordine: extract misurati peggiori sul slack
vanno in fondo. Congestione GRT alta o focus di regione sposta il budget sul
livello physical. I knobs ABC e `coreUtilization` restano fingerprint distinti.

- **BOiLS** — kernel SSK + GP + **EHVI(area, WNS)**; EHVI(area, IR) is secondario quando ≥2 extract F4 — never un box unico con util/pkg L
- **DRiLLS** — UCB sul prossimo op ABC dato (ultimo op, focus IR); reward area+WNS
- **e-graph** — saturation + extract, non RTL casuale
- **GNN** — 2 layer mean-aggregate + ridge su HPWL F2-fast; incertezza alta se n&lt;4
- **AutoDMP-shaped** — util/density catalog: F0 is only a prior; **one point is GPL**
- **OpenROAD GPL** — colpo `-skip_io` sul vincitore F1 + colpo catalogo (non F5)
- **LLM** — optional proposer (`DSE_LLM_URL`); fallback simbolico; **non** is l’the optimizer

## Layer sostituibili

`learn/dse/layers.py` registra extraction / power / activity / current / DSE /
surrogate / solver / physical_fast / physical_gpl / routing / timing.
Extraction is `write_pg_spice` sul candidate legalizzato **or** ingest del finish.
Activity is OpenSTA `report_arrival` sul candidate (t50), non una mappa RTL→ITerm inventata.
Solver is `make_solver(direct|amg|bicg|ras)` — AMG is residual MF, non il gold.
Il gold GCD 45.298 mV non si ristampa. EM J is `em_thermal_snapshot` su V_worst.

## Comandi

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_dse.sh
# DSE_F1_MAX=6 DSE_BUDGET_S=90 DSE_FRESH=1
python3 learn/scripts/test_dse.py
```

Report: `learn/sim/reports/dse_flowlab.json` · memoria: `learn/sim/dse/memory_flowlab.jsonl`.

Studio: azione `dse` · `/strumenti?tab=run&action=dse` · pannello su `/pkg` e FlowLab signoff.

Riferimenti (non fork): BOiLS DATE’22 / HEBO ActionSimple, DRiLLS, AutoDMP ISPD’23,
ROVER/ASPEN/SmoothE come forma (ROVER/ASPEN non are OSS), MAVIREC, EMSim split A/B,
Raptor/MATEX/ESPSim in existing PI solver.
