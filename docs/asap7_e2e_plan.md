# ASAP7 end-to-end consolidation plan

Living plan. Not a frozen DSE plan. Not a course switch. Not a product
win surface. Do not restamp gold Dynamic IR **45.298 mV**. Do not
overwrite `nangate45/gcd/flowlab`. Do not write `.lvs.ok`. Do not
launch AES finish "just to see". One heavy cook at a time.

Question: the lab ASAP7 track already cooks single variants and has
close paths for each leftover (`asap7_close_plan.md`). What is still
missing for the track to work **end-to-end, for every phase**, on any
machine that has this repo and the toolchain — and how do we
consolidate what exists so the whole chain is one reproducible,
honest path instead of a folio of hand-launched cooks?

**Answer: the pieces exist; the chain does not.** Every phase
(synth → floorplan → place → CTS → route → finish, plus DRC, LVS,
setup/hold pair, layer-1 SPICE, IR readout, and reporting) has a
script or a knob today, but they are wired as separate hand runs.
The e2e test (`test_asap7_e2e.py`) asserts eleven live GDS with
`must_exist=True` and there is no runner that recreates them; a
fresh clone fails the gate by construction. This plan turns the
track into a serial, resumable, phase-checkpointed pipeline with
one entry point, honest per-phase verdicts, and the same refuse
rules it has today.

Checked on disk 2026-09-05. Implementation of W1–W10 landed on this
branch (`run_asap7_e2e.py`, stage ledger, leftover-named DRC, `--variant`
on LVS/MMMC, suite hooks, two-tier e2e test). W11 stays a named GAP.
A fresh clone still passes tier 1 without GDS. On a toolchain
machine the runner rebuilt all twelve cookable specs serially;
`test_asap7_e2e.py` then passed tier 2. Live rows only (gitignored
folio) — not gold. uart 290 ps stayed open. Gold IR SHA intact;
Nangate FlowLab GDS absent (`nangate_lock_absent`). Evidence lines
below name the file that proves each claim.

---

## 1. What "end-to-end, all phases" means here

Two axes. Both must hold for the goal to be true.

### 1.1 Flow phases (one cook)

The ORFS make chain on `PLATFORM=asap7`, variant `lab_asap7_*`:

| # | Phase | ORFS artifact that proves it | Today |
|---|---|---|---|
| 1 | synth | `1_synth.v` (+ `1_1_yosys` log) | runs; only `6_final.gds` is asserted |
| 2 | floorplan | `2_*_floorplan*.odb` | runs; unchecked |
| 3 | place | `3_*_place*.odb`, `3_5_place_dp.json` | runs; unchecked |
| 4 | cts | `4_*_cts*.odb`, `4_cts_final.rpt` | runs; WC legalization leftover |
| 5 | route | `5_*_route*.odb`, `5_route_drc.rpt`, `5_1_grt.json` | runs; unchecked |
| 6 | finish | `6_final.{gds,def,odb}`, `6_report.json` | asserted by `test_asap7_e2e.py` |

"Works end-to-end" for a cook = every stage artifact exists and the
stage ledger records pass / STOP with a reason, not just a final GDS.

### 1.2 Analysis and reporting phases (per finish)

| Phase | Script today | Today's state |
|---|---|---|
| Timing readout (`period_min_ps`, `fmax_ghz`, `timing_closed`) | `asap7_lab.collect_report` | live, per cook |
| Setup WC / hold BC pair | `learn/scripts/lab_asap7_mmmc.py` | hand-run, one netlist |
| DRC (community KLayout `asap7.lydrc`) | none wired on this track | leftover counted only in prose |
| LVS (cell-vs-CDL, not Calibre) | `learn/scripts/lab_asap7_lvs.py` | hand-run, ~79% on gcd 480 ps |
| Layer-1 SPICE (Xyce, level 72→107) | `learn/scripts/lab_asap7_spice.py` | hand-run inverter |
| Layer-1 PDK inventory | `learn/scripts/lab_asap7_pdk.py` | hand-run |
| IR readout (new mesh, never gold) | `6_report.json` PSM keys via `_metrics` | live, per cook |
| Folio + last-run reports | `lab_asap7.json`, `lab_asap7_folio.json` | live, gitignored |
| Studio `/lab#asap7` + suite hook `asap7_layer1` | `studio/src/lib/suite.ts` | one hook only |
| Suite status table | `learn/reference/suite-status.md` | **no ASAP7 rows at all** |

