# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-09-01T11:30Z — Confronto ORFS finish vs DSE (GCD)

Onesto, non marketing. Fonte finish: `6_report.json` + `3_5_place_dp.json`.
Fonte DSE: `memory_flowlab.jsonl` 140/137 ok (campagna live, prima solo in
WT). Write-up: `learn/sim/reports/flow_vs_dse_gcd.md`.

ORFS vince il chip: WNS **−37 ps**, 132 repair buf, stdcell finish 940 µm².
Place era già meeting (**+12 ps**, 684 µm²) — finish peggiora col CTS.
DSE non chiude: F5-lite **−641 ps** (no repair), ideal ABC **−114 ps**.
Mapped 407.5 ≠ finish 940 (categorie diverse).

DSE vince la ricerca: 140 candidati vs 1 ricetta; ABC cono `boils_balance`
wns_cost **0.2088**; PDN **stesso** extract finish (`n_r=5816`) DirectLU
**6.075 → decap 4.156 mV**. Non usare catalog 1.705 né leftover 3.942 vs
finish. Gold 45.298 unrestamp. AES sha intatto. Nessun Krylov AES.

## 2026-09-01T10:50Z — Campagna live GCD (resume JSONL)

`run_dse.py --campaign --wall-s 180`. Resume `memory_flowlab.jsonl` (no
`--fresh`, no AES). `start_inner=1` (tetti inner 0 già spesi).
`stop=hv_eps` dopo 2 inner (~151 s). HV 257.090 → 257.787 (ref congelato).
+27 candidati (26 ok): 5 F1 cone ABC, 1 GPL, 2 GRT, 2 F5-lite, 2 CTS,
2 cell size-up. Best logic `wns_cost` 0.2106 → **0.2088** (`boils_balance`
553.28 µm², prima senza STA). Size-up sull’arch winner: 425.6 µm² WNS
−0.405 ns. Corone invariate: area arch **407.512**, synth WNS **−0.114**,
DirectLU **6.075**, decap **4.156**. Gold **45.298** unrestamp; AES
`febe6804241c` sha `9e89f6e88b61` intatto. `prlimit --as=8GiB`. Fix
UnboundLocalError wrapper F4 in `run_controller` (prima chiamata live).

## 2026-09-01T08:20Z — Campagna DSE (HV gated, JSONL condiviso)

`dse.campaign.run_campaign` rilancia `run_controller` sulla stessa JSONL.
Stop: HV relativo < eps (front gated logic area vs `wns_cost`, ref congelato),
wall, zero nuovi `ok`, max_inner. Tetti lifetime: inner 0 = default di oggi
(GPL/F5/CTS/cell/net = 1, F3=8, F2-fast=4). Inner successivi `v+i`.
`f1_max = 6×(inner+1)`. Skip parent già coperti; `pred` solo tie-break.
CLI `--campaign` opt-in. `test_dse_campaign.py` fake runner (no OpenROAD/AES/F4).
`test_dse` ALL PASSED **1120** `ok` (~291 s): 1086 + 34 campagna. DirectLU
6.075 + `sta_t50`; gold 45.298 unrestamp; AES `febe6804241c` sha `9e89f6e88b61`
static 6.954 intatto. Gate AES Krylov resta REFUSED. Nessun DesignState.

## 2026-09-01T07:45Z — PD QoR axes (leakage, TNS, HPWL, stdcell)

`QoR` first-class: `leakage_w`, `tns_cost`, `hpwl_um`; observation
`internal_power_w` / `switching_power_w` / `wirelength_um` / `core_util`.
`area_um2` documented as mapped stdcell instance area. OpenSTA
`report_power` Total row split (internal/switching/leakage/total).
TIMING_POWER gated includes TNS+leakage. `test_dse` ALL PASSED **1086**
`ok` (~294 s). Live GCD F3: WNS −0.522 ns TNS −16.719 ns P 1.26 mW leak
8.56 µW. DirectLU 6.075 + `sta_t50`; gold 45.298 unrestamp; AES
`febe6804241c` sha `9e89f6e88b61` static 6.954 intatto. Studio
`DsePanel` columns: stdcell, cells, TNS, leak, P tot, HPWL µm.

