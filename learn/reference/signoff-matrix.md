# GCD Nangate45 signoff matrix

Single source of truth for the **four pillars** of signoff on the educational GCD:
timing (STA), geometry (DRC), equivalence (LVS), power (IR). System PDN and
Phase 2 stay on `/pkg`.

TypeScript registry: `studio/src/lib/signoff.ts`  
Numeric thresholds: `learn/signoff/golden-gcd.json` (derived from [golden-metrics.md](./golden-metrics.md))  
Batch evaluation: `learn/scripts/signoff_eval.py`  
Studio API: `GET /api/signoff?variant=flowlab`

---

## Gate legend

| Result | Meaning |
|---|---|
| **PASS** | Metrics in the report JSON meet golden ± tolerance |
| **FAIL** | Threshold exceeded — interpret the report, not just the badge |
| **Missing** | Script not run after `finish` |

LVS is a KLayout compare on a prepared CDL (unused library cells dropped,
FILLCELL from DEF, wells mapped to VDD/VSS). A pass requires
`CONGRATULATIONS! Netlists match`. Must-connect warnings on DFF_X2 stay in
the lvsdb (Nangate split wells). This is educational FreePDK45, not foundry LVS.

---

## Lesson ↔ pillar ↔ tool ↔ artifact matrix

| Pillar | Lesson | Studio action | Script | Report JSON | Main gate |
|---|---|---|---|---|---|
| **Timing (STA)** | 07-finish | `sta_signoff` | `run_sta_signoff.sh` | `sim/reports/sta_signoff_{v}.json` | WNS/TNS/viol vs golden · leftover setup open if WNS < 0 (register or I/O) |
| **Timing (STA IR-aware)** | 07-finish | `sta_ir_aware` | `run_sta_ir_aware.sh` | `sim/reports/sta_ir_aware_{v}.json` | Educational NLDM × ITerm V (does not change WNS) |
| **Geometry (DRC)** | 06-routing, 07 | `drc_signoff` | `run_drc_signoff.sh` | `sim/reports/drc_signoff_{v}.json` | route DRC lines + GDS items |
| **Equivalence (LVS)** | 07-finish | `klayout_lvs` | `run_klayout_lvs.sh` | `sim/reports/lvs_signoff_{v}.json` | KLayout match + leftover named |
| **Power** | 03–07, finish | `power_signoff` | `run_power_signoff.sh` | `sim/reports/power_signoff_{v}.json` | chip IR vs golden |
| **Orchestrator** | 07 LAB | `signoff_all` | `run_signoff_all.sh` | `sim/reports/signoff_all_{v}.json` | all 4 pillars (+ optional Phase 2 with `SIGNOFF_INCLUDE_PHASE2=1`) |

Power sub-checks (inside `power` pillar):

| Check | Action | Artifact |
|---|---|---|
| Activity → power | `activity_power` | `activity_power_{v}.log` |
| Vectorless / dynamic | `vectorless` | `vectorless_{v}.json` |
| Chip IR mesh | `chip_pdn_ir` | `pdn_chip_ir_{v}.json` + `.chip_pdn_ir.ok` |
| vyges-em-ir | `vyges_em_ir` | `vyges_em_ir_{v}.json` + `.vyges_em_ir.ok` |
| Dynamic IR I(t) | `dynamic_ir` | `dynamic_ir_{v}_direct.json` + `.svg` + `.dynamic_ir.ok` (gold 45.298 stays `dynamic_ir_{v}.json`) |
| SPICE lab export | `export_spice_lab` | `sim/spice/INDEX_{v}.md` |

PKG (after four-pillar close, on `/pkg`):

| Check | Action | Artifact |
|---|---|---|
| System PDN | `system_pdn` | `system_pdn_{v}.json` + `.system_pdn.ok` |

---

## Dependencies (preflight)

All signoff actions require **`finish`** completed:

| Action | Minimum files |
|---|---|
| `sta_signoff` | `6_final.v` |
| `sta_ir_aware` | `6_final.v` + `sta_arrivals_{v}.json` + `dynamic_ir_{v}_direct.map.csv` (not gold) |
| `drc_signoff`, `klayout_lvs` | `6_final.gds` |
| `power_signoff`, `signoff_all` | `6_final.odb` |

---

## Golden thresholds (`golden-gcd.json`)