"Works end-to-end" for the track = one entry point cooks the folio
serially, runs the analysis passes on each closed finish, stamps the
gitignored reports, and both tests (`test_asap7_lab.py`,
`test_asap7_e2e.py`) pass from that entry point alone — on a machine
with the toolchain, starting from zero cooked artifacts.

### 1.3 What end-to-end does NOT mean

- Not Calibre DRC/LVS (ASU tarball + 2017 license, gated —
  `asap7_layer1_plan.md`).
- Not a real SRAM (FakeRAM stays a named leftover).
- Not a 6-track finish (`ASAP7_TRACK=6` stays refused until a real
  second platform exists — §5.11).
- Not an ASAP7 gold stamp, not a product win, not a course swap.
- Not AES/jpeg/cva6/swerv without `ALLOW_HEAVY_ANALYSIS=1`, and
  never as part of the default e2e set.

---

## 2. Current state, with evidence

What exists and works (single runs, on a machine that cooked them):

1. **Spec + refuse layer.** `learn/dse/asap7_lab.py`:
   `LabAsap7Spec` builds `lab_asap7_*` variant names from
   design/corner/VT/lib/track/clk; `validate()` refuses locked
   variants, Krylov names, unknown corners/VT, 6-track, CCS without
   the five families, heavy designs without the flag. Tested by
   `test_asap7_lab.py` without cooking.
2. **Wrapper.** `scripts/run_lab_asap7.sh`: `prlimit --as/--cpu`,
   locked-variant regex, WC die default (`CORE_UTILIZATION=40`),
   slang capability gate, CCS liberty assignment for TC/WC, SDC
   written in Python (`write_constraint_sdc`) so `set -u` cannot
   expand ORFS variables. No `if design ==`.
3. **Report + folio.** `collect_report()` stamps a payload with
   `surface: lab`, `predictive: true`, `product_win: false`,
   `comparable_to_gold_ir: false`, a `leftover` block, and derived
   `period_min_ps` / `fmax_ghz` / `timing_closed`. `scan_folio()`
   walks every live `*/lab_asap7_*/6_final.gds`.
4. **Analysis scripts.** LVS (`lab_asap7_lvs.py`, GDS masters vs
   `.SUBCKT` names on fetched CDL, never `.lvs.ok`), MMMC pair
   (`lab_asap7_mmmc.py`, two OpenSTA jobs on one finish), layer-1
   inventory (`lab_asap7_pdk.py`), Xyce inverter
   (`lab_asap7_spice.py` with the level 72→107 patch).
5. **Fetches.** `fetch_asap7_libextras.sh` (CCS `.7z` + CDL),
   `fetch_asap7_pdk.sh` (GitHub half of layer 1),
   `fetch_asap7_sc6t.sh` (6T views). All land in gitignored paths.
6. **Live numbers already demonstrated** (from
   `asap7_close_plan.md`, not gold): gcd NLDM TC WNS −116 ps at
   310 ps; 430 ps still open (WNS −23); **480 ps closed**
   (WNS +5.38 ps, area 46.0 µm², power 0.424 mW, leak 35.9 nW,
   IR 2.46 mV, fmax 2.08 GHz); uart 270 ps WNS −18; CCS BC −22;
   WC −312; cell-vs-CDL ~79%.

What does not hold together:

1. **No orchestrator.** The eleven cooks that
   `test_asap7_e2e.py` asserts (`must_exist=True`: NLDM TC, CCS BC,
   WC, BC, RVT+LVT, MBFF, uart, 430 ps, 480 ps, CCS TC, CCS WC)
   were hand-launched. Nothing in the repo can rebuild that folio.
   On this fresh clone `results/asap7/` does not exist and the e2e
   gate cannot pass at all.
