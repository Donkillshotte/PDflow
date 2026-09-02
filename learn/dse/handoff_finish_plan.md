# Plan: full cook of DSE winners vs standard finish

Objective: after DSE search, **cook the full dish** with the
chosen recipes and compare to today's ORFS finish. Same exam,
same oven. Not another DSE round.

Plan language: what we do, in what order, how we decide if it
won. File details are at the end.

## Why

Today we compare tastings (DSE) with a served dish (`make finish`).
That is the wrong question for “are we better?”. The right question is:
**same full flow, only the netlist changes**.

## What this plan is NOT

- Do not launch `make finish` from inside the DSE controller on every try.
- Do not touch the `flowlab` finish already on disk (gold 45.298, current-run 6.075).
- No AES, no Krylov, no restamping gold.
- Do not stitch v1 “piece-only” changes (cone ABC): not a file ORFS
  ingests on its own.
- Do not declare win on different power meshes.

## Three cooks, not twenty

Only one thing changes: **the input netlist**. Clock, utilization,
density, PDN strategy: **identical** to baseline. Otherwise we compare
chip floorplan, not the DSE recipe.

| Cook | Who | DSE netlist (id) | What it tests |
|---|---|---|---|
| A — baseline | Finish `flowlab` already done | standard ORFS Yosys+ABC | Today's dish. Do not relaunch. |
| B — small | New ORFS variant | `54142494d890` `sub_twos_complement` (~407 µm² mapped, 257 cells) | The smallest shape. |
| C — fast | New ORFS variant | `52e0ecacb19b` `orfs_abc_speed` (~619 µm² mapped, 408 cells) | The fastest logic on paper. |

Decoupling caps on the supply: **not** a fourth place/route
cook. On baseline it is already measured (6.075 → 4.156 mV, same graph).
After B and C, if new finishes exist, repeat **only** that
measurement on the new extracts. Phase 2, non-blocking.

## How we decide if it won

Before cooks, criteria (same `6_report.json` file):

1. **On time** — finish WNS and TNS. “Better” = less delay, or same
   timing with **fewer repair instances**.
2. **How big** — finish stdcell area and instance count. “Better”
   = smaller at non-worse timing.
3. **Power delivery** — voltage drop on the **same type** of extract
   (DirectLU, not another mesh). Phase 2.
4. **Cost** — how many repair buffers ORFS inserted.

Possible outcomes, all honest:

- **Product win:** B or C beats A on timing *or* on area at equal timing.
- **Tie:** ORFS reinserts the same buffers, the three dishes look
  alike. Search was useful, the dish was not.
- **Regression:** B or C worsens timing or area. Keep A.

GCD is small: deltas can be tiny. A tie **is not**
plan failure; it is an answer.

## Phases

### 0 — Baseline freeze

Copy aside (not in live `flowlab/` tree) A numbers:
WNS, TNS, area, repair count, power, util, DirectLU IR.

Do not relaunch A. Do not overwrite `results/.../gcd/flowlab/`.

### 1 — Pick files, not slogans

Verify on disk that both DSE `.v` exist, are `module gcd`,
pass quick equiv vs RTL (B) / vs flatten (C if applicable).

If a file is missing (netlist is gitignored): **regenerate only that F1**,
not a campaign.

### 2 — Isolated oven

New ORFS `FLOW_VARIANT`s, e.g. `flowlab_dse_small` and `flowlab_dse_fast`.
Logs/results separate from `flowlab`.

Trick: skip Yosys. The DSE netlist **is already** gate-level. Place it
as `1_2_yosys.v` (or ORFS equivalent) and start from floorplan.
Same `constraint.sdc`, same `CORE_UTILIZATION` as baseline
(live finish ≈ 55%, not 35% from DSE GPL trials).

One heavy job at a time. Memory cap as for the rest of the VM.

### 3 — Cook B, then C

Serial. For each: `make finish` → same `6_report.json`.

If a cook crashes (legalize, antenna, DRT): record failure.
Do not “fix the recipe” silently: that would be DSE again.

### 4 — Single table

Same columns for A, B, C:

- WNS / TNS setup
- stdcell area and n. instances
- n. repair buffers and clock buffers
- power / leakage
- util
- (phase 2) DirectLU IR on *that* finish extract

No mapped 407 vs finish 940. No F5-lite vs finish.

### 5 — Decision and stop

Write three lines: B won, C won, nobody, or A stays the dish.
Only then discuss whether cone ABC stitching or handoff in the
controller is worth it.

## Out of v1 (explicit)

| Request | Why later |
|---|---|
| ABC only on data path (`boils_balance`) | Must be stitched into chip; not drop-in. |
| Cell size-up / net buffer DSE | ORFS repair redoes it; would confuse signal. |
| Catalog IR 1.705 / leftover 3.94 | Different mesh. |
| AES | Out of VM budget; not this comparison. |
| `make finish` in DSE loop | Costs and mixes categories. |

## Work order (when implementing)

1. Isolated script/variant + dry test: “this `.v` enters floorplan”. **done**
2. Finish B. **done** (`flowlab_dse_small`, WNS −338 ps)
3. Finish C. **done** (`flowlab_dse_fast`, WNS −187 ps)
4. Table and verdict in write-up next to `flow_vs_orfs_gcd.md`. **done**
   (`handoff_finish_bakeoff.md`: A stays)
5. Phase 2 IR only if B/C were born. **skipped** (different dies; PSM ≠ DirectLU)

No controller code: the GCD verdict does not justify the loop.
