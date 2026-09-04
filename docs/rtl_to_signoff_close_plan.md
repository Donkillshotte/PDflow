# RTL-to-signoff close plan (suite integration)

Living action plan. **Plan only — not an implementation log.**
Not a frozen DSE plan. Do not fold this into `tpe_plan.md`,
`product.md`, `arch_review.md`, `next_iteration_plan.md`, `PLAN.md`,
`experiment_campaign_plan.md`, or `joint_recipe_plan.md`.

Campaign evidence: [`rtl_to_signoff.md`](rtl_to_signoff.md) ·
[`learn/reference/gaps.md`](../learn/reference/gaps.md) ·
[`learn/reference/suite-status.md`](../learn/reference/suite-status.md).

| Field | Value |
|---|---|
| Written | 2026-09-04 |
| Surface | Course / Studio suite only |
| This document | **Plan.** Do not treat it as a leftover-free close. |
| Physical leftover-free | **Out of scope.** Stopped. Do not resume. |

---

## 0. Decision law

“Conclude an unclosed item” has two meanings. Mixing them is the failure
mode of the last campaign.

| Kind | Conclude means | Who |
|---|---|---|
| **License / PDK / SDC gated** | Park it as a named leftover / GAP. `ok` stays true only when the real check ran. The leftover object stays on the report, the suite hook, and the tests. | This repo (naming + tests). A license, form, or different PDK if someone later wants the *physical* object. |
| **To-build suite drift** | Make the leftover visible and consistent on every suite surface. Fix stale copy. Add tests that fail on drift or a silent green. | This repo, next implementation goal. |
| **Already built** | Do not reopen. Tests already lock it. | — |

Success of a later implementation goal is **leftover-named suite
integrity**, not leftover-free silicon.

A later close is done when:

1. Every leftover in §1 has a stable `id`, a kind, a suite hook, a
   Studio surface, and a test needle.
2. `GET /api/suite` details are leftover-named (not “STA → DRC → LVS →
   power” while leftovers exist).
3. Locked `flowlab` and copy `eco_scratch` leftovers are both named
   without switching SignoffMatrix default to `eco_scratch`.
4. `test_dse_next.py`, `test_signoff_honesty.py`, and `test_eco.py` pass.
5. No gated leftover is marked closed. No invented `emlimit`, density
   rule, named ERC, slow/fast liberty, or rewritten course SDC.
6. Docs and suite tables use the same leftover phrases (no leftover
   column left as `—` when a leftover exists).

---

## 1. Leftover catalog (every unclosed item)

Authoritative live numbers stay in the JSON under
`learn/sim/reports/`. This table is the work queue.

### 1.1 Must park (gated). Do not physically close.

| id | Leftover | Why gated | Suite hook today | Conclude later |
|---|---|---|---|---|
| `setup_open_flowlab` | Locked `flowlab` WNS −0.02 · 16 viol · R2R VIOLATED | Locked variant. Do not overwrite `gcd/flowlab/`. | `sta_signoff` names leftover setup open. **Missing:** leftover no MCMM on the same hook. | Keep named. Dual-variant compare. Do not recook. |
| `setup_open_eco_io` | Copy WNS −0.01 on `resp_msg[14]` (course 20% output delay) | Tutorial SDC `clk_period` 0.46 · `clk_io_pct` 0.2. Shared NAND2_X2 `_647_`. | `eco` detail names I/O leftover. `signoff_all` hook does **not**. | Park as SDC leftover. EcoPanel already names the cone. |
| `must_connect_dff_x2` | LVS must-connect 2 on `DFF_X2` | Nangate split wells. Unpin / flatten failed. | `lvs_signoff` / `lvs_deep` name it. | Park. Do not flatten again. |
| `via_flatten` | `blank_circuit("VIA_*")` | Routing vias have no CDL. | Named in suite-status / LVS docs. Hook detail is thin. | Park. Mention on `lvs_signoff` detail. |
| `no_mcmm` | Single `typical.lib` | ORFS Nangate45 ships one corner. | Stamped on `signoff_all` JSON. **Suite `sta_signoff` / `signoff_all` details omit it.** | Park. Push into those hook details. |
| `no_density_erc` | Density / named ERC not in `FreePDK45.lydrc` | Deck has antenna 300:1 only. | Stamped on `signoff_all` JSON. **Suite `drc_signoff` / `klayout_drc` details omit it.** | Park. Push into those hook details. |
| `em_checked_0` | `em_checked` 0 | No foundry `emlimit`. | `vyges_em_ir` names `em_checked`. | Park. Keep. Do not invent a limit. |
| `ir_meshes_incomparable` | Gold / current_run / chip / vyges / system | Different extracts. | `power_signoff` detail is “chip IR + golden gate”. **Omits ledger.** | Park. Name `comparable: false` on the hook. |
| `no_ccs_official` | Official liberty is NLDM | Si2/Silvaco CCS is form-gated. Sidecar is re-char. | `ccs_char` is WORKS*. | Park. Official lib stays NLDM. |
| `no_starrc` | No StarRC / Raphael | Commercial. | Analysis hooks are OpenRCX / FasterCap. | Park as GAP. |
| `no_sparam` | Board S-parameter (Touchstone `.sNp`) | Form-gated. Lumped VRM→board→pkg only. | `system_pdn` leftover “no Touchstone”. | Park. Do not export the lump as `.sNp`. |
| `no_magic_netgen` | No FreePDK45 Magic `.tech` | Wrong tool / missing tech. | `magic_netgen` GAP. | Park. Keep GAP. |
| `no_sky130_course` | Course is Nangate45 | Different PDK. | `sky130` GAP. | Park. Do not mix. |
| `gold_ir_locked` | Dynamic IR gold **45.298 mV** | Forbidden restamp. | `dynamic_ir` uses current_run; gold locked. | Park as LOCKED. |
| `course_0_8` | Lessons 0/8 | Student pace. | Course progress LOCKED. | Park. Do not stamp `.progress.json`. |
| `aes_row_locked` | `memory_aes.jsonl` row `febe6804241c` | Product invariant. | Product / Lab table. | Park. Do not overwrite. |