2. **Only the finish is checked.** A cook that dies at CTS leaves
   nothing but a nonzero exit and a stderr tail; there is no
   per-stage ledger, so "end-to-end for every phase" is not
   observable. The WC legalization leftover (DPL-0036) was
   diagnosed by hand, not by the report.
3. **Analysis passes are not attached to cooks.** LVS and MMMC run
   on whatever variant their argv points at; the folio does not say
   which finishes have been through DRC/LVS/MMMC and which have not.
4. **DRC is not wired at all** on this track. The platform ships
   `KLayout/` decks and the research note counts 33 items on gcd,
   but no script runs `asap7.lydrc` against a `lab_asap7_*` GDS and
   stamps a leftover-named count.
5. **Reporting gaps.** `learn/reference/suite-status.md` has zero
   ASAP7 rows while Studio already exposes the `asap7_layer1` hook;
   the WORKS/FAIL/GAP table silently omits the whole track.
6. **Hygiene.** `CCS_OK = {("BC", "RVT")}` in `asap7_lab.py` is
   dead code (defined, never read — the live gate is `ccs_ready()`);
   `flowlab_untouched()` is called in `cook()` and then ignored
   (`pass`), so the guard documents an intention it does not
   enforce; `collect_report()["ok"]` means "GDS exists" in one call
   site and "GDS exists and exit 0" in another.

---

## 3. Design of the consolidated track

One entry point, serial phases, resumable, honest.

```
learn/scripts/run_asap7_e2e.py  (new; the only new entry point)
  → plan: ordered list of specs (cheap first, §6)
  → for each spec:
      cook via scripts/run_lab_asap7.sh   (unchanged contract)
      stage ledger from logs/asap7/<nick>/<variant>/   (new, §5.2)
      skip if 6_final.gds already live (resume; no recook)
  → analysis passes on each live finish:
      DRC (KLayout asap7.lydrc, leftover-named)   (new, §5.5)
      LVS (cell-vs-CDL when fetched; else named GAP)
      MMMC pair (setup WC / hold BC) on closed finishes
  → layer-1 passes once per run (inventory + Xyce smoke)
  → write lab_asap7_folio.json with per-phase verdicts
  → exit nonzero if any REQUIRED phase failed; leftovers stay named
```

Rules the runner inherits, unchanged:

- One heavy job: the runner is strictly serial and does not
  pre-launch anything. `prlimit` stays in the wrapper.
- Variants stay `lab_asap7_*`; locked names refused twice (Python
  and bash), as today.
- Relaxed-clock cooks tag the variant (`_480ps`) and never
  overwrite the 310 ps GDS, as today.
- No gold stamps: every report stays gitignored; `45.298` and
  `gold_ir_mv` never appear in any payload (already asserted).
- No `if design ==` anywhere. Design-specific behavior comes from
  ORFS config files and capability probes only.

---

## 4. Phase-by-phase gap table

| Phase | Works today | Gap | Workstream |
|---|---|---|---|
| synth | yes (Yosys; slang fallback on uart) | not in any ledger; eqy leftover unnamed per cook | W2, W9 |
| floorplan | yes | unchecked; WC die default undocumented in report | W2 |
| place | yes | `3_5_place_dp.json` parsed nowhere on this track | W2 |
| cts | yes on BC/TC; WC needed die default | failure surfaces only as exit code | W2 |
| route | yes | `5_route_drc.rpt` ignored | W2, W5 |
| finish | yes, asserted | `ok` semantics inconsistent | W2, W9 |
| timing readout | yes | closure ladder (310→430→480) only in prose | W8 |
| DRC | **not wired** | no script, no count, no suite row | W5 |
| LVS | script exists | not attached to folio; CDL fetch-gated | W6 |
| MMMC pair | script exists | one netlist, hand-run; not per-finish | W4 |
| CCS | BC in pack; TC/WC after fetch | LVT/SLVT refused; fetch not in runner | W3 |
| layer-1 SPICE | inverter runs | not attached to the e2e run | W7 |
| IR readout | per cook | fine (never gold); no consolidation gap | — |
| folio/report | live | no per-phase verdicts; `ok` ambiguity | W2, W9 |
| Studio/suite | one hook | no suite-status rows; no per-phase hooks | W10 |
| e2e test | asserts 11 GDS | unbuildable on fresh clone; no runner | W1 |
| 6-track | refused | second platform is a project, stays gated | W11 |