## 2026-08-31T22:25Z — E2E no-skip (extract + gold + F5 GCD)

I skip della run 994 non erano OpenROAD assente: `extract_available`
True, ma i fixture gitignore `4628a15dbc9a.v` / `ab9f115d5a67.v` e
`dynamic_ir_flowlab.json` mancavano. Piantati da F1 liberty-default
(409.108 µm², 248 celle) + sentinel gold **45.298** (non restamp 6.075).
`check_live_f4` 49 `ok`: DirectLU 6.075 + `sta_t50`; extract `n_r=1939`
droop 18.760; region r32; gold unrestampato. GPL/GRT/F5-lite/F5-CTS GCD
ok. Soglia CTS vs lite: ΔWNS ≠ 0 (su GCD 3–7 ps). `test_dse` ALL PASSED
**1069** `ok` (~289 s). AES `febe6804241c` sha `9e89f6e88b61…` intatto.
Mai Krylov AES. Un job, `prlimit --as=8GiB`.

## 2026-08-31T21:36Z — PLAN Fase 2 D.2–D.5 + cleanup

`test_dse` runner: metrics → memory → planner → steer → live F4 (ultimo).
D.2 `test_dse_memory.py` · D.3 `test_dse_planner.py` · D.4 `test_dse_steer.py`
(558 `ok` smoke) · D.5 `test_dse_live_f4.py`. Stesso entrypoint.
`test_dse.py` ALL PASSED (~262 s); **994** `ok`; DirectLU 6.075 + `sta_t50`;
AMG/RAS 6.075; Krylov 6.092. Gold file assente su disco (check unrestamp
skipped); `GOLD_MV` 45.298 non ristampato. AES `febe6804241c` n_r=73139
static 6.954 intatto (sha `9e89f6e88b61…`). Suite veloce verde.
`controller.py` 3115 → 3062: drop import unused post C4–C7; 66 `should_pay_*`
restano in `acquire.py`. `PLAN.md` Diagnosi aggiornata (buchi 1–5 chiusi).
Nessun `DesignState`.

## 2026-08-31T20:50Z — PLAN Fase 2 D.1 + chiusura

`test_dse_metrics.py` (dominates / gated / HV / EHVI, 15 `ok`).
`test_dse.py` resta l’entrypoint. Stesso conteggio 994 `ok`.
`test_dse.py` ALL PASSED (~261 s); DirectLU 6.075 + `sta_t50`. Gold unrestamped.
AES `febe6804241c` n_r=73139 static 6.954 intatto. `controller.py` 3115:
ingest/F1 teacher → slice → C1–C6 → `run_next_refine` → C7 → report.
Nessun `DesignState`. Fase 2 chiusa.

## 2026-08-31T20:44Z — PLAN Fase 2 C7: champ solvers + static/EM

`STAGES_IR_SOLVERS` after `run_next_refine`. AMG/RAS/Krylov-champ + static
IR/mesh/straps + EM. `admit_paid_f4` wrappers on ctx. `controller.py`
3551 → 3115. `test_dse.py` ALL PASSED (~259 s); DirectLU 6.075 + `sta_t50`.
Gold unrestamped. F1 teacher and refine while stay inlined.

## 2026-08-31T20:38Z — PLAN Fase 2 C6: winning_ir_region_cell depth 0

Size / extract / PDN family Stage. `run_next_refine` stays immediately after.
`controller.py` 3712 → 3551. `test_dse.py` ALL PASSED (~259 s);
DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:32Z — PLAN Fase 2 C5: inspect loops

`run_inspect_loop` + leftover-cone-region / winning_ir_region (cap 4).
Denied acquire `"no leftover-cone-region extract or |Δ| PDN"` pinned.
`controller.py` 3941 → 3712. `test_dse.py` ALL PASSED (~258 s);
DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:26Z — PLAN Fase 2 C4: winning_ir + champ family

