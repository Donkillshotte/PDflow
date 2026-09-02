# PLAN — Phase 2: I(t) guiding scenario, honest gated front, declarative IR queue

Repo navigation: [`docs/README.md`](docs/README.md). This plan is
**Phase 2 lab** (IR controller), not the knob/finish product.
Lab: [`docs/laboratorio.md`](docs/laboratorio.md).

Status: step A ✅, E ✅, B ✅, C1 ✅, C2 ✅, C3 ✅, C4 ✅, C5 ✅, C6 ✅, C7 ✅, D.1 ✅, D.2 ✅, D.3 ✅, D.4 ✅, D.5 ✅. Steps run **in order**; each step closes
only with the indicated green tests and a dedicated commit. No step introduces a
parallel `DesignState` type: tighten what exists.

Phase 1 (schema → declarative slices) is **closed** at `ca47126`
(steps 0–6). This document replaces it as the executable plan.
References: `learn/dse/README.md`, `.cursor/SETUP_LOG.md`, PR #2.

---

## Diagnosis (state after Phase 2 D.5 + cleanup, 2026-08-31)

Measured on the current tree, not from memory. Phase 1 snapshot (`ca47126`:
controller 4920, inlined IR queue, `test_dse` 4925) is archive.

| File | Lines | Role |
|---|---:|---|
| `learn/dse/controller.py` | 3062 | Ingest/F1 teacher inlined → `STAGES_*` C1–C6 → `run_next_refine` → `STAGES_IR_SOLVERS` → report. Import only names in use |
| `learn/dse/acquire.py` | 3146 | **66** `should_pay_*` remain (stage + test). Not deleted |
| `learn/dse/stages.py` | 2264 | Slices C1–C7: steer-gap / IR_STEER / IR_CELL / IR_CHAMP / inspect / region-cell / IR_SOLVERS |
| `learn/scripts/test_dse.py` | 51 | Runner: D.1 metrics → D.2 memory → D.3 planner → D.4 steer → D.5 live F4 |
| `learn/scripts/test_dse_metrics.py` | 43 | D.1 dominates / gated / HV / EHVI |
| `learn/scripts/test_dse_memory.py` | 172 | D.2 JSONL / BOiLS / e-graph / catalogs |
| `learn/scripts/test_dse_planner.py` | 1320 | D.3 attribution / `plan_search` / F1 |
| `learn/scripts/test_dse_steer.py` | 3279 | D.4 residual / F5 / IR leftover / champ / static |
| `learn/scripts/test_dse_live_f4.py` | 166 | D.5 live F4, imported last; one process, one job |
| `learn/dse/current_scenario.py` | 204 | `source` guides I(t) (step A) |
| `learn/scripts/dse_f4_worker.py` | 368 | `plan_events` respects `source`; triangle does not steal STA |
| `learn/dse/planner.py` | 812 | `prefer_gated` + `pareto_gated` (step B). Parent F1 remains F1-only |
| `studio/.../DsePanel.tsx` | — | Reads `pareto_gated`. Heatmap/suite say `current_run`, not “A gold” |

**What is already true (do not redo).**

- `STAGES_LOGIC_TRANSFORM` / `STAGES_PLACE_ROUTE` / `STAGES_F4_HEAD` run
  as tables. GRT sits between STA and SDF **by data**, not by comment.
- `STAGE_F5_PORT` and `STAGE_PHYSICAL_CATALOG` remain singletons because
  residual/port/f2_region split them.
- Refine depth ≥ 1 is already generic: `dispatch.run_next_refine` +
  `actions.py` + `frame.py`. It is not a controller block to “tabulate”.
- `f1_pareto_parents` = area-best + WNS-best **F1 only**. Correct for
  F1→F2.
- GCD finish live: DirectLU **6.075 mV**, `current_scenario.source=sta_t50`,
  `n_r` worker **5816**. Gold **45.298** intact. AES `febe6804241c` intact.
