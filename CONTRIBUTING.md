# Contributing

Index: [`docs/README.md`](docs/README.md). Product law: [`learn/dse/product.md`](learn/dse/product.md).
Agent rules: [`AGENTS.md`](AGENTS.md).

## Before changing code

1. Know the surface: product, lab, or course. Do not mix them.
2. One heavy job. VM ~15 GiB / 4 CPU.
3. Synthetic or gcd-scale tests. Live F4 last.

## Branch and commits

`cursor/` prefix, agent-assigned suffix. Do not work on `main`.
One commit per logical change. No force-push. Do not merge on your own.

Do not commit leftovers:

- `learn/sim/dse/memory_flowlab_nl.jsonl` (+ `.index.json`)
- `learn/sim/dse/memory_camp_spi_dse.index.json`
- `learn/sim/reports/dse_camp_spi_dse.json`
- `learn/sim/dse/tpe_*.db` (already ignored)

## Minimum tests

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/test_dse_next.py    # product + docs map
./scripts/test_cloud_bootstrap.sh         # if touching install
./scripts/test_course.sh                  # if touching the course
```

Lab: `python3 learn/scripts/test_dse.py` alone, never in the same process
as the product suite.

## Forbidden

- `if design ==` in tuner / space / score / coordinator / transfer
- `FLOW_VARIANT` in `{flowlab, learn, base}` from the product wrapper
- Krylov / MOR on AES (~50–70k-R)
- Restamping gold GCD Dynamic IR **45.298 mV**
- Overwriting `results/.../gcd/flowlab/` or `memory_aes.jsonl` row `febe6804241c`
- TPE on spi @ 1 ns
- Moving ORFS or product modules for “cleanup”
- Rewriting frozen plans ([docs/piani.md](docs/piani.md))
- `pkill -f` (kill by PID)

## Documentation

Human recipe titles (`Denser placement`, not `camp_gcd_tpe_*`).
Always report area, power, leakage, IR together. Honest win/lose.
If you change an entry point, update `docs/` and the map check in
`test_dse_next.py`.