`STAGES_IR_CHAMP`: winning_ir_pdn → iscale_champ → ir_cell_champ/cone.
Faithful extract (`ir_champ.py`). `controller.py` 4399 → 3941.
`test_dse.py` ALL PASSED (~261 s); DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:18Z — PLAN Fase 2 C3: IR-cell family

`STAGES_IR_CELL`: size → extract → PDN → region → region PDN. Hosts stay
attribution. `controller.py` 4633 → 4399. `test_dse.py` ALL PASSED (~258 s);
DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:20Z — PLAN Fase 2 C2: IR steer slice

ir_steer / host_ir_steer / f4_scale_win → `STAGES_IR_STEER`. While-loop
acquire strings identical. `controller.py` 4789 → 4633. `test_dse.py` ALL
PASSED (~259 s); DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:10Z — PLAN Fase 2 C1: STAGES_STEER_GAP

residual_steer / F5_PORT / port_steer / physical_catalog / f2_region moved
to `STAGES_STEER_GAP`. Order unchanged. `controller.py` 4920 → 4789.
`test_dse.py` ALL PASSED (~265 s); DirectLU 6.075 + `sta_t50`. Gold unrestamped.

## 2026-08-31T20:00Z — PLAN Fase 2 passo A: scenario guida I(t)

`i_t_inputs` + worker: `source` decide STA/VCD/SAIF. Triangle → `--no-sta`,
nessuno STA leftover. `sta_t50` REAL → `--sta` only. Worker non importa `dse`
(SciPy 1.x). GCD live DirectLU **6.075** + `sta_t50`. Gold unrestamped.
Nessun AES Krylov.

| Item | Result |
|---|---|
| triangle argv | `--no-sta`, no `--sta` |
| sta_t50 argv | `--sta` + scenario |
| ABSENT vcd | no `--vcd`, no leftover STA |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_dse.py` | ALL PASSED (~261 s); 6.075 / sta_t50; AMG/RAS match; C 6.092 |

## 2026-08-31T19:30Z — PLAN Fase 2 scritto (non eseguito)

`PLAN.md` sostituito: Fase 1 (0–6) archiviata su `ca47126`. Fase 2 è il
piano eseguibile per i buchi rimasti, misurati sul tree (controller 4920,
66 `should_pay_*`, `test_dse` 4925, scenario stamp-only, gated non-picker).

Ordine: A scenario→I(t) · E etichette 6.075 vs 45.298 · B `prefer_gated` +
Studio · C1–C7 strangler coda IR · D split test (dopo C). Fuori: DesignState,
AES full/CTS/Krylov, CCS, gold restamp, flatten F1 teacher, gated su F1→F2.

Nessun codice runtime toccato. Nessun `test_dse` in questo passo.

## 2026-08-31T17:56Z — PLAN passo 6: CurrentScenario

`learn/dse/current_scenario.py`: named I(t) source. Triangle remains default.
GCD finish infers `sta_t50` when STA arrivals exist (same 6.075 mV path).
Missing VCD/SAIF → `ABSENT`, never invented. `liberty_ccs` is GAP on
Nangate45 (NLDM). `build_worker_cmd` / worker take `--scenario` JSON;
`SolveResult.activity_via` points at it. No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| default | `ideal_triangle` / SYNTHETIC |
| GCD finish | `sta_t50` / REAL |
| missing waveform | ABSENT, no `--vcd`/`--saif` |
| CCS | GAP, no tables invented |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~265 s); DirectLU 6.075 with `sta_t50`; ≠ gold 45.298 |

## 2026-08-31T17:50Z — PLAN passo 5: Pareto gated by fidelity

`dominates_with_fidelity` / `pareto_front_gated`: a lower-fidelity timing/power
point cannot dominate a higher-fidelity point (they co-exist). Area stays
comparable. At equal axes F5 dominates F1. `pred` is tie-break only.
`pareto_front` unchanged for historical reports. Planner `next_candidate_ids`
feeds `plan["next"]` and controller `pareto_gated`. No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| F1 better WNS vs F5 | does not dominate; gated front keeps both |
| F5 at equal axes | dominates F1 |
| area F1 vs F5 | still comparable |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_designs/frame/dispatch` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~263 s); DirectLU 6.075 ≠ 45.298; gated F1/F5 co-exist |