### 1.2 Already built. Do not reopen.

| id | Item | Evidence |
|---|---|---|
| `lvs_match` | KLayout compare matches | `CONGRATULATIONS! Netlists match` · `.lvs.ok` only on that line |
| `eco_two_process` | SPEF size-up then BufferMove without SPEF | `run_eco.py` · RSZ-0074 if combined |
| `dse_proposer` | DSE never calls `signoff_all` | `learn/dse/flow_role.py` |
| `gap_class` | License vs to-build | `learn/reference/gaps.md` |
| `antenna_300` | Antenna in deck | `FreePDK45.lydrc` · `drc_deck_coverage.json` |
| `ir_ledger` | Meshes stamped, not mixed | `ir_mesh_ledger.py` |
| `ccs_sidecar` | 19 GCD combo cells | `ccs_char` WORKS* |

### 1.3 Failed physical closes. Do not retry.

| Attempt | Result |
|---|---|
| `ECO_PHASE=io` | Does not close I/O leftover |
| BUF_X1 → BUF_X4 on `output42` | Regresses R2R or stays −0.01 |
| RSZ `clone,split` | Cloned a NAND4, not `_647_` |
| Manual clone of `_647_` | Regresses R2R |
| I/O-only CLKBUF/BUF swaps on `output42` | Stays WNS −0.01 |
| LVS unpin / flatten-all / flat extract on DFF_X2 | Breaks match or raises leftover |

Default apply stays **two** OpenROAD processes. No third phase.

---

## 2. Suite integration gaps (the real to-build)

`GET /api/suite` is `ok` + a `detail` string
(`studio/src/lib/suite.ts`). Leftover lives in JSON
(`signoff_all_*.json`) and on finish / home, but several suite hooks
still look leftover-free.

| Hook | `ok` today | Detail today | Required leftover phrase |
|---|---|---|---|
| `sta_signoff` | true | leftover setup open | **also** leftover no MCMM (`typical.lib` only) |
| `drc_signoff` | true | `Route DRC + KLayout GDS · run_drc_signoff.sh` | antenna 300:1 · leftover no density / named ERC |
| `klayout_drc` | true | `run_klayout_drc.sh` | same deck leftover |
| `power_signoff` | true | `chip IR + golden gate` | IR meshes not comparable |
| `signoff_all` | true | `STA → DRC → LVS → power` | Compact leftover list (must-connect, setup open, no MCMM, no density/ERC, meshes) |
| `lvs_signoff` | true | leftover must-connect 2 | Keep. Add VIA flatten as leftover, not a fail. |
| `eco` | true | I/O leftover named | Keep. Do not change default variant. |
| `vyges_em_ir` | true | `em_checked 0` | Keep. |
| `dse` | true | proposer only | Keep. |

Studio surfaces that already name leftover (keep, then consume one
catalog):

- Home `GET /api/story` via `leftoverNamedBit()` in
  `studio/src/lib/story.ts`
- Finish EcoPanel + SignoffMatrix (`studio/src/lib/signoff.ts`)
- Variant compare: locked `flowlab` vs `eco_scratch`

Studio / docs drift to fix in the implementation goal (not now):

- `learn/reference/suite-status.md` §1 still says the remaining leftover
  is DFF_X2 only. Wrong. Must list setup / MCMM / deck / EM / meshes.
- Signoff-pillar leftover column: STA says “not PrimeTime”; DRC is `—`;
  `signoff_all` does not name leftovers.
- `period_min` golden in `signoff-matrix.md` is ≥ 0.50 ns; live
  `eco_scratch` is 0.46 ns and `flowlab` is 0.48 ns. Do **not** rewrite
  SDC. Document that the educational golden WNS ≥ −0.04 is the timing
  gate, and `period_min` on the copy is leftover-named vs the 0.50
  finish-era number.

---

## 3. Implementation phases (later goal — do not start here)

One heavy cook at a time. No AES finish. No recook of locked
`gcd/flowlab/`. Kill by PID only.

### Phase A — Leftover catalog (machine-readable)

Add `learn/signoff/leftover_catalog.json` (name may adjust) with one
object per `id` in §1.1–§1.2:

