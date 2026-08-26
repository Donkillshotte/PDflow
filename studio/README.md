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
| **Flusso** | **FlowLab** RTL→GDSII: editor Monaco, parametri, signoff finish, storico run, VCD download |
| Lezioni | **Wizard 5 passi** con **gate hard** lato server (teoria, LAB ≥50%, run ok, artefatti, risultati) |
| Strumenti | Toolchain + Suite hub + **Ops** + console SSE (confirm/cancel/retry/export) + inspect/viewer |
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
- **Azioni estese**: `rtl_sim`, `gridcheck`, `activity_power`, `klayout_drc` (+ preflight artefatti)

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
| `POST /api/viewer` `{ stage }` | avvia OpenROAD Web Viewer |
| `GET /api/suite` | stato collaborativo di tutti gli hook |
| `GET/PUT /api/flowlab` | RTL + parametri FlowLab |
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
./scripts/test_studio_api.sh
```

Il CLI del corso resta invariato.
