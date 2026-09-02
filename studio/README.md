# OpenROAD Physical Design Studio

**Enterprise** web interface for the course in `learn/`.
It does not replace the scripts: it **orchestrates** them with locks, dependencies, job history, and completion gates.

Repo index: [`docs/README.md`](../docs/README.md) · course: [`docs/course.md`](../docs/course.md).
The `learn` and `flowlab` variants are locked for the product.

## Getting started

From the repository root:

```bash
./scripts/run_studio.sh
```

Open [http://127.0.0.1:43217](http://127.0.0.1:43217).

Production:

```bash
./scripts/run_studio.sh --build
```

## What the UI does

| Area | Content |
|---|---|
| Studio | Unified path (`/#story`, `GET /api/story`) + progress + **Suite hub** + flow map |
| **Flow** | **FlowLab** RTL→GDSII: Monaco editor, layout viewport (zoom/pan, GRT↔DRT comparisons, filmstrip, layer HUD), finish signoff |
| Lessons | **5-step wizard** + **layout canvas** on Results step (`learn` variant) |
| Tools | Toolchain + Suite + Ops + console + **layout preview** + inspect/viewer |
| Materials | Search, in-app documents, GUI gallery |

## Operational contract (enterprise)

- **Single-flight**: one ORFS job at a time (`learn/.studio-run.lock`)
- **Phase dependencies**: e.g. `place` requires `floorplan` artifacts (HTTP 412)
- **Confirmation** for long actions: `cts`, `route`, `finish`
- **Cancel / retry / export log** from the console and history
- **Job history**: `GET /api/jobs` → `learn/.studio-jobs.json`
- **Lesson completion**: `POST /api/progress` → **422** if gates fail
- **Open GUI / dashboard**: palette **Ctrl+K**, deep-link `/tools?stage=cts&tab=results`,
  `POST /api/open` launches OpenROAD/KLayout on Desktop (`DISPLAY`) or copies the command;
  kind `run` → console; kind `webviewer` → `POST /api/viewer`
- **Tool inspection**: `GET /api/inspect` (ODB via `-python`, OpenSTA JSON, Yosys `stat`)
- **Web Viewer**: `POST /api/viewer` → OpenROAD `-web` on port `43190`
- **Suite hub**: `GET /api/suite` → hook matrix (environment → signoff) on `/` and `/tools#suite`
- **Extended actions**: `rtl_sim`, `gridcheck`, `activity_power`, `vectorless`, `vyges_em_ir`, `dynamic_ir`, `yosys_equiv`, `formal_gcd`, `openrcx_report`, `klayout_drc` (+ artifact preflight)

## Useful APIs

| Endpoint | Role |
|---|---|
| `GET /api/run/stream?action=` | SSE log + job |
| `POST /api/run/cancel` | SIGTERM on job |
| `GET /api/jobs` | history + pipeline + lock |
| `DELETE /api/jobs?force=1` | forced unlock (stale lock) |
| `GET /api/progress?lessonId=` | progress + gates |
| `GET /api/open` | dashboard + GUI target catalog |
| `POST /api/open` `{ id }` or `{ artifact }` | navigate or launch OpenROAD/KLayout |
| `GET /api/inspect?stage=` | ODB / STA / Yosys live |
| `GET /api/layout-preview?phase=&variant=` | Preview metadata: PNG, gallery filmstrip, compare pairs, layer HUD |
| `GET /api/layout-preview/image?phase=` | Primary phase image |
| `GET /api/layout-preview/image?shot=` | Screenshot from `learn/reference/gui-shots/` (allowlist filename) |
| `GET /api/vcd-waveform` | RTL waveform parsed from `gcd.vcd` |
| `POST /api/viewer` `{ stage, artifact? }` | OpenROAD `-web` (embedded in FlowLab) |
| `GET /api/suite` | collaborative state of all hooks |
| `GET /api/signoff?variant=` | 4-pillar matrix + gates vs golden-gcd |
| `GET/PUT /api/flowlab` | RTL + FlowLab params + sim + run history |
| `GET /api/flowlab/download?kind=vcd\|simlog` | download waveform / sim.log |
| `GET /api/run/stream?mode=flowlab&action=` | run with allowlisted overrides |

Useful deep links:

- `/flow` — RTL → GDSII lab
- `/tools?stage=place&tab=results`
- `/tools?stage=cts&tab=results#inspect`
- `/tools?tab=run&action=rtl_sim`
- `/tools?tab=run&action=gridcheck`
- `/tools#suite`
- `/tools?stage=finish&tab=run`
- `/materials?tab=gallery`
- `/materials/reference/tool-hooks.md`
- `/materials/reference/extended-flow.md`
- `/materials/reference/gui-atlas.md`


API smoke tests (server already running):

```bash
./scripts/run_studio.sh          # http://127.0.0.1:43217
./scripts/test_all_phases.sh      # exhaustive validation of course phases + FlowLab + power chain
./scripts/test_studio_api.sh     # includes FlowLab + variant flowlab
./scripts/test_course.sh         # learn pipeline
cd studio && npm run build
```

The course CLI is unchanged.

## FlowLab (`/flow`)

**RTL → GDSII** workbench with isolated variant `results/nangate45/gcd/flowlab`:

1. **RTL** — Monaco editor, autosave, Icarus sim, VCD waveform with cursor/zoom
2. **Synthesis → GDSII** — layout viewport (wheel zoom, pan, Fit/`0`/`f`, Full/`F`), Place↔Route and GRT↔DRT comparisons (wipe/split), gui-shots filmstrip, Nangate45 layer HUD
3. **Console** — SSE log, artifacts, ODB/STA/Yosys inspection; **Expand chip** button to hide it
4. **Finish signoff** — STA/DRC/LVS/power matrix, `signoff_all`, SPICE chain
5. **History** — latest jobs per phase from `/api/jobs`

Shortcuts: `Ctrl+S` save, `Ctrl+Enter` run phase.

Screenshots (current UI): `studio/docs/images/flowlab/`

## ORFS / Studio troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| HTTP **412** on run | Missing previous-phase artifact | Complete the previous phase or use FlowLab in order |
| HTTP **409** locked | Job already running | Wait or `DELETE /api/jobs?force=1` if stale |
| `iverilog` missing | Incomplete toolchain | `./scripts/learn_physical_design.sh --check` |
| GUI won't open | Headless / no DISPLAY | Use Web Viewer or copy command from toast |
| FlowLab vs course | Different variants | Course=`learn`, FlowLab=`flowlab` — do not mix artifacts |
| Congestion / timing fail | Aggressive parameters | «Didactic» profile or relaxed SDC in FlowLab |
| Slow `make` on cts/route | Normal on GCD | Confirm dialog; one job at a time |
| Terminal full of yellow/red | ORFS WARNING + false positive on `Failure: 0` | Console digest: **0 ERROR** = flow OK. Typical noise: `RSZ-0104`, `IFP-0028`, `GUI-0010`, `GRT-0246` |
| Red «N Issues» badge at bottom | **Next.js DevTools** (`next dev` only), not ORFS | Disabled in `next.config.ts`; not shown in production (`next start`). ORFS = terminal digest |
| WNS −0.04 / setup violations | Golden nangate45 GCD | Expected (see `golden-metrics.md`); not a wrapper crash |
| `RSZ-0062` Unable to repair | Residual timing post-CTS/GRT | Expected on tutorial; review only if WNS << −0.15 |
| PDN / PKG phase | Power analysis | **PDN** = chip gridcheck; **PKG** = hierarchical System PDN (ngspice VRM→board→pkg→die) · hub `/pkg` |

Job log: `learn/.studio-jobs.json` · lock: `learn/.studio-run.lock`