## 2026-08-31T17:45Z — PLAN passo 3e: flatten controller stage slices

`run_controller` consecutive `run_stage` calls collapsed into
`STAGES_LOGIC_TRANSFORM` / `STAGES_PLACE_ROUTE` / `STAGES_F4_HEAD`.
F4 head is **not** nested under f2_region. GRT order is data in the
place-route tuple. residual_steer / port / f2_region / IR leftover stay
inlined. Domain `should_pay_*` remain (stages still call them); redundant
n_have/wall early-returns dropped on the 3a generic wrappers.
`controller.py` 4979 → 4903 (−76). No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| Slices | synth/cell/net/net_port; STA→GRT→SDF…→local; F4 extract…scale |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK including 3e slice order |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~263 s); DirectLU 6.075 ≠ 45.298 |

## 2026-08-31T18:55Z — PLAN passo 3d: F4 stages + needs_admit

Strangler: F4 extract / region extract / PDN catalog / AMG / RAS / Krylov / host arrivals / host extract / host region / I-scale moved to `stages.py`. `Stage.needs_admit=True` → `_pay_and_maybe_eval` calls `admit_paid_f4` before evaluate. Evaluate still uses controller wrappers (stamp SolveResult, no JSONL restamp of live memory). Champ/static/EM stay inlined (steer-special). `controller.py` 5432 → 4979 (−453). No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| `needs_admit` | F4 extract/PDN/solvers/host/scale |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK including 3d names |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~263 s); DirectLU 6.075 ≠ 45.298 |

## 2026-08-31T18:40Z — PLAN passo 3c: cell / net / synthesis / physical-catalog

Strangler: `synthesis`, `cell`, `net`, `net_port`, `physical_catalog` moved to `learn/dse/stages.py`. Order unchanged: synth/cell/net/net_port still run before F2; physical F0 propose + catalog GPL still after port_steer. Catalog keeps `require_plan=False`. `controller.py` 5661 → 5432 (−229). No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| Stages | `STAGE_SYNTHESIS`, `STAGE_CELL`, `STAGE_NET`, `STAGE_NET_PORT`, `STAGE_PHYSICAL_CATALOG` |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK including 3c names |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~263 s); DirectLU 6.075 ≠ 45.298 |

## 2026-08-31T18:20Z — PLAN passo 3b: routing / F5 stages

Strangler: GRT, F5-DRT, F3-SPEF, F5-CTS, F5-local, F5-port moved to `learn/dse/stages.py`. Order unchanged: STA → GRT → SDF → DRT → SPEF → CTS → LOCAL → residual_steer (inlined) → PORT. `why`/`step` strings unchanged including F5_LOCAL host_why kwargs. `controller.py` 5800 → 5661 (−139). No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| Stages | `STAGE_ROUTING`, `STAGE_F5_DRT`, `STAGE_F3_SPEF`, `STAGE_F5_CTS`, `STAGE_F5_LOCAL`, `STAGE_F5_PORT` |
| Order | GRT still between STA and SDF |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK including 3b names |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~266 s); DirectLU 6.075 ≠ 45.298 |

## 2026-08-31T18:00Z — PLAN passo 4: empirical p75 cost model

`learn/dse/costs.py`: `estimated_cost_s` is p75 of ok `cost_s` for that fidelity+design; < 3 samples → `COST_HINT`. Stages GPL/STA/SDF pass empirical `min_s` into `should_pay_*`. `_pay_and_maybe_eval` skips evaluate when wall+est exceeds `t_end` without changing acquire why. Controller F1/F3 interleave uses the estimate instead of static `COST_HINT`. Budget 45 s unchanged. No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| `p75([1,2,3,4])` | 3.25 (linear interp) |
| < 3 samples | `COST_HINT` fallback |
| `COST_HINT` | kept as declared fallback, not deleted |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~273 s); DirectLU 6.075 ≠ 45.298 |

## 2026-08-31T17:40Z — PLAN passo 3a: stages.py + f2_fast / f2_gpl / f3_sta / f3_sdf

