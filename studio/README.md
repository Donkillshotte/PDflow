# OpenROAD Physical Design Studio

Interfaccia web **enterprise** per il corso in `learn/`.
Non sostituisce gli script: li **orchestra** con lock, dipendenze, storico job e gate di completamento.

## Avvio

Dalla root del repository:

```bash
./scripts/run_studio.sh
```

Apri [http://127.0.0.1:43217](http://127.0.0.1:43217).

Produzione:

```bash
./scripts/run_studio.sh --build
```

## Cosa fa l’UI

| Area | Contenuto |
|---|---|
| Studio | Hero + progresso + **Suite hub** (hook live) + mappa del flusso guidato |
| **Flusso** | **FlowLab** RTL→GDSII: editor Monaco, viewport layout (zoom/pan, confronti GRT↔DRT, filmstrip, HUD layer), signoff finish |
| Lezioni | **Wizard 5 passi** + **canvas layout** su step Risultati (variante `learn`) |
| Strumenti | Toolchain + Suite + Ops + console + **layout preview** + inspect/viewer |
| Materiali | Ricerca, documenti in-app, galleria GUI |

## Contratto operativo (enterprise)

- **Single-flight**: un solo job ORFS alla volta (`learn/.studio-run.lock`)
- **Dipendenze fase**: es. `place` richiede artefatti di `floorplan` (HTTP 412)
- **Conferma** per azioni lunghe: `cts`, `route`, `finish`
- **Cancel / retry / export log** dalla console e dallo storico
- **Job history**: `GET /api/jobs` → `learn/.studio-jobs.json`
- **Completamento lezione**: `POST /api/progress` → **422** se i gate falliscono
- **Apri GUI / dashboard**: palette **Ctrl+K**, deep-link `/strumenti?stage=cts&tab=results`,
  `POST /api/open` lancia OpenROAD/KLayout su Desktop (`DISPLAY`) o copia il comando;
  kind `run` → console; kind `webviewer` → `POST /api/viewer`
- **Ispezione tool**: `GET /api/inspect` (ODB via `-python`, OpenSTA JSON, Yosys `stat`)
- **Web Viewer**: `POST /api/viewer` → OpenROAD `-web` su porta `43190`
- **Suite hub**: `GET /api/suite` → matrice hook (ambiente → signoff) su `/` e `/strumenti#suite`
- **Azioni estese**: `rtl_sim`, `gridcheck`, `activity_power`, `vectorless`, `vyges_em_ir`, `dynamic_ir`, `yosys_equiv`, `formal_gcd`, `openrcx_report`, `klayout_drc` (+ preflight artefatti)

## API utili

| Endpoint | Ruolo |
|---|---|
| `GET /api/run/stream?action=` | SSE log + job |
| `POST /api/run/cancel` | SIGTERM sul job |
| `GET /api/jobs` | storico + pipeline + lock |
| `DELETE /api/jobs?force=1` | unlock forzato (lock stale) |
| `GET /api/progress?lessonId=` | progresso + gate |
| `GET /api/open` | catalogo dashboard + GUI targets |
| `POST /api/open` `{ id }` o `{ artifact }` | naviga o lancia OpenROAD/KLayout |
| `GET /api/inspect?stage=` | ODB / STA / Yosys live |
| `GET /api/layout-preview?phase=&variant=` | Metadata preview: PNG, gallery filmstrip, compare pairs, layer HUD |
| `GET /api/layout-preview/image?phase=` | Immagine primaria della fase |
| `GET /api/layout-preview/image?shot=` | Screenshot da `learn/reference/gui-shots/` (allowlist filename) |
| `GET /api/vcd-waveform` | Waveform RTL parsata da `gcd.vcd` |
| `POST /api/viewer` `{ stage, artifact? }` | OpenROAD `-web` (embedded in FlowLab) |
| `GET /api/suite` | stato collaborativo di tutti gli hook |
| `GET /api/signoff?variant=` | matrice 4 pilastri + gate vs golden-gcd |
| `GET/PUT /api/flowlab` | RTL + parametri FlowLab + sim + storico run |
| `GET /api/flowlab/download?kind=vcd\|simlog` | download waveform / sim.log |
| `GET /api/run/stream?mode=flowlab&action=` | run con override allowlistati |

Deep-link utili:

- `/flusso` — laboratorio RTL → GDSII
- `/strumenti?stage=place&tab=results`
- `/strumenti?stage=cts&tab=results#inspect`
- `/strumenti?tab=run&action=rtl_sim`
- `/strumenti?tab=run&action=gridcheck`
- `/strumenti#suite`
- `/strumenti?stage=finish&tab=run`
- `/materiali?tab=gallery`
- `/materiali/reference/tool-hooks.md`
- `/materiali/reference/extended-flow.md`
- `/materiali/reference/gui-atlas.md`


Smoke API (server già avviato):

```bash
./scripts/run_studio.sh          # http://127.0.0.1:43217
./scripts/test_all_phases.sh      # validazione esaustiva fasi corso + FlowLab + power chain
./scripts/test_studio_api.sh     # include FlowLab + variant flowlab
./scripts/test_course.sh         # pipeline learn
cd studio && npm run build
```

Il CLI del corso resta invariato.

## FlowLab (`/flusso`)

Workbench **RTL → GDSII** con variante isolata `results/nangate45/gcd/flowlab`:

1. **RTL** — editor Monaco, autosave, sim Icarus, waveform VCD con cursore/zoom
2. **Sintesi → GDSII** — viewport layout (rotella zoom, pan, Fit/`0`/`f`, Full/`F`), confronti Place↔Route e GRT↔DRT (wipe/split), filmstrip gui-shots, HUD layer Nangate45
3. **Console** — log SSE, artefatti, ispezione ODB/STA/Yosys; pulsante **Espandi chip** per nasconderla
4. **Finish signoff** — matrice STA/DRC/LVS/power, `signoff_all`, catena SPICE
5. **Storico** — ultimi job per fase da `/api/jobs`

Scorciatoie: `Ctrl+S` salva, `Ctrl+Enter` esegue fase.

Screenshot (UI corrente): `studio/docs/images/flowlab/`

## Troubleshooting ORFS / Studio

| Sintomo | Causa probabile | Azione |
|---|---|---|
| HTTP **412** su run | Artefatto fase precedente mancante | Completa la fase precedente o usa FlowLab in ordine |
| HTTP **409** locked | Job già in corso | Attendi o `DELETE /api/jobs?force=1` se stale |
| `iverilog` assente | Toolchain incompleta | `./scripts/learn_physical_design.sh --check` |
| GUI non si apre | Headless / no DISPLAY | Usa Web Viewer o copia comando da toast |
| FlowLab vs corso | Varianti diverse | Corso=`learn`, FlowLab=`flowlab` — non mischiare artefatti |
| Congestion / timing fail | Parametri aggressivi | Profilo «Didattico» o SDC relaxed in FlowLab |
| `make` lento su cts/route | Normale su GCD | Conferma dialog; un solo job alla volta |
| Terminale pieno di giallo/rosso | WARNING ORFS + false positive su `Failure: 0` | Digest in console: **0 ERROR** = flusso OK. Rumore tipico: `RSZ-0104`, `IFP-0028`, `GUI-0010`, `GRT-0246` |
| Badge rosso «N Issues» in basso | **Next.js DevTools** (solo `next dev`), non ORFS | Disabilitato in `next.config.ts`; in produzione (`next start`) non compare. ORFS = digest terminale |
| WNS −0.04 / setup violations | Golden nangate45 GCD | Atteso (vedi `golden-metrics.md`); non è un crash del wrapper |
| `RSZ-0062` Unable to repair | Timing residuale post-CTS/GRT | Atteso sul tutorial; rivedi solo se WNS << −0.15 |
| Fase PDN / PKG | Analisi power | **PDN** = chip gridcheck; **PKG** = System PDN gerarchico (ngspice VRM→board→pkg→die) · hub `/pkg` |

Log job: `learn/.studio-jobs.json` · lock: `learn/.studio-run.lock`
