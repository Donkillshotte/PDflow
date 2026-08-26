# OpenROAD Physical Design Studio

Interfaccia web interattiva per il corso in `learn/`.
Non sostituisce gli script: li **orchestra** (check, fasi ORFS, progresso, materiali).

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

Oppure:

```bash
cd studio
npm install
npm run dev -- -H 127.0.0.1 -p 43217
```

## Cosa fa l’UI

| Area | Contenuto |
|---|---|
| Studio | Hero + progresso cliccabile + mappa del flusso guidato |
| Lezioni | **Wizard 5 passi**: teoria → LAB checklist → run live → risultati → chiusura |
| Strumenti | Toolchain + **console SSE** (log in diretta, annulla) + pannello artefatti |
| Materiali | Ricerca, documenti in-app, **galleria GUI** con lightbox |

Le azioni lunghe (`route`, `finish`) possono richiedere diversi minuti; l’output
appare in streaming. Il CLI resta invariato.