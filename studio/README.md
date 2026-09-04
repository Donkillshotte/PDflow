# Studio

Next.js UI for the course and FlowLab. It launches the same scripts as
the CLI (`learn/scripts/`). It does not decide product wins.

Index: [`docs/README.md`](../docs/README.md) · course: [`docs/course.md`](../docs/course.md).
`FLOW_VARIANT` in `{learn, flowlab, base}` is locked for product cooks.

## Run

```bash
./scripts/run_studio.sh          # http://127.0.0.1:43217
./scripts/run_studio.sh --build  # next start
```

## Pages

| Route | Role |
|---|---|
| `/` | Story (`GET /api/story`) · lesson progress · toolchain counts → `/tools#suite` |
| `/flow` | FlowLab GCD (`FLOW_VARIANT=flowlab`) · RTL → finish → signoff |
| `/lessons` | Course wizard on `learn` |
| `/tools` | Suite, jobs, run console, inspect, viewer |
| `/pkg` | System PDN / package hub |
| `/lab` | Lab proposer (DSE). Does not run `signoff_all` |
| `/product` | Product wins (`win_rule.py`). Area / power / leakage / IR |
| `/materials` | Docs and GUI shots |

Course and FlowLab are different variants. Do not mix their artifacts.

## FlowLab (`/flow`)

Isolated finish at `results/nangate45/gcd/flowlab`.
ORFS recook (`synth` … `finish`) is refused while `6_final.gds` exists
(HTTP 403). That baseline is not overwritten. Signoff, RTL sim, and ECO
apply on `eco_scratch` stay available. Param knobs become display-only.

1. RTL — Monaco, Icarus, VCD
2. synth → finish — layout preview, phase log
3. Signoff — STA → DRC → LVS → power (`signoff_all`)
4. ECO — propose on `flowlab`; apply/close on `eco_scratch` only

DSE proposes knobs on `/lab`. It is not a FlowLab finish step and does
not run `signoff_all`.

Shortcuts: `Ctrl+S` save, `Ctrl+Enter` run phase.
Screenshots: `studio/docs/images/flowlab/`.

## Jobs and locks

One ORFS job at a time (`learn/.studio-run.lock`).
Missing prior-phase artifacts return HTTP 412.
A running job returns HTTP 409.
A FlowLab ORFS recook against an existing `6_final.gds` returns HTTP 403.
Long actions (`cts`, `route`, `finish`, `signoff_all`, ECO apply/close)
ask for confirmation.

| Endpoint | Role |
|---|---|
| `GET /api/run/stream?action=` | SSE log |
| `POST /api/run/cancel` | SIGTERM by job id |
| `GET /api/jobs` | history + pipeline + lock |
| `GET /api/signoff?variant=` | four pillars vs `golden-gcd.json` |
| `GET /api/suite` | hook matrix |
| `GET /api/story` | three-surface snapshot |
| `GET /api/product` | official-slot cooks vs `win_rule.py` |
| `GET /api/inspect?stage=` | ODB / STA / Yosys |
| `POST /api/viewer` | OpenROAD `-web` on port 43190 |
| `GET/PUT /api/flowlab` | RTL + params |

Deep links: `/flow?phase=finish#eco` · `/tools#suite` · `/tools?tab=run&action=klayout_lvs`.

## Tests

```bash
./scripts/test_studio_api.sh
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_signoff_honesty.py
```

## Troubleshooting

| Symptom | Action |
|---|---|
| HTTP 412 | Run the previous phase |
| HTTP 409 | Wait, or `DELETE /api/jobs?force=1` if the lock is stale |
| GUI will not open | Headless: use Web Viewer or copy the command |
| WNS −0.02 ns on FlowLab GCD | Expected vs `golden-metrics.md` |
| LVS must-connect on DFF_X2 | Educational leftover (Nangate split wells). Compare must still match |
| Next.js “Issues” badge | Dev overlay only. ORFS errors are in the terminal digest |

Job log: `learn/.studio-jobs.json`. Lock: `learn/.studio-run.lock`.
