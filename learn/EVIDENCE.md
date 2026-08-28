# Evidenza di verifica (corso)

Aggiornato durante il work goal autonomo. Non sostituisce lo studio: certifica che i **materiali e la pipeline** esistono e girano.

## Struttura (test automatico)

```bash
./scripts/test_course.sh
```

Esito atteso: `SMOKE PASSED`.

Copre: 8 lezioni × (README, LAB, run.sh) con profondità minima, 6 walkthrough Tcl,
atlante GUI + PNG Qt/canvas/heatmap, `golden-metrics.md`, workbook + `solutions.md`,
design tutorial, `--list`, `--check`, `--auto --lesson 00`, versioni tool.

## Pipeline ORFS variante `learn`

Eseguito sul design tutorial (`FLOW_VARIANT=learn`, `CORE_UTILIZATION=35`, SDC 0.46 ns):

- `make synth floorplan place cts route finish` → exit 0
- Artefatto: `flow/results/nangate45/gcd/learn/6_final.gds`
- Numeri: [golden-metrics.md](./reference/golden-metrics.md) — finish WNS −0.04,
  `period_min` 0.50 ns (~2.01 GHz) vs SDC 0.46 ns (~2.17 GHz). Exit 0 ≠ timing chiuso.

## GUI pixel-level

Screenshot Qt in `learn/reference/gui-shots/` più heatmap ORFS (`orfs_*.png`: clock tree, worst path, congestion, IR drop).

Guida: `learn/reference/gui-atlas.md` (sezioni 1–9).

## Signoff enterprise (Fase 1 + Fase 2)

Varianti `flowlab` (FlowLab) e `learn` (corso ORFS) condividono gli script in `learn/scripts/`.

```bash
# Dopo make finish sulla variante scelta
export FLOW_VARIANT=learn   # o flowlab

./learn/scripts/run_signoff_all.sh
SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh   # include thermal + PKG

# Valutazione gate vs golden-gcd.json
python3 learn/scripts/signoff_eval.py --variant "${FLOW_VARIANT}"
```

Report attesi in `learn/sim/reports/`:

| Report | Pilastro |
|---|---|
| `sta_signoff_{v}.json` | Timing |
| `drc_signoff_{v}.json` | Geometria |
| `lvs_signoff_{v}.json` | Equivalenza |
| `power_signoff_{v}.json` | Power / PKG |
| `signoff_all_{v}.json` | Orchestrator |
| `thermal_signoff_{v}.json` | Thermal proxy |
| `pkg_signoff_{v}.json` | Packaging |
| `signoff_phase2_{v}.json` | Fase 2 |

Matrice e DoD: [signoff-matrix.md](./reference/signoff-matrix.md).  
UI Studio: FlowLab fase **finish**, hub [/pkg](http://127.0.0.1:43217/pkg), `GET /api/signoff?variant=flowlab`.

Smoke automatico: `./scripts/test_all_phases.sh` (include hook signoff in `test_studio_api.sh`).

## Laboratorio visuale (FlowLab + lezioni)

Ogni fase PD mostra **layout reale**, non mockup decorativi:

| Superficie | Cosa vedi |
|---|---|
| `/flusso` (FlowLab) | Canvas centrale: ORFS PNG (`final_routing`, …) + **OpenROAD Web Viewer** iframe |
| `/flusso?phase=rtl` | Waveform **VCD reale** (`clk`, `reset`, handshake) da `GET /api/vcd-waveform` |
| `/lezioni/*/risultati` | Stesso canvas layout (variante `learn`) |
| `/strumenti?tab=results` | Layout preview sopra artefatti |

API: `GET /api/layout-preview?phase=route&variant=flowlab` · mapping ODB in `studio/src/lib/layoutPreview.ts`.

### Evidenza run `learn` (2026-08-28)

Dopo `6_final.*` presente in `flow/results/.../gcd/learn/`:

```bash
FLOW_VARIANT=learn SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh
```

| Pilastro | Esito | Summary |
|---|---|---|
| Timing | **PASS** | WNS −0.02 ns · TNS −0.14 · viol 3 |
| Geometria | **PASS** | Route DRC 0 · GDS DRC 0 |
| Equivalenza | **PASS** | LVS PASS · errors 0 |
| Power | **PASS** | Chip IR 6.34 mV · Sys droop 10.16 mV |
| Thermal proxy | **FAIL** (educational) | 62.86 mV > soglia 50 mV — interpretare proxy |
| PKG | **PASS** | bump + RDL + system_pdn ok |

Report: `learn/sim/reports/signoff_all_learn.json`. Fase 1 completa; thermal proxy segnala droop transient elevato sul run learn (valore didattico).

## Studio UI (wrapper grafico)

```bash
./scripts/run_studio.sh
# http://127.0.0.1:43217
```

Smoke: sezione `== Studio UI ==` in `./scripts/test_course.sh` (build Next.js).
API verificate: `/api/toolchain`, `/api/lessons`, `/api/run` action `check`.

## Audit requisiti goal

Vedi [AUDIT.md](./AUDIT.md).

## Cosa resta allo studente (non è un gap del repo)

- Compilare `mio-quaderno.md` e `mio-progetto-finale.md`
- Track sky130: estensione post-corso in CURRICULUM