```
id, kind (gated|built|locked|forbidden_retry),
variant (flowlab|eco_scratch|both|n/a),
report_path + json pointer,
suite_hook_ids[],
studio_surfaces[],
detail_needle,
test_module
```

`stamp_signoff_all.py` and Studio leftover helpers read this catalog.
Do not hard-code a second phrase list in `leftoverNamedBit()`.

**Exit:** catalog ids ⊇ §1.1. A unit test fails if `gaps.md` or
`signoff_all_*.json` names a leftover the catalog lacks.

### Phase B — Suite hook details

In `studio/src/lib/suite.ts`:

1. Reuse `leftoverMcmmDetail`, `leftoverDeckCoverageDetail`,
   `leftoverSetupOpenDetail`, `leftoverMustConnectDetail` from
   `signoff.ts` (or catalog-backed equivalents).
2. Replace generic details on `drc_signoff`, `klayout_drc`,
   `power_signoff`, `signoff_all`.
3. Optional: add `leftover?: { ids: string[] }` on `HookStatus` so the
   Suite UI can render amber leftover chips without parsing prose.
4. Keep SignoffMatrix **default `flowlab`**. Add a read-only
   `eco_scratch` leftover strip (already on finish). Do not remap Run.

**Exit:** live `GET /api/suite` JSON contains every §1.1 needle that
belongs on a hook. No hook with `ok: true` and an empty leftover where
the catalog says gated.

### Phase C — Suite / docs tables

Update `learn/reference/suite-status.md` leftover columns and §1.
Point “Next honest closes” at this plan (suite integrity), not a sixth
physical close.

Keep `docs/rtl_to_signoff.md` as the campaign verdict. This file stays
the action plan. Do not rewrite frozen DSE plans.

**Exit:** leftover columns are not `—` when a leftover exists. Phrase
match vs catalog needles.

### Phase D — Tests (no leftover-free contract)

Extend existing suites. Do not invent a parallel test stack.

| Suite | Add |
|---|---|
| `test_signoff_honesty.py` | Every catalog `id` appears on the matching suite hook detail (or `leftover.ids`). `signoff_all` hook detail is leftover-named, not pillar-only. `drc_signoff` names leftover no density. `sta_signoff` names leftover no MCMM. |
| `test_eco.py` | Keep `setup_open is True` on the copy close. Refuse a third apply phase. |
| `test_dse_next.py` | Docs index cites this plan + `rtl_to_signoff.md`. No guillemets on new course pages. |
| Studio API (`scripts/test_studio_api.sh`) | `GET /api/suite` and `GET /api/story` leftover phrases match. |

Forbidden test outcomes:

- A test that requires WNS ≥ 0 at 0.46 ns.
- A test that requires `must_connect == 0`.
- A test that requires `em_checked > 0` or `mcmm: true`.
- A test that stamps course `8/8`.

### Phase E — Validation run (after implementation)

Order. Stop if any step fails. Do not recook `flowlab`.

```bash
# 1. Reports still match the catalog (no recook)
python3 - <<'PY'
# assert leftover ids vs signoff_all_flowlab.json + signoff_all_eco_scratch.json
PY

# 2. Honesty + ECO + DSE (fast)
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_signoff_honesty.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_eco.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py

# 3. Studio API against the running server (do not kill by name)
./scripts/test_studio_api.sh

# 4. Live suite
# GET /api/suite  and  GET /api/story
# Confirm leftover needles on sta / drc / lvs / power / signoff_all / eco / vyges
```

Manual Studio pass (when UI changes land): home leftover above the fold;
finish Signoff/ECO above GDS; compare `flowlab` vs `eco_scratch`; Suite
hub leftover chips; `/pkg` stays System PDN + Phase 2.

**Do not** launch AES finish “just to see”. **Do not** run TPE on spi @
1 ns.

### Phase F — Stop / audit

Mark the implementation goal complete only when §0 success criteria
are proven from live `GET /api/suite`, the three Python suites, and
the catalog-vs-JSON check. If any gated leftover was “closed” in copy,
fail the audit.

---

## 4. What this plan will not do

- Resume leftover-free RTL-to-signoff on Nangate45.
- Rewrite course SDC or overwrite `results/.../gcd/flowlab/`.
- Restamp gold Dynamic IR 45.298 mV.
- Invent `emlimit`, density rules, named ERC, or slow/fast liberty.
- Mix sky130 into the course.
- Add a third ECO apply phase or retry §1.3.
- Switch SignoffMatrix default to `eco_scratch` without remapping Run.
- Promote lab IR to a product win. No `if design ==` in tuner/space/score.
- Rewrite frozen DSE plans.
- Stamp course `8/8` or overwrite AES row `febe6804241c`.

---

## 5. Suggested later `/goal` (implementation)

When this plan is accepted, a new goal may implement Phases A–F in
order. That goal’s objective is leftover-named suite integrity, not
leftover-free silicon. Keep this file as the contract; update status
checkboxes only after evidence.

Phase order is A → B → C → D → E → F. Do not skip A (catalog) and
patch hook strings only: that is how home / finish / suite drifted
apart last time.