Strangler: four simple stages moved to `learn/dse/stages.py`. GRT stays between STA and SDF (order unchanged). `why` strings unchanged. `controller.py` 5900 → 5801 lines (−99). No AES Krylov. Gold unrestamped.

| Item | Result |
|---|---|
| `should_pay_generic` | n_have / wall / parent; domain checks stay in acquire |
| Stages | `STAGE_F2_FAST`, `STAGE_F2_GPL`, `STAGE_F3_STA`, `STAGE_F3_SDF` |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK including generic why strings |
| `test_dse.py` | ALL PASSED (~260 s); DirectLU 6.075 ≠ 45.298 |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |

## 2026-08-31T17:20Z — PLAN passo 2: controller consumes admit_solve / SolveResult

Every paid F4 goes through `admit_paid_f4` (logs `step("admit", why=…)`) and `solve_f4` re-admits with mesh size. Champ solver residuals read `artifacts.solve.abs_err_vs_reference_mv` when present. `activity_status` is copied onto `attr`. No AES Krylov. 73k-R / 6.954 untouched. Gold 45.298 unrestamped.

| Item | Result |
|---|---|
| `admit_paid_f4` | GCD DirectLU/Krylov admitted; AES Krylov REFUSED (~14484 MiB) and logged |
| `solve_f4` | AES Krylov `n_r=73139` does **not** launch (status REFUSED) |
| Champ residual | `residual_vs_reference_mv` prefers SolveResult, signed QoR fallback |
| `attr.activity_status` | stamped from `artifacts.solve` on F4 evaluate paths |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_dse.py` | ALL PASSED (~264 s); DirectLU 6.075 reference, Krylov 6.092 accelerator; current finish ≠ 45.298 |
| `test_heavy/designs/frame/dispatch/actions` | ALL PASSED |

## 2026-08-31T17:00Z — PLAN passo 1: delta_vs_baseline

Reconcile `Candidate.delta` (vs parent) vs attr baseline-delta (vs liberty_default). No AES Krylov. 73k-R / 6.954 untouched. Gold 45.298 unrestamped.

| Item | Result |
|---|---|
| Writer | `controller._attach_delta` writes `attr.delta_vs_baseline` via `qor_delta` |
| Dual-read | `metrics.baseline_delta_of` prefers new key, falls back to historical `attr.delta` |
| `Candidate.delta` | unchanged (vs parent); schema test asserts it is not overwritten |
| Studio | no `attr.delta` readers |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_heavy_analysis.py` | HEAVY_GUARD_OK |
| `test_designs.py` | ALL PASSED |
| `test_frame.py` / `test_dispatch.py` / `test_actions.py` | ALL PASSED |
| `test_dse.py` | ALL PASSED (~260 s); DirectLU 6.075, Krylov 6.092; current finish ≠ 45.298 |

## 2026-08-31T16:40Z — Candidate schema + SolveResult (no DesignState type)

Harden existing `Candidate` + F4 contract. No parallel DesignState. No AES Krylov. 73k-R / 6.954 untouched.

| Item | Result |
|---|---|
| `Candidate.delta` | child−parent on shared QoR axes; missing omitted |
| Roles | knobs=action, artifacts=observation, attr=interpretation, pred=prediction |
| `SolveResult` | A=reference, B/C/D=accelerator, \|A−C\|, activity_status, backend_requested/actual |
| `admit_solve` | single gate; AES Krylov 15 GiB **REFUSED** (~14484 MiB est.) |
| GCD A/B/D/C via `solve_f4` | 6.075 / 6.075 / 6.075 / 6.092 mV; not 45.298 |
| `test_candidate_schema.py` | SCHEMA_CONTRACT_OK |
| `test_heavy_analysis.py` | HEAVY_GUARD_OK |
| `test_designs.py` | ALL PASSED, 73k pin, SHA of jsonl unchanged on read |
| `test_dse.py` | ALL PASSED; current finish ≠ reference_run 45.298 |

## 2026-08-31T15:33Z — GCD finish + per-solver IR + AES F5-lite OK

Safe subset under `prlimit --as=8GiB`. No AES Krylov. 73k-R / 6.954 mV untouched.

