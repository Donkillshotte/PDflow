# GCD Nangate45 signoff matrix

Single source of truth for the **four pillars** of enterprise signoff on the educational GCD:
timing (STA), geometry (DRC), equivalence (LVS), power/PKG integrity.

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

On educational FreePDK45, **LVS may FAIL** even with a correct flow: the educational value is the process and interpreting `.lvsdb`; do not pretend tapeout-clean.

---

## Lesson ↔ pillar ↔ tool ↔ artifact matrix

| Pillar | Lesson | Studio action | Script | Report JSON | Main gate |
|---|---|---|---|---|---|
| **Timing (STA)** | 07-finish | `sta_signoff` | `run_sta_signoff.sh` | `sim/reports/sta_signoff_{v}.json` | WNS/TNS/viol vs golden |
| **Geometry (DRC)** | 06-routing, 07 | `drc_signoff` | `run_drc_signoff.sh` | `sim/reports/drc_signoff_{v}.json` | route DRC lines + GDS items |
| **Equivalence (LVS)** | 07-finish | `klayout_lvs` | `run_klayout_lvs.sh` | `sim/reports/lvs_signoff_{v}.json` | LVS clean (educational) |
| **Power / PKG** | 03–07, PKG hub | `power_signoff` | `run_power_signoff.sh` | `sim/reports/power_signoff_{v}.json` | IR/droop/Zmax vs golden |
| **Orchestrator** | 07 LAB | `signoff_all` | `run_signoff_all.sh` | `sim/reports/signoff_all_{v}.json` | all 4 pillars (+ optional Phase 2 with `SIGNOFF_INCLUDE_PHASE2=1`) |

Power sub-checks (inside `power` pillar):

| Check | Action | Artifact |
|---|---|---|
| Activity → power | `activity_power` | `activity_power_{v}.log` |
| Vectorless / dynamic | `vectorless` | `vectorless_{v}.json` |
| Chip IR mesh | `chip_pdn_ir` | `pdn_chip_ir_{v}.json` + `.chip_pdn_ir.ok` |
| vyges-em-ir | `vyges_em_ir` | `vyges_em_ir_{v}.json` + `.vyges_em_ir.ok` |
| Dynamic IR I(t) | `dynamic_ir` | `dynamic_ir_{v}.json` + `.svg` + `.dynamic_ir.ok` |
| System PDN | `system_pdn` | `system_pdn_{v}.json` + `.system_pdn.ok` |
| SPICE lab export | `export_spice_lab` | `sim/spice/INDEX_{v}.md` |

---

## Dependencies (preflight)

All signoff actions require **`finish`** completed:

| Action | Minimum files |
|---|---|
| `sta_signoff` | `6_final.v` |
| `drc_signoff`, `klayout_lvs` | `6_final.gds` |
| `power_signoff`, `signoff_all` | `6_final.odb` |

---

## Golden thresholds (`golden-gcd.json`)

| Pillar | Metric | Target (learn ref) |
|---|---|---|
| Timing | WNS max | ≥ −0.04 ns |
| Timing | TNS max | ≥ −0.6 |
| Timing | Setup violations | ≤ 45 |
| Timing | period_min | ≥ 0.50 ns |
| Geometry | Route DRC lines | 0 |
| Geometry | GDS DRC items | 0 |
| Equivalence | LVS | clean (interpret report) |
| Power | Chip static IR | ≤ 15 mV |
| Power | Chip transient droop | ≤ 120 mV |
| Power | System droop | ≤ 20 mV |
| Power | System Zmax | ≤ 15000 mΩ |

Tolerance: timing ±15%, power ±25%.

---

## Quick CLI

```bash
export FLOW_VARIANT=learn   # or flowlab

./learn/scripts/run_sta_signoff.sh
./learn/scripts/run_drc_signoff.sh
./learn/scripts/run_klayout_lvs.sh
./learn/scripts/run_power_signoff.sh
./learn/scripts/run_signoff_all.sh

# Optional Phase 2 (thermal + PKG) included in orchestrator:
SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh
```

---

## Definition of Done (enterprise deliverable)

Every pillar signoff is **complete** when all five artifacts exist:

| Artifact | Example |
|---|---|
| **Script** | `learn/scripts/run_*_signoff.sh` |
| **Report JSON** | `learn/sim/reports/*_signoff_{variant}.json` |
| **Golden gate** | evaluation in report (`evaluation.checks` vs `signoff/golden-gcd.json`) |
| **Test** | `scripts/test_all_phases.sh` · `scripts/test_studio_api.sh` |
| **Doc** | this matrix · lesson 07 LAB Part 7 · FlowLab finish/PKG |

Quick post-`finish` checklist:

- [ ] `sta_signoff` → WNS/TNS/viol vs golden
- [ ] `drc_signoff` → route DRC + GDS items = 0
- [ ] `klayout_lvs` → `.lvsdb` report interpreted (educational)
- [ ] `power_signoff` → IR/droop/system vs golden
- [ ] `signoff_all` → aggregated 4 pillars ok
- [ ] (opt.) Phase 2: `thermal_signoff`, `pkg_signoff`, `signoff_phase2`
- [ ] UI: matrix visible on FlowLab **finish** and **/pkg** hub
- [ ] Zero drift: `signoff.ts` ↔ `actions.ts` ↔ `run.ts` ↔ `jobs.ts` ↔ bash scripts

---

## Studio UI

| Surface | Content |
|---|---|
| FlowLab phase **finish** | 4-pillar matrix + STA/DRC/LVS actions |
| FlowLab phase **PKG** / [`/pkg`](/pkg) | Full matrix + power chain |
| `/api/signoff` | JSON matrix + `evaluateSignoffGates()` |

Cross-ref: [extended-flow.md](./extended-flow.md) · [spice-power-chain.md](./spice-power-chain.md)

---

## Phase 2 (planned in registry) {#phase-2-planned-in-registry}

Pillars prepared in `signoff.ts` → `SIGNOFF_PLANNED_PILLARS`:

| Pillar | Action (future) | Script | Status |
|---|---|---|---|
| **Packaging** | `pkg_signoff` | `run_pkg_bump.sh`, `run_pkg_rdl.sh` | READY (educational) |
| **Thermal** | `thermal_signoff` | `run_thermal_signoff.sh` (IR+droop proxy) | proxy READY |

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_pkg_signoff.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_thermal_signoff.sh
```
