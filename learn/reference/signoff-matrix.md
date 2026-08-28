# Matrice signoff GCD Nangate45

Single source of truth per i **4 pilastri** del signoff enterprise sul GCD educativo:
timing (STA), geometria (DRC), equivalenza (LVS), integrità power/PKG.

Registry TypeScript: `studio/src/lib/signoff.ts`  
Soglie numeriche: `learn/signoff/golden-gcd.json` (derivato da [golden-metrics.md](./golden-metrics.md))  
Valutazione batch: `learn/scripts/signoff_eval.py`  
API Studio: `GET /api/signoff?variant=flowlab`

---

## Legenda gate

| Esito | Significato |
|---|---|
| **PASS** | Metriche nel report JSON rispettano golden ± tolleranza |
| **FAIL** | Soglia superata — interpretare il report, non solo il badge |
| **Assente** | Script non eseguito dopo `finish` |

Su FreePDK45 educativo, **LVS può FAIL** anche con flow corretto: il valore didattico è il processo e l’interpretazione del `.lvsdb`, non fingere tapeout-clean.

---

## Matrice lezione ↔ pilastro ↔ tool ↔ artefatto

| Pilastro | Lezione | Studio action | Script | Report JSON | Gate principale |
|---|---|---|---|---|---|
| **Timing (STA)** | 07-finish | `sta_signoff` | `run_sta_signoff.sh` | `sim/reports/sta_signoff_{v}.json` | WNS/TNS/viol vs golden |
| **Geometria (DRC)** | 06-routing, 07 | `drc_signoff` | `run_drc_signoff.sh` | `sim/reports/drc_signoff_{v}.json` | route DRC lines + GDS items |
| **Equivalenza (LVS)** | 07-finish | `klayout_lvs` | `run_klayout_lvs.sh` | `sim/reports/lvs_signoff_{v}.json` | LVS clean (educational) |
| **Power / PKG** | 03–07, PKG hub | `power_signoff` | `run_power_signoff.sh` | `sim/reports/power_signoff_{v}.json` | IR/droop/Zmax vs golden |
| **Orchestrator** | 07 LAB | `signoff_all` | `run_signoff_all.sh` | `sim/reports/signoff_all_{v}.json` | tutti e 4 i pilastri (+ opz. Fase 2 con `SIGNOFF_INCLUDE_PHASE2=1`) |

Sub-check power (dentro pilastro `power`):

| Check | Action | Artefatto |
|---|---|---|
| Activity → power | `activity_power` | `activity_power_{v}.log` |
| Chip IR mesh | `chip_pdn_ir` | `pdn_chip_ir_{v}.json` + `.chip_pdn_ir.ok` |
| System PDN | `system_pdn` | `system_pdn_{v}.json` + `.system_pdn.ok` |
| SPICE lab export | `export_spice_lab` | `sim/spice/INDEX_{v}.md` |

---

## Dipendenze (preflight)

Tutte le azioni signoff richiedono **`finish`** completato:

| Action | File minimo |
|---|---|
| `sta_signoff` | `6_final.v` |
| `drc_signoff`, `klayout_lvs` | `6_final.gds` |
| `power_signoff`, `signoff_all` | `6_final.odb` |

---

## Golden thresholds (`golden-gcd.json`)

| Pilastro | Metrica | Target (learn ref) |
|---|---|---|
| Timing | WNS max | ≥ −0.04 ns |
| Timing | TNS max | ≥ −0.6 |
| Timing | Setup violations | ≤ 45 |
| Timing | period_min | ≥ 0.50 ns |
| Geometry | Route DRC lines | 0 |
| Geometry | GDS DRC items | 0 |
| Equivalence | LVS | clean (interpretare report) |
| Power | Chip static IR | ≤ 15 mV |
| Power | Chip transient droop | ≤ 120 mV |
| Power | System droop | ≤ 20 mV |
| Power | System Zmax | ≤ 15000 mΩ |

Tolleranza: timing ±15%, power ±25%.

---

## CLI rapida

```bash
export FLOW_VARIANT=learn   # o flowlab

./learn/scripts/run_sta_signoff.sh
./learn/scripts/run_drc_signoff.sh
./learn/scripts/run_klayout_lvs.sh
./learn/scripts/run_power_signoff.sh
./learn/scripts/run_signoff_all.sh

# Opzionale Fase 2 (thermal + PKG) inclusa nell'orchestrator:
SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh
```

---

## Definition of Done (deliverable enterprise)

Ogni pilastro signoff è **completo** quando esistono tutti e cinque gli artefatti:

| Artefatto | Esempio |
|---|---|
| **Script** | `learn/scripts/run_*_signoff.sh` |
| **Report JSON** | `learn/sim/reports/*_signoff_{variant}.json` |
| **Gate golden** | valutazione in report (`evaluation.checks` vs `signoff/golden-gcd.json`) |
| **Test** | `scripts/test_all_phases.sh` · `scripts/test_studio_api.sh` |
| **Doc** | questa matrice · lezione 07 LAB Parte 7 · FlowLab finish/PKG |

Checklist rapida post-`finish`:

- [ ] `sta_signoff` → WNS/TNS/viol vs golden
- [ ] `drc_signoff` → route DRC + GDS items = 0
- [ ] `klayout_lvs` → report `.lvsdb` interpretato (educational)
- [ ] `power_signoff` → IR/droop/system vs golden
- [ ] `signoff_all` → aggregato 4 pilastri ok
- [ ] (opz.) Fase 2: `thermal_signoff`, `pkg_signoff`, `signoff_phase2`
- [ ] UI: matrice visibile su FlowLab **finish** e hub **/pkg**
- [ ] Zero drift: `signoff.ts` ↔ `actions.ts` ↔ `run.ts` ↔ `jobs.ts` ↔ script bash

---

## UI Studio

| Superficie | Contenuto |
|---|---|
| FlowLab fase **finish** | Matrice 4 pilastri + azioni STA/DRC/LVS |
| FlowLab fase **PKG** / [`/pkg`](/pkg) | Matrice completa + catena power |
| `/api/signoff` | JSON matrice + `evaluateSignoffGates()` |

Cross-ref: [extended-flow.md](./extended-flow.md) · [spice-power-chain.md](./spice-power-chain.md)

---

## Fase 2 (planned in registry)

Pilastri predisposti in `signoff.ts` → `SIGNOFF_PLANNED_PILLARS`:

| Pilastro | Action (future) | Script | Stato |
|---|---|---|---|
| **Packaging** | `pkg_signoff` | `run_pkg_bump.sh`, `run_pkg_rdl.sh` | READY (educational) |
| **Thermal** | `thermal_signoff` | `run_thermal_signoff.sh` (proxy IR+droop) | proxy READY |

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_pkg_signoff.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_thermal_signoff.sh
```