- `leftover_cone_region_next` / `winning_ir_region_next` are already inspector
  closed-loop (`kind ∈ {extract, pdn}`), not one-shot.
- Gap 1 (stamp scenario) closed in A: `source` decides STA/VCD/SAIF.
- Gap 2 (Pareto gated) closed in B: Studio reads `pareto_gated`.
- Gap 3 (photocopied IR queue) closed in C1–C7: queue in `STAGES_*`.
- Gap 4 (two IR numbers) closed in E: `current_run` vs `reference_run`.
- Gap 5 (`test_dse` monolith) closed in D.1–D.5: runner + five modules.

**What remains outside (not a Phase 2 gap).**

AES as second GCD (cones, e-graph, F5-CTS, Krylov, full DSE controller),
ibex slang, CUDA, CCS on Nangate45, free closed-loop synth↔PD, DesignState,
LLM/GNN as controller center, restamp the gold.

---

## Permanent constraints (apply to every step)

- Cloud VM ~15 GiB / 4 CPU / swap 0. One heavy job only; `prlimit --as=8GiB`.
- **Never** Krylov/MOR on AES mesh ~50–70k R. `admit_solve` must refuse.
- **Never** overwrite `memory_aes.jsonl` row `febe6804241c`
  (`n_r=73139`, static **6.954 mV**).
- **Never** restamp GCD gold 45.298 mV
  (`learn/sim/reports/dynamic_ir_flowlab.json`).
- Current FlowLab finish = **6.075 mV** on `n_r=5816`: it is `current_run`,
  not `reference_run`. Tests do not confuse them. `n_r_from_spice` (~5821)
  ≠ worker `n_r`: do not pin 5816 on the spice row.
- AES SDC 0.82 ns, `top=aes_cipher_top`; F5 AES refuses path `/gcd/`.
- Tests synthetic or GCD-scale only. `pkill -f` forbidden (kill by PID).
- DirectLU = numerical reference. B/C/D = accelerator + error vs A.
- **Do not** `mem.touch` on cached F4 hit (breaks
  “live memory is not restamped, got 113”).
- **Do not** delete `should_pay_*` that stages or tests still call.
  `test_dse.py` asserts `why` fragments (`"not bumps"`, `"not gold"`).
- **Do not** replace `f1_pareto_parents` for F2-fast. F1-only is correct.
- **Do not** use an F5 as host of the *first* `cell_size_up`:
  `evaluate_cell_size` wants `mapped_v` from an F1 netlist.
- One `test_dse.py` at a time (~5 min). Fast suite does not launch F4.