---

## 5. Workstreams

Ordered. Each one is independently landable and independently
testable. None of them touches product code, course code, frozen
plans, or Nangate artifacts.

### 5.1 W1 — Reproducible e2e harness

**Why.** The e2e gate must be reachable from zero. Today
`test_asap7_e2e.py` is a *state* check (eleven GDS must already be
live) with no path that creates the state.

**What.**

1. New `learn/scripts/run_asap7_e2e.py`: builds the ordered spec
   list (§6), cooks each one through `scripts/run_lab_asap7.sh`,
   **skips** specs whose `6_final.gds` is already live (resume
   semantics — recook only with an explicit `--force` that still
   refuses locked variants), then runs the analysis passes and
   rewrites the folio.
2. `--dry-run` prints the plan (spec list, which are live, which
   would cook, estimated order) without touching ORFS. This is the
   fresh-clone smoke that CI-like checks can run without a
   toolchain.
3. `--only <variant>` cooks a single named spec for debugging;
   `--max-cooks N` caps the session, like `run_tpe.py` does.
4. The runner never parallelizes and never launches a heavy design
   unless `ALLOW_HEAVY_ANALYSIS=1` *and* the spec was explicitly
   requested. The default plan contains gcd, gcd-ccs, uart only.
5. `test_asap7_e2e.py` grows a documented two-tier mode without
   weakening the full gate: tier 1 (always) = spec/refuse/report
   invariants plus `--dry-run` plan shape; tier 2 (when GDS are
   live, i.e. after the runner) = today's `must_exist=True` checks,
   unchanged. A fresh clone fails tier 2 with a message that names
   the runner instead of a bare `FAIL live GDS missing`.

**Acceptance.** On a machine with the toolchain:
`python3 learn/scripts/run_asap7_e2e.py` followed by
`python3 learn/scripts/test_asap7_e2e.py` passes with zero manual
steps in between. On a machine without cooked artifacts:
`run_asap7_e2e.py --dry-run` and tier 1 pass.

**Risk.** Wall-clock: eleven cooks are hours. Mitigation: resume
semantics, `--max-cooks`, cheap-first order; the runner is
restartable at any point because state = artifacts on disk.

### 5.2 W2 — Per-stage checkpoints (the "all phases" core)

**Why.** End-to-end for every phase must be observable, not
inferred from a final GDS.

**What.**

1. New helper `stage_ledger(spec, root)` in `asap7_lab.py`: walks
   `logs/asap7/<nick>/<variant>/` and
   `results/asap7/<nick>/<variant>/` and returns, per stage
   (synth, floorplan, place, cts, route, finish), `{done, artifact,
   mtime, note}`. Stage names map to the ORFS numbered prefixes
   (`1_`…`6_`) so the helper needs no design knowledge.
2. `collect_report()` embeds the ledger under `payload["stages"]`
   and derives `payload["stopped_at"]` = first missing stage when
   the GDS is absent. The WC DPL-0036 class of failure then reads
   as `stopped_at: "cts"` with the tail of the stage log attached,
   instead of a bare exit code.
3. Parse what the flow already writes: `3_5_place_dp.json` (place
   WNS), `5_1_grt.json` (GRT wirelength/violations) — same parsers
   the product track uses in `f6_finish.py` (`parse_place_dp`,
   `parse_grt`) — imported, not duplicated.
4. Normalize `ok`: `ok` = GDS live **and** last cook exit 0;
   add `gds_live` = GDS exists regardless of the last exit. Both
   fields stamped; existing consumers keep working because `ok`
   only gets stricter.