| Item | Result |
|---|---|
| GCD FlowLab `make finish` 0.46 ns | **OK** ~52 s, RSS ~913 MiB, `6_final.odb/gds/spef` |
| Dynamic IR A DirectLU | **OK** `n_r=5816`, droop **6.075 mV**, `A_direct_be` |
| Dynamic IR B SA-AMG | **OK** 6.075 mV, \|A−B\| ≈ 0 |
| Dynamic IR D RAS | **OK** 6.075 mV, \|A−D\| ≈ 0 |
| Dynamic IR C Krylov m=96 | **OK** 6.092 mV, \|A−C\| = 0.017 mV, RSS ~677 MiB |
| AES F5-lite 2 DRT, no CTS | **OK** id `25176b74aba8`, WNS **−2.0546 ns** (OpenSTA SPEF), SDC AES 0.82 ns, `top=aes_cipher_top`, `clock=ideal`, 53381 rc segs, 1106 s, DRT peak ~1074 MiB. Prior fails: DRT-0305 / TCL SIGNAL / 540 s timeout. |
| 73k-R pin | `febe6804241c` still `n_r=73139`, static **6.954 mV**, dynamic GAP |
| `test_designs.py` | **ALL PASSED** including live F5 SDC/top/clock and cloud 17.745 mV |

This FlowLab Dynamic IR is **6.075 mV**, not gold 45.298. Re-run F5: `ALLOW_HEAVY_ANALYSIS=1 ./scripts/run_aes_f5_lite_cloud.sh` (default timeout 1200 s). Do not set `AES_F5_ALLOW_CTS=1`.

Still out of scope: AES Krylov, F5-CTS, full AES DSE controller, gold restamp, combined A+B+C+D+VSS+electrothermal, uncapped `solve_f4`.

## 2026-08-31T13:50Z — analysis draft Build SUCCEEDED

[`bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914) **SUCCEEDED** (~19 min). Draft; warming skipped; does not become the default boot snapshot until activated.

| Check | Result |
|---|---|
| Profile | `Profilo analysis EDA_JOBS=2` |
| OpenSTA standalone | skipped |
| `libdpn.so` | OK, `ALL dpn_test PASSED` (synthetic only) |
| Studio npm | 453 packages |
| Smoke | `CLOUD_SMOKE_OK` (openroad 26Q2, yosys 0.63, klayout, sta 3.1.0) |
| Install | exit 0, snapshot ready |
| Heavy work during install | none (no AES / DSE / Krylov) |

## 2026-08-31T13:35Z — remaining jobs under 15 GiB

Executed the four remaining safe items. No Krylov. No overwrite of 73k-R / 6.954 mV.

| Item | Result |
|---|---|
| GCD FlowLab DSE `./scripts/run_dse_gcd_cloud.sh` budget 45 s, `prlimit --as=8GiB` | **OK** resume, 113 candidates, 2.41 s, RSS 56 MiB, exit 0. Did not wipe memory (`DSE_FRESH` refused). |
| AES F1–F3 `AES_SLICE_SKIP_F4=1` under 8 GiB | **OK** reuse F1 `c6c1a7e0ad2c` / F3 WNS −1.3258 ns / GPL `bd74975200c1`, 0.20 s. F4 left to the cloud wrapper. |
| AES F4 cloud wrapper | Without flag: **REFUSED** exit 2. With flag: **reuse** `8c589d0cc392` droop 17.745 mV in 0.42 s (no re-solve, `PDN_DISABLE_KRYLOV=1`). |
| Ingest new PDN candidate | **OK** id `8c589d0cc392`, `n_r=66295`, static 12.953 mV, droop **17.745 mV**, knobs `via=cloud_agent_directlu`. 73k-R row `febe6804241c` still 6.954 mV, dynamic GAP. Idempotent second ingest. `test_designs.py` PASSED including the new cloud asserts. |
| Install profile | `environment.json` now `PD_FLOW_PROFILE=analysis EDA_JOBS=2`. |
| Draft Build analysis | **SUCCEEDED** [`bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914) — `CLOUD_SMOKE_OK`, `libdpn` + `dpn_test`, OpenSTA skipped. Draft only. |