Regression tests to keep green at every step:

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_candidate_schema.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_heavy_analysis.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_designs.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse.py        # ~5 min with F4
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_frame.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dispatch.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_actions.py
```

Steps A / B / E (no new mesh): schema + designs + head of `test_dse`
suffice locally; `test_dse` live remains the gate before commit if you
touch worker / `solve_f4` / IR report.

---

## Step A — I(t) guiding scenario (small, high honesty)

**Problem.** `CurrentScenario` is serialized on argv and on
`SolveResult.activity_via`, but `plan_events` in
`learn/scripts/dse_f4_worker.py` (around 165–181) loads STA/VCD/SAIF from
file flags. `build_worker_cmd` (`learn/dse/f4_oracle.py` 175–201) adds
`--sta` if the path exists, even when `source=ideal_triangle`.

**Do not change.** Infer default GCD finish (`kind=="finish"`, `design_id=="gcd"`,
STA on disk, no explicit `source`) stays `sta_t50`. That is the 6.075 path.
`liberty_ccs` stays GAP. Missing waveform stays ABSENT, never invented.
`pdn_activity.plan_events` signature unchanged: the worker decides *what* to pass.

**Changes.**

1. `dse_f4_worker.py` after parsing `--scenario`:
   - `ideal_triangle` → do not load STA/VCD/SAIF even if files exist;
     `plan_events(..., sta_arrivals=None, vcd=None, saif=None)`.
   - `sta_t50` + `activity_status=ABSENT` → do not apply STA; GAP/ABSENT
     status already covered by infer.
   - `sta_t50` + REAL → load only `--sta` (as today for 6.075).
   - `vcd`/`saif` + ABSENT → do not pass files (already true in `build_worker_cmd`).
   - `vcd`/`saif` + REAL → waveform; do not promote STA to source.
   - `liberty_ccs` → unchanged (exit 0 + GAP).
2. `build_worker_cmd`:
   - `source=ideal_triangle` → `--no-sta`, no `--sta`, no activity flags.
   - `source=sta_t50` and STA file → `--sta` (GCD 6.075 unchanged).
   - `source=sta_t50` and STA missing → `--no-sta`, scenario ABSENT.
3. No new field on `CurrentScenario`. Fingerprint already includes `source`.

**Acceptance.**

- `test_candidate_schema.py`: default GCD cmd contains `--scenario` + `sta_t50`
  and `--sta` (or STA path). Explicit `ideal_triangle` cmd has `--no-sta` and
  **not** `--sta`, even if GCD STA is on disk.
- `test_designs.py`: AES waveform-free stays without `--vcd`/`--saif`.
- `test_dse.py` live A: DirectLU **6.075** ± 0.05, `source=sta_t50`,
  `activity_via.scenario.source=sta_t50`, ≠ 45.298.
- Explicit triangle on same mesh: `activity_status=SYNTHETIC`.
  **Do not** pin droop to 6.075 (may differ). An argv unit test
  suffices; do not launch a second live F4 in step A if the first is already
  `sta_t50`.
- Gold unrestamped. No AES Krylov.

---

## Step B — Gated front as preference, not as F1→F2 (small)

**Problem.** Step 5 wrote the contract (`dominates_with_fidelity`,
`pareto_front_gated`, `next_candidate_ids`) and prints it. Real parents
remain F1 winners. Studio (`DsePanel.tsx` ~191–192, ~630) badges
`report.pareto`.

**Do not.**

- Replace `f1_pareto_parents` / `f1_area_winner` / `f1_wns_winner`
  for F2-fast, cell *first shot*, net *first shot*, F4 extract host.
  Those hosts must be mapped F1 netlists (`mapped_pick` + `mapped_v`).
- Let residual/port/IR pick from the gated front: host is
  residual (`steer_from_*`), not a WNS.
- Change `pareto_front` (historical reports).
- `test_dse.py` checks “area winner is liberty_default” / “WNS winner is
  the delay-improved sequence” stay green without touching values.

**Changes.**

1. `learn/dse/planner.py` (or `metrics.py`): helper
   `prefer_gated(mem, level, cands, *, pred=None) -> list`.
   Filter/sort `cands` keeping those on the gated front at that level;
   if the front is empty, return `cands` unchanged. Does not invent hosts.
2. One real consumer, not a dead helper:
   - Studio `DsePanel.tsx`: badge and count use `pareto_gated` if
     present, fallback to `pareto`. TS type: add `pareto_gated?`.
   - Optional and only if a C batch introduces a mixed list at the same
     level (e.g. multiple measured F4 extracts): `prefer_gated` on *that*
     list. Do not anticipate.
3. Unit in `test_dse.py` (metrics block at top, gated already there):
   better F1 WNS + worse F5 WNS both stay on the gated front;
   a “WNS-only” picker would keep only F1 — document that `prefer_gated`
   does not do that reduction.

**Acceptance.**

- `test_dse.py` green without changing expected F1 winner values.
- `test_candidate_schema.py` / `test_frame.py` green.
- Studio: type accepts `pareto_gated`; no mandatory layout change
  beyond reading the right key. Manual check on DSE page only
  if the step touches visible CSS/markup.

---

## Step E — Two labeled IR numbers (small, after A)

**Problem.** Tests know 6.075 ≠ 45.298. Studio and copy still say
“Solver A golden” on current finish (`DynamicIrHeatmap.tsx` ~295, ~594;
`suite.ts` “Solver A gold”).

**Changes.**

- F4 / DSE report: explicit fields `current_run_mv` (live finish) and
  `reference_run_mv` (45.298, read-only from gold JSON, never restamp).
  If gold file missing, `reference_run_mv=null` — do not invent.
- Studio copy: “A = DirectLU current_run” vs “reference_run 45.298
  (historical gold, unrestamped)”. Do not rename `solver_kind=direct`.
- `test_candidate_schema.py` or head `test_dse`: keys exist and
  `current_run_mv` is not 45.298 on GCD finish path.

**Do not.** Restamp gold, change signoff thresholds, touch
`febe6804241c`, merge the two JSONs `dynamic_ir_flowlab.json` and
`dynamic_ir_flowlab_direct.json`.

**Acceptance.** Gold file byte-identical. Live A stays 6.075. UI does not
present 6.075 as gold.

---

## Step C — Strangler of the queue (same rule as 3a–3e)

Batch order **sacred** (`via` / residual / extract_id dependencies).
One batch = one commit. `why` / `step` / `via` / `fidelity` identical to
the inlined block. `test_dse.py` green **without** changing expected values.
Measure `wc -l learn/dse/controller.py` before/after. Domain `should_pay_*`
stay in `acquire.py`; stages call them.

Pattern already proven: `Stage` + `run_*` + `_pay_and_maybe_eval`.
Closed-loop loops (`leftover_*_next`): **not** a one-shot `Stage` —
helper `run_inspect_loop` calls the inspector, pays extract or PDN,
repeats until `None` / wall / cap already in tests (4 iter leftover-cone-region).

F4 remain `needs_admit=True` and go through `ctx["admit_paid_f4"]` +
controller `evaluate_f4_*` wrapper (stamp SolveResult, no restamp
live JSONL).

F1 teacher (BOiLS while + ctrl-cone, ~751–890) **stays inlined**. Not
photocopied IR; it is SSK-GP/EHVI acquisition.

### C1 — residual_steer + port_steer + f2_region

Sit **between** `STAGES_PLACE_ROUTE` and `STAGES_F4_HEAD` (controller ~939–1070).

| Block | `should_pay_*` | `fidelity` acquire | evaluate |
|---|---|---|---|
| residual_steer | `should_pay_residual_steer` | `RESIDUAL_STEER` | `evaluate_f5_local` / `evaluate_cell_size` / `evaluate_net_buffer` on `steer["level"]` |
| port_steer | `should_pay_port_steer` | `PORT_STEER` | `evaluate_net_buffer(..., source="net_buffer_spef")` |
| f2_region | `should_pay_f2_region` | `F2_REGION` | `evaluate_f2_gpl` + `extra_knobs` region; parent = `_mapped_pick(F1 winners)` |

After C1 you may merge `STAGE_F5_PORT` / `STAGE_PHYSICAL_CATALOG` into nearby slices
**only if** runtime order stays identical (port after residual,
catalog before f2_region, f2_region before F4_HEAD). If merging slices
breaks comment/order, leave the two singleton stages.

**Acceptance.** Planner checks “schedules residual-steered / port / f2_region”
unchanged. No new QoR values. Controller lines ↓.

### C2 — ir_steer + host_ir_steer + f4_scale_win

`while planned_*` (~1074–1232). Loop cap already in `should_pay_ir_steer`
(“IR-steer loop caps at region family + unused catalog”).

| Block | pay | via child |
|---|---|---|
| ir_steer | `should_pay_ir_steer` + `steer_from_ir_residual` | `active_f4_ir` |
| host_ir_steer | `should_pay_host_ir_steer` + `steer_from_host_ir_residual` | `active_f4_host_ir` |
| f4_scale_win | `should_pay_f4_scale_win` | `f4_iscale_win`; host `iscale_parent` + `winning_host_pdn` |

Loop = `run_inspect_loop` or `Stage` with `max_shots` aligned to existing cap.
Do not raise the cap.

**Acceptance.** `test_dse` block on `steer_from_ir_residual` /
`should_pay_ir_steer` (decap_200f → pkg_l_100p, n_steer cap) unchanged.

### C3 — ir_cell family (depth 0, not refine)

~1234–1474. Order: size → extract → PDN → region → region PDN.

| planner level | pay | via / source |
|---|---|---|
| `ir_cell` | `should_pay_ir_cell` | `cell_size_ir` / `active_f4_ir_cell` |
| `ir_cell_extract` | `should_pay_ir_cell_extract` | `f4_ir_cell_extract` |
| `ir_cell_pdn` | `should_pay_ir_cell_pdn` + `steer_from_ir_cell_residual` | `active_f4_ir_cell_pdn` |
| `ir_cell_region` | `should_pay_ir_cell_region` | region density cap |
| `ir_cell_region_pdn` | `should_pay_ir_cell_region_pdn` | restamp PDN |

Host: `iscale_parent` / `ir_cell_host` (attribution, not Pareto).

### C4 — winning_ir catalog + iscale_champ + ir_cell_champ family

~1476–1927.

| level | note |
|---|---|
| `winning_ir_pdn` | `should_pay_winning_ir_catalog` / steer unused Dynamic IR |
| `f4_scale_champ` | `should_pay_f4_scale_champ` |
| `ir_cell_champ` | size-up on champ |
| `ir_cell_champ_extract` / `_pdn` | mesh + restamp |
| `ir_cell_champ_cone` / `_extract` / `_pdn` | cone dpath/ctrl; leftover modules already in `acquire` |

Champ `via` (`active_f4_ir_cell_champ_*`) are strings pinned in tests.
Copy them.

### C5 — inspector loops leftover-cone-region and winning_ir_region

~1929–2150. Already `leftover_cone_region_next` / `winning_ir_region_next`.

Extract `run_inspect_loop(ctx, next_fn, handlers)` in controller or
`stages.py`. The `for _ in range(4)` leftover-cone-region and the
winning-IR-region loop stay cap/why identical, including the first denied
acquire `"no leftover-cone-region extract or |Δ| PDN"`.

**Do not** convert these loops into a single `Stage(max_shots=1)`.

### C6 — winning_ir_region_cell depth 0 (size / extract / PDN)

~2175–2316. Depth ≥ 1 is already `run_next_refine` **right after** (~2333).
Do not merge depth 0 into dispatch in this batch: `frame.py` treats
empty suffix as depth 0, but the current controller pays depth 0
inlined then enters the refine while. Changing that boundary is a
separate refactor, outside C6.

Pay: `should_pay_winning_ir_region_cell` / `_extract` / `_pdn`.

### C7 — champ AMG/RAS/Krylov + static IR/mesh/straps + EM (last)

~2361–2782. Steer-special, last because they read champ/static already written.

| acquire fidelity | pay | solver / catalog |
|---|---|---|
| `F4_AMG_CHAMP` | `should_pay_f4_amg_champ` | `evaluate_f4_pdn(..., solver="amg")` |
| `F4_RAS_CHAMP` | `should_pay_f4_ras_champ` | `solver="ras"` |
| `F4_KRYLOV_CHAMP` | `should_pay_f4_krylov_champ` | `solver="krylov"` + residual vs Direct champ |
| `F4_STATIC_IR` | `should_pay_static_ir_steer` | `steer_from_static_ir_residual` |
| `F4_STATIC_MESH` | `should_pay_static_mesh` | bump catalog |
| `F4_STATIC_STRAPS` | `should_pay_static_straps` | pitch catalog (`"not bumps"` / `"not gold"`) |
| `F4_EM_STRAPS` | `should_pay_em_straps` | width catalog |

Krylov **only** on admitted GCD champ. `admit_paid_f4` stays.
No AES.

After C7 controller `run_controller` should be: ingest/teacher F1
→ logic slice → place-route slice → C1 stages → F4 head slice → C2–C7
stages/loops → `run_next_refine` while → report. Photocopied queue
gone; F1 teacher no.

**Acceptance for each C batch.** Fast suite + `test_dse.py` ALL PASSED.
Live droop 6.075 / `sta_t50`. Gold unrestamped. SETUP_LOG with Δ controller
lines. One commit.

---

## Step D — Split `test_dse.py` (after C, one module per commit)

**Problem.** 4925 lines, one `main()`. Phase 1 said “stage by stage
during 3”: not done. Doing it **now** in one shot breaks the 5 min gate.

**Rule.** One extracted file per commit. Same `check()`. `test_dse.py`
remains the entrypoint that imports and calls pieces, so CI/docs stay

`PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse.py`.

Natural cuts (order):

1. `test_dse_metrics.py` — dominates / gated / HV / EHVI (current head ~50–220).
2. `test_dse_memory.py` — JSONL / BOiLS / e-graph / catalogs.
3. `test_dse_planner.py` — attribution, `plan_search`, f1 winners.
4. `test_dse_steer.py` — residual / F5 / IR leftover / champ / static (bulk).
5. Live F4 A/B/D/C **stays** in `test_dse.py` (or `test_dse_live_f4.py`
   imported last). One process, one heavy job.

**Do not.** Two parallel `test_dse`, pin `n_r` spice=5816, split the
live block into four processes.

**Acceptance.** Same number of `ok` / same messages. `test_dse.py`
ALL PASSED ~5 min. No new expected values.

---

## Explicitly NOT in plan

- Parallel `DesignState` type to `Candidate`.
- LLM / GNN / e-graph / RL as controller center.
- Free closed-loop synthesis↔PD (stays: parameter-DSE, then structural;
  refine chain is already IR search).
- Restamp gold 45.298; F5-CTS AES; Krylov AES; full AES DSE; ibex slang; CUDA.
- Flatten knobs across levels.
- Delete the 66 `should_pay_*` “because generic exists”.
- Use gated front to promote F1 to F2 or for first cell size-up.
- Merge depth-0 winning_ir_region_cell into `run_next_refine` inside C6.
- Flatten F1 BOiLS teacher.

---

## Commit order

```
1  I(t) guiding scenario                         (step A)
2  current_run vs reference_run labels          (step E)
3  prefer_gated + Studio reads pareto_gated    (step B)
4  C1 residual / port / f2_region
5  C2 ir_steer / host_ir / iscale_win
6  C3 ir_cell family
7  C4 winning_ir + champ family
8  C5 inspect loops leftover / winning_ir_region
9  C6 winning_ir_region_cell depth 0
10 C7 champ solvers + static/EM
11 (opt) test_dse_metrics.py extracted          (step D.1)
12 (opt) test_dse_memory.py extracted           (step D.2)
13 (opt) test_dse_planner.py extracted          (step D.3)
14 (opt) test_dse_steer.py extracted            (step D.4)
15 (opt) test_dse_live_f4.py extracted          (step D.5)
```

Each commit: green tests for the batch, line in `.cursor/SETUP_LOG.md`,
push, update PR #2. One `test_dse` at a time.

---

## How Phase 2 success is measured

- Worker: `source` decides STA/VCD/SAIF; explicit triangle does not “steal” STA.
- GCD live A stays **6.075 mV** + `sta_t50`. Gold 45.298 and AES
  `febe6804241c` intact.
- Studio does not badge an ungated front as gated; does not call
  6.075 “gold”.
- `run_controller` after C7 no longer has photocopied IR_STEER…EM blocks;
  F1 teacher and `run_next_refine` remain the two non-table loops, for
  different reasons (acquisition vs generic refine).
- `test_dse.py` can become a runner; live F4 stays one job.

Phase 1 archive (git, do not re-run): 0 `3bd9479` · 1 `4c4bcc7` ·
2 `9e1bab4` · 3a `74e1173` · 4 `aed3a6d` · 3b `c5f1d4a` · 3c `d4d2548`
· 3d `b2b96c9` · 3e `d94df2f` · 5 `9785bca` · 6 `14b6e47` / `ca47126`.