**Acceptance.** A cook killed at CTS produces a report with
`stopped_at: "cts"`, `stages.route.done == false`, and the folio
row shows the same. `test_asap7_lab.py` gains synthetic checks for
the ledger (build a fake logs tree, assert stage mapping) — no
cooking required.

### 5.3 W3 — CCS consolidation

**Why.** CCS is the single biggest reason ASAP7 is in this tree
(`asap7_research.md`); the current story (pack has RVT+FF; extras
add RVT TT/SS; LVT/SLVT refused) is right but scattered.

**What.**

1. The runner (W1) probes `ccs_ready()` for TC/WC and, when the
   extras are missing, records the two CCS TC/WC specs as
   `refused: fetch extras with learn/scripts/fetch_asap7_libextras.sh`
   in the folio instead of dying. Fetching stays a human decision
   (network + ~size); the runner never fetches on its own.
2. Delete dead `CCS_OK` from `asap7_lab.py` (the live gate is
   `ccs_ready()`; a constant that says something else is a trap).
3. LVT/SLVT CCS stays a named refuse in `validate()` until the
   `.7z` archives for those VT are extracted; the refuse message
   already names the fetch script — keep it.
4. Document in `learn/lab/asap7/README.md` the exact make
   assignment the wrapper passes (`${CORNER}_CCS_LIB_FILES=…`) and
   that ORFS itself only defines `BC_CCS_LIB_FILES`.

**Acceptance.** With extras fetched, the default plan cooks
NLDM TC/BC/WC + CCS BC/TC/WC and the folio names all six.
Without extras, the folio names the two refusals with the fetch
command. `test_asap7_lab.py` already covers both branches
(`ccs_ready` true/false); keep both.

### 5.4 W4 — MMMC pair as a per-finish phase

**Why.** Setup at WC/SS and hold at BC/FF on one netlist is the
honest open-source MCMM this kit supports (Hammer corner table,
`asap7_close_plan.md` §12). Today it runs once, by hand.

**What.**

1. `lab_asap7_mmmc.py` takes `--variant` (default: latest closed
   finish in the folio) so the runner can invoke it per finish.
2. The runner executes it for every `timing_closed` finish in the
   plan and stores `{setup: {...}, hold: {...}}` per variant in a
   folio sidecar (`lab_asap7_mmmc.json` keyed by variant, still
   gitignored).
3. Open finishes are skipped with a named reason (setup at WC on an
   already-open TC netlist adds noise, not information).

**Acceptance.** After a full run, every closed finish has a
setup/hold pair row; `test_asap7_e2e.py` tier 2 asserts the pair
exists for the 480 ps cook (it already asserts the file — extend to
per-variant keys).

### 5.5 W5 — DRC as a wired phase (leftover-named)

**Why.** The platform ships KLayout decks
(`platforms/asap7/KLayout`, community `asap7.lydrc`); the research
note counts 33 items on gcd; nothing on this track runs it.

**What.**

1. New `learn/scripts/lab_asap7_drc.py`: runs KLayout in batch on a
   named `lab_asap7_*` GDS with the community deck, counts items
   per rule, writes `lab_asap7_drc.json` (gitignored) with
   `calibre: false`, `deck: "community laurentc2"`, `product_win:
   false`, and the honest note that several via-width rules are off
   and `OFFGRID = false`.
2. The runner invokes it on the default gcd TC finish and on the
   480 ps closed finish (two data points: smoke and closed).
3. The count is a **leftover-named observation**, never a gate: the
   run does not fail on nonzero DRC items, it fails only if KLayout
   itself cannot run the deck.

**Acceptance.** `lab_asap7_drc.json` exists after a full run with a
per-rule breakdown; suite hook (W10) shows the count with the
"community deck, not Calibre" label. No `.drc.ok` style stamp.

### 5.6 W6 — LVS attached to the folio

**Why.** `lab_asap7_lvs.py` works (~79% cell-vs-CDL) but is
orphaned: nothing records which finish it checked.

**What.**

1. Add `--variant` (same convention as W4) and stamp the checked
   variant + GDS sha into `lab_asap7_lvs.json`.
2. Runner behavior: when `cdl_ready()` is false, record a named GAP
   (`fetch extras…`) instead of skipping silently.