Not run: AES F5, full AES DSE controller, gold 45.298, `run_dynamic_ir.sh` AMG+Krylov+RAS, uncapped `solve_f4`.

## 2026-08-31T08:41Z — timeout vs RAM

Tried raising timeout and RAM so AES F4 could run on this Cloud Agent.

| Item | Result |
|---|---|
| VM RAM | **cannot raise** — 15 GiB / 4 CPU / swap 0. `environment.json` has no memory/cpu fields; Cursor schema `unevaluatedProperties: false`. `swapon` fails. Docs: Enterprise support only. |
| F4 timeout | **can raise** — `PDN_SOLVE_TIMEOUT_S` (600 / 1800). Session timeout cannot. |
| RSS budget | AES Krylov 73k-R ~14.5 GiB **REFUSED** even with `ALLOW_HEAVY_ANALYSIS=1`. DirectLU estimated 828 MiB, allowed. |
| GCD F4 DirectLU `timeout=600` | **OK** `n_r=4656`, droop 16.642 mV, static 12.887 mV, 16 s, RSS 395 MiB |
| DirectLU 54 289-node 2D grid | **OK** factor 0.36 s, 130 solves 0.56 s, RSS 125–164 MiB |
| AES F1 remap | **OK** ~8 s |
| AES write_pg_spice | **OK** `n_r=66295` `n_i=9964` in 5.5 s |
| AES static IR (parse+LU) | **OK** 12.953 mV, 49 282 nodes, RSS 201 MiB |
| AES F4 DirectLU dynamic | **OK** with `prlimit --as=8GiB` and `PDN_SOLVE_TIMEOUT_S=90`. Droop **17.745 mV**, static 12.953 mV, `A_direct_be`, 48 s, not gold. First uncapped attempt recycled the pod. |
| AES Krylov | still **REFUSED** on 15 GiB RSS budget |

Timeout yes (`PDN_SOLVE_TIMEOUT_S`). RAM no. AES F4 is testable here with DirectLU + RSS cap, not with Krylov. Re-run: `ALLOW_HEAVY_ANALYSIS=1 ./scripts/run_aes_f4_cloud.sh` (8 GiB `prlimit`, 90 s timeout). Do not overwrite the 6.954 mV / 73k-R row in `memory_aes.jsonl` — `test_designs.py` pins that mesh.

## 2026-08-31T07:45Z — goal complete

| Gate | Result | Evidence |
|---|---|---|
| Prior Set-environment chat | FAIL | Session expired. Krylov MOR on AES ~73k-R mesh; VM thrashing. |
| Recurring Build (old full install) | OK | [`bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c) |
| Static bootstrap + AES refuse | OK | `CLOUD_BOOTSTRAP_TEST_OK`; `run_aes_f4.py` exit 2 |
| GCD relaxed RTL→GDS (this VM) | OK | `6_final.gds` 508K, DRC 0, WNS 0.00, setup viol 0, SDC 2.0 ns |
| Draft Build core | OK | [`bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c) — skipped OpenSTA+libdpn, `CLOUD_SMOKE_OK`, install exit 0 |
| Fresh agent on that Build | OK | Agent `bc-95543107-7d79-5ef7-b947-5349568b62e7` booted from the draft Build. Smoke OK, AES refused, `libdpn` absent, OpenSTA standalone absent, GCD synth `1_synth.odb` 608K |

No AES / Krylov / 73k-R mesh was run in this goal.

## 2026-08-31T07:22Z — GCD relaxed RTL→GDS OK (parent VM)

`./scripts/run_gcd_e2e_relaxed.sh finish` — variant `e2e_relaxed`, SDC **2.0 ns**.

| Item | Result |
|---|---|
| `1_synth.odb` | OK, chip area 628.824 µm², 35× DFF_X1 |
| `6_final.gds` | OK, 508K |
| DRC `5_route_drc.rpt` | **0** lines |
| STA finish | WNS 0.00, TNS 0.00, setup viol **0**, `period_min` 0.83 ns |
| Peak RSS (detail route) | 861 MB |