| Pillar | Metric | Target (learn ref) |
|---|---|---|
| Timing | WNS max | ≥ −0.04 ns (educational). WNS < 0 at 0.46 ns stays leftover setup open |
| Timing | TNS max | ≥ −0.6 |
| Timing | Setup violations | ≤ 45 |
| Timing | period_min | ≥ 0.50 ns |
| Geometry | Route DRC lines | 0 |
| Geometry | GDS DRC items | 0 |
| Equivalence | LVS | match (`CONGRATULATIONS`) · leftover must-connect 2 on DFF_X2 stays visible |
| Power | Chip static IR | ≤ 15 mV |
| Power | Chip transient droop | ≤ 120 mV |
| PKG | System droop | ≤ 20 mV |
| PKG | System Zmax | ≤ 15000 mΩ |

Tolerance: timing ±15%, power ±25%.

---

## Quick CLI

```bash
export FLOW_VARIANT=learn   # or flowlab

./learn/scripts/run_sta_signoff.sh
./learn/scripts/run_sta_ir_aware.sh   # optional overlay; needs dynamic_ir current_run
./learn/scripts/run_drc_signoff.sh
./learn/scripts/run_klayout_lvs.sh
./learn/scripts/run_power_signoff.sh
./learn/scripts/run_signoff_all.sh

# Optional Phase 2 (thermal + PKG) included in orchestrator:
SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh
```

---

## Definition of Done

Every pillar signoff is **complete** when all five artifacts exist:

| Artifact | Example |
|---|---|
| **Script** | `learn/scripts/run_*_signoff.sh` |
| **Report JSON** | `learn/sim/reports/*_signoff_{variant}.json` |
| **Golden gate** | evaluation in report (`evaluation.checks` vs `signoff/golden-gcd.json`) |
| **Test** | `scripts/test_all_phases.sh` · `scripts/test_studio_api.sh` |
| **Doc** | this matrix · lesson 07 LAB Part 7 · FlowLab finish |

Quick post-`finish` checklist:

- [ ] `sta_signoff` → WNS/TNS/viol vs golden
- [ ] (opt.) `sta_ir_aware` → slack vs slack_ir on the worst path (educational; not Tempus)
- [ ] `drc_signoff` → route DRC + GDS items = 0
- [ ] `klayout_lvs` → `CONGRATULATIONS` + leftover object (DFF_X2)
- [ ] `power_signoff` → chip IR vs golden · IR meshes not comparable
- [ ] `signoff_all` → 4 pillars ok · leftover + IR ledger named
- [ ] (opt.) Phase 2: `thermal_signoff`, `pkg_signoff`, `signoff_phase2`
- [ ] UI: matrix visible on FlowLab **finish** (`/flow?phase=finish`). `/pkg` is System PDN + Phase 2 only.
- [ ] Zero drift: `signoff.ts` ↔ `actions.ts` ↔ `run.ts` ↔ `jobs.ts` ↔ bash scripts

---

## Studio UI

| Surface | Content |
|---|---|
| FlowLab phase **finish** (`/flow?phase=finish`) | Four-pillar matrix, ECO, STA IR-aware, IR ledger, Dynamic IR heatmap |
| `/pkg` | System PDN + Phase 2 only (no matrix, no ECO) |
| `/product` | `win_rule` table (area / power / leakage / IR) |
| `/lab` | Physics ledger + DSE proposer |
| `/api/signoff` | JSON matrix + `evaluateSignoffGates()` |

Cross-ref: [extended-flow.md](./extended-flow.md) · [spice-power-chain.md](./spice-power-chain.md)

---

## Phase 2 (HotSpot + dummy RDL) {#phase-2-proxy}

Pillars in `signoff.ts` → `SIGNOFF_PLANNED_PILLARS`:

| Pillar | Action | Script | Status |
|---|---|---|---|
| **Packaging** | `pkg_signoff` | `run_pkg_bump.sh`, `run_pkg_rdl.sh` | **active** (educational) — bump + system PDN + dummy `rdl_route` on a sidecar ODB (`ok` only if `rdl.executed`). Dummy bump is not C4. |
| **Thermal** | `thermal_signoff` | `run_thermal_signoff.sh` (UVA HotSpot °C) | **active** (architecture compact model) — `t_max_c`; IR+droop kept as a secondary check. Not Ansys / not foundry. |

`pkg_rdl` `ok: true` requires `rdl.executed` and wires on the sidecar. Dummy bump LEF is not C4.

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_pkg_signoff.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_thermal_signoff.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_signoff_phase2.sh
```