3. Keep every existing honesty invariant: `lvs_closed: false`,
   `calibre: false`, never `.lvs.ok`, match percentage reported as
   a leftover metric, not a pass.

**Acceptance.** Folio rows say `lvs: 79% cell-vs-CDL (not
Calibre)` or `lvs: GAP (CDL not fetched)` per checked finish.

### 5.7 W7 — Layer-1 passes in the run

**Why.** Inventory + Xyce inverter are the only transistor-level
truth this image can produce; they should be part of "all phases",
once per run, not a separate ritual.

**What.**

1. The runner ends with `run_lab_asap7_pdk.sh` semantics: fetch is
   **not** automatic; if `learn/lab/asap7/pdk/` is absent the folio
   records the named GAP with the fetch command. If present, run
   the inventory and the Xyce inverter and attach both reports.
2. No change to the scripts themselves; they already stamp
   `calibre_ready` / `calibre_ran` / `product_win: false` and the
   `level 72→107` patch name.

**Acceptance.** One command produces (or honestly GAPs) all four
layer-1 signals: PDK inventory, Calibre-gated flags, Xyce wave,
`n_model` count — same assertions `test_asap7_e2e.py` already has.

### 5.8 W8 — Timing closure ladder, recorded

**Why.** The 310 ps smoke SDC is open by construction (ORFS CI
allows WNS ≥ −32.2 on gcd); the honest story is the ladder
310 (open, smoke) → 430 (open, WNS −23) → 480 (closed, +5.38) and
`period_min_ps` / `fmax_ghz` per cook. Today the ladder lives in
`asap7_close_plan.md` prose only.

**What.**

1. The default plan (§6) includes the 430 ps and 480 ps gcd TC
   cooks, so the ladder is reproducible, not archaeological.
2. Folio gains `closure_ladder` per design: the list of
   (clk_ps, wns_ps, timing_closed) sorted by clock, derived from
   live rows only — no frozen numbers.
3. WC stays on its own budget: a WC entry is *not* required to
   close at 480 ps; its row reports `period_min_ps` honestly. If
   someone wants a closed WC, that is a new tagged cook
   (`LAB_CLK_PS` higher), not a rewrite of the TC ladder.
4. uart: keep 270 ps smoke; add one relaxed tagged cook chosen from
   live `period_min_ps` (ceil to 10 ps) so uart also demonstrates a
   closed finish. Same rule: new variant tag, never overwrite.

**Acceptance.** `lab_asap7_folio.json` shows, for gcd TC, at least
one open smoke row and one closed row, with `period_min_ps` and
`fmax_ghz` populated; same for uart after its relaxed cook.
`test_asap7_e2e.py` already asserts `timing_closed` on the 480 ps
row and "folio names a closed-timing cook" — keep both.

### 5.9 W9 — Guardrails and hygiene

**Why.** Small inconsistencies found in review; cheap to fix, and
they are exactly the kind of drift that erodes trust in the track.

**What.**

1. `flowlab_untouched()`: stop ignoring it. In `cook()`, when the
   locked Nangate GDS is missing, log a named warning into the
   payload (`nangate_lock_absent: true`) — do not abort (a fresh
   clone legitimately has no Nangate artifacts) but never `pass`
   silently. The write-path refusal (variant prefix + locked regex)
   remains the real guard.
2. Remove dead `CCS_OK` (W3.2).
3. `ok` semantics (W2.4).
4. Add to `test_asap7_lab.py`: wrapper refuses `LAB_CLK_PS` that
   would collide with a locked name (already impossible via
   `validate()`, assert it anyway); runner `--dry-run` emits no
   subprocess calls (mock `subprocess.run` and count).
5. Keep the two gold SHAs (`GOLD_IR_SHA`, `GOLD_GDS_SHA`,
   `GOLD_RPT_SHA`) asserted before **and** after any e2e session,
   as `test_asap7_e2e.py` does today — the runner must call
   `assert_nangate_gold_untouched()` at start and end too.

**Acceptance.** All named checks green in `test_asap7_lab.py`
without cooking; no silent `pass` left on the guard path.

