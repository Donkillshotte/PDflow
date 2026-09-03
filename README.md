# PDflow

RTL → GDSII on OpenROAD / ORFS (Nangate45 / FreePDK45). Course, FlowLab GUI, and a
physically-aware design-space loop share one tree — wins are decided only in product code.

Three surfaces. Do not mix them.

| Surface | What | Entry |
|---|---|---|
| **Product** | Physical knobs, official netlist, fixed die, real finish | [docs/product.md](docs/product.md) |
| **Lab** | e-graph, rewrite, IR F4, refine, DSE | [learn/dse/README.md](learn/dse/README.md) |
| **Course / Studio** | Lessons, FlowLab, signoff actions | [learn/README.md](learn/README.md) · [studio/README.md](studio/README.md) |

Product win rule: [`learn/dse/win_rule.py`](learn/dse/win_rule.py).
Operations: [`docs/operations.md`](docs/operations.md).
Results: [`docs/results.md`](docs/results.md).
Live tool status (WORKS / FAIL / GAP): [`learn/reference/suite-status.md`](learn/reference/suite-status.md).
Agent rules: [`AGENTS.md`](AGENTS.md).

Educational stack, not a foundry deck. Signoff is `run_signoff_all.sh`
(STA → DRC → LVS → power). DSE only proposes knobs. ECO propose is
allowed on locked variants; apply writes finish artifacts on an unlocked
copy and still requires `signoff_all`. License-gated leftovers
(CCS liberty, StarRC, S-parameter, MCMM corners) are listed in
[`learn/reference/gaps.md`](learn/reference/gaps.md).

## Quick start

```bash
PD_FLOW_PROFILE=core EDA_JOBS=2 bash scripts/cloud_agent_install.sh
./scripts/run_studio.sh          # http://127.0.0.1:43217
```

Headless GCD flow:

```bash
./scripts/run_gcd_flow.sh
```

Fast honesty checks:

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_signoff_honesty.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_lab_physics.py
```

Install profiles, versions, troubleshooting: [docs/install.md](docs/install.md).

## Studio / FlowLab

```bash
./scripts/run_studio.sh
# FlowLab: http://127.0.0.1:43217/flow
```

Monaco RTL editor, ORFS parameters, seven-phase pipeline, layout viewport, signoff console.
Screenshots: [`studio/docs/images/flowlab/`](studio/docs/images/flowlab/).
API and layout: [studio/README.md](studio/README.md).

Extended signoff (gate sim, activity, chip/system PDN, thermal, PEX, CCS sidecar):
[learn/reference/extended-flow.md](learn/reference/extended-flow.md).

## Toolchain

| Tool | Version |
|---|---|
| OpenROAD | 26Q2 |
| OpenSTA | 3.1.0 |
| ORFS / Yosys | 26Q2 / 0.63 |
| KLayout | 0.30.11 |

Also: ngspice, vyges-em-ir, optional HotSpot / Xyce / FasterCap.
OSS matrix: [learn/reference/oss-integrations.md](learn/reference/oss-integrations.md).

Tested on Ubuntu 24.04 (22.04 supported).

## Documentation

Index: [docs/README.md](docs/README.md) · architecture: [docs/architecture.md](docs/architecture.md) ·
contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
