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
| Studio | Hero + progresso cliccabile + mappa del flusso guidato |
| Lezioni | **Wizard 5 passi** con **gate hard** lato server (teoria, LAB ≥50%, run ok, artefatti, risultati) |
| Strumenti | Toolchain + **Ops dashboard** (pipeline, storico, lock) + console SSE (confirm/cancel/retry/export) |
| Materiali | Ricerca, documenti in-app, galleria GUI |

## Contratto operativo (enterprise)

- **Single-flight**: un solo job ORFS alla volta (`learn/.studio-run.lock`)
- **Dipendenze fase**: es. `place` richiede artefatti di `floorplan` (HTTP 412)
- **Conferma** per azioni lunghe: `cts`, `route`, `finish`
- **Cancel / retry / export log** dalla console e dallo storico
- **Job history**: `GET /api/jobs` → `learn/.studio-jobs.json`
- **Completamento lezione**: `POST /api/progress` → **422** se i gate falliscono

## API utili

| Endpoint | Ruolo |
|---|---|
| `GET /api/run/stream?action=` | SSE log + job |
| `POST /api/run/cancel` | SIGTERM sul job |
| `GET /api/jobs` | storico + pipeline + lock |
| `DELETE /api/jobs?force=1` | unlock forzato (lock stale) |
| `GET /api/progress?lessonId=` | progresso + gate |

Smoke API (server già avviato):

```bash
./scripts/test_studio_api.sh
```

Il CLI del corso resta invariato.