### 5.10 W10 — Reporting: suite-status, Studio, docs

**Why.** The WORKS/FAIL/GAP table is the honesty contract of this
repo and it currently omits the entire ASAP7 track.

**What.**

1. `learn/reference/suite-status.md`: add an "ASAP7 (Lab)" section
   with one row per phase — cook (per design/corner), DRC
   (community), LVS (cell-vs-CDL %), MMMC pair, layer-1 inventory,
   Xyce inverter, 6-track (GAP), Calibre (GAP), FakeRAM (leftover
   forever). Status vocabulary unchanged (WORKS / WORKS* / FAIL /
   GAP / LOCKED); ASAP7 rows can never be LOCKED gold.
2. Studio: extend the `/lab#asap7` panel with the folio's
   per-phase verdicts and closure ladder; add suite hooks
   `asap7_cook`, `asap7_drc`, `asap7_lvs`, `asap7_mmmc` next to the
   existing `asap7_layer1` in `studio/src/lib/suite.ts`, each `ok`
   iff the gitignored report exists (same pattern as today's hook).
3. Docs: this plan is the index entry; `docs/lab.md` points here;
   `learn/lab/asap7/README.md` gains the runner as the first
   command. `docs/script.md` lists `run_asap7_e2e.py` and
   `lab_asap7_drc.py` when they land.
4. Map check: `test_dse_next.py` `_check_enterprise_docs` gains
   this file (exists, indexed, protects 45.298, refuses product
   win) — same pattern as the other three ASAP7 docs.

**Acceptance.** `GET /api/suite` exposes the ASAP7 hooks; the
suite-status table names every phase with an honest status; docs
map check passes.

### 5.11 W11 — 6-track platform (gated project, not this pass)

**Why.** `ASAP7_TRACK=6` is refused today and must stay refused
until someone builds a real second platform. Naming the work
precisely is part of consolidation; pretending it is a knob is not.

**What it would take** (from `asap7_close_plan.md` §5, expanded):
site definition for the 6T row height, `make_tracks` for the 6T
grid, tapcell/filler/tie cell lists from `asap7sc6t_26`, a PDN
config sized for the 6T rail pitch, a GDS layer map, KLayout layer
views, and its own smoke SDC — a parallel
`platforms/asap7_sc6t/`-style tree (kept out of git or in
`learn/lab/asap7/`, mirroring how other fetched views are
handled), never a patch of the 7.5T platform in place.

**Decision for this plan:** out of scope for e2e. The refuse
message stays; the folio records 6T as a named GAP. Revisit only
when a density study actually needs it.

---

## 6. Default plan order (cheap first, serial)

The runner's default spec list. One at a time; resume by skipping
live GDS. gcd is minutes-scale; nothing here is AES.

| # | Spec | Purpose |
|---|---|---|
| 1 | gcd TC RVT NLDM 7p5 (310 ps smoke) | baseline; open by design |
| 2 | gcd BC RVT NLDM | fast corner |
| 3 | gcd WC RVT NLDM (die default 40) | slow corner + CTS leftover exercised |
| 4 | gcd-ccs BC RVT CCS | CCS from the slim pack |
| 5 | gcd TC RVT CCS (needs extras; else named refuse) | CCS typical |
| 6 | gcd WC RVT CCS (needs extras; else named refuse) | CCS slow |
| 7 | gcd TC RVT+LVT NLDM | multi-VT |
| 8 | gcd TC RVT NLDM MBFF (`CLUSTER_FLOPS=1`) | `*_FAKE.lib` leftover exercised |
| 9 | gcd TC 430 ps | ladder: still open |
| 10 | gcd TC 480 ps | ladder: closed |
| 11 | uart TC (270 ps smoke; slang fallback) | second design |
| 12 | uart TC relaxed (from live `period_min`) | second closed finish |

Then, in order: DRC on #1 and #10; LVS on #10 (or named GAP);
MMMC pair on every closed row; layer-1 inventory + Xyce (or named
GAP); folio rewrite; gold-SHA re-assert.

`riscv32i-mock-sram` and `minimal` stay out of the default plan
(FakeRAM is not a gcd-scale e2e; `minimal` skips metrics) but
remain cookable via `--only`.

---

## 7. Definition of done for this plan

All of the following, verified live, none stamped as gold:

1. `python3 learn/scripts/run_asap7_e2e.py --dry-run` works on a
   fresh clone and prints the twelve-spec plan with live/refused
   status per spec.
2. On a toolchain machine starting from zero cooked ASAP7
   artifacts, one invocation of the runner (possibly across
   resumed sessions) produces: all cookable specs live, per-stage
   ledgers on every row, DRC/LVS/MMMC/layer-1 reports or named
   GAPs, and a folio with closure ladders.
3. `test_asap7_lab.py` passes with no cooked artifacts.
   `test_asap7_e2e.py` tier 1 passes with no cooked artifacts;
   tier 2 passes after the runner.
4. Nangate gold SHAs identical before and after the full session
   (`assert_nangate_gold_untouched()` at both ends).
5. `learn/reference/suite-status.md` has the ASAP7 section;
   `GET /api/suite` exposes the ASAP7 hooks; `/lab#asap7` shows
   per-phase verdicts.
6. No new tracked report under `learn/sim/reports/` (git ls-files
   check stays green); no frozen ASAP7 numbers anywhere in docs —
   live rows only.
7. Every leftover that cannot close on this image is still named,
   with its gate: Calibre (ASU tarball + 2017 license), foundry
   LVS, FakeRAM, LVT/SLVT CCS archives, 6-track platform, real
   SRAM compiler.

Anything less is progress, not done. Do not redefine done around
what happens to pass first.

---

## 8. Order of execution for the workstreams

1. **W9 + W2** (hygiene + stage ledger) — pure Python, testable
   synthetically, unblocks honest failure reporting for everything
   after.
2. **W1** (runner + two-tier test) — the backbone.
3. **W3, W8** (CCS story + ladder in the plan) — plan content.
4. **W4, W6, W7** (attach MMMC / LVS / layer-1 to the run).
5. **W5** (DRC wiring — the only genuinely new analysis script).
6. **W10** (suite-status, Studio hooks, docs, map check).
7. **W11** stays a named GAP.

Each lands as its own commit with its own test delta. Fast suite
rules apply: synthetic or gcd-scale; one `test_dse.py` at a time;
live cooks last and only one at a time.

---

## 9. What stays leftover forever (named, not hidden)

| Leftover | Why it never closes here |
|---|---|
| Calibre DRC/LVS/xACT | ASU encrypted tarball + Calibre 2017.3/4 license |
| Foundry signoff / tapeout | ASAP7 is predictive; not manufacturable |
| Real SRAM | FakeRAM2.0 by upstream design; OpenRAM has no ASAP7 port |
| Full CCS (all VT × corners) | archives exist upstream; LVT/SLVT stays refused until extracted |
| HSpice on `.pm` cards | no HSpice; Xyce patch path is the honest substitute |
| 6-track finish | second platform is a project (§5.11) |
| ASAP7 gold numbers | forbidden by design — live rows only |
| ASAP7 product win / course swap | forbidden (`AGENTS.md`, `asap7_research.md`) |

---

## 10. Fit to the three surfaces

Unchanged. Course and product stay Nangate45. Everything in this
plan is Lab. A fully green ASAP7 e2e run — twelve specs, four
analysis passes, honest folio — is still not a `win_rule.py` win,
still not comparable to gold Dynamic IR **45.298 mV**, and still
not a reason to touch `nangate45/gcd/flowlab`.

Sources: `docs/asap7_research.md`, `docs/asap7_close_plan.md`,
`docs/asap7_layer1_plan.md`, `learn/dse/asap7_lab.py`,
`scripts/run_lab_asap7.sh`, `learn/scripts/test_asap7_lab.py`,
`learn/scripts/test_asap7_e2e.py`, `learn/lab/asap7/README.md`,
ORFS `platforms/asap7` and `designs/asap7/*` in this tree.
