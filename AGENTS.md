# AGENTS

Operational rules for anyone touching this repo. Product law lives in
[`learn/dse/product.md`](learn/dse/product.md). Index: [`docs/README.md`](docs/README.md).

## Three surfaces

1. **Product** — physical knobs, official netlist, fixed die, real finish.
   Win = `learn/dse/win_rule.py`. Cycle: cover → improve → tune.
2. **Lab** — e-graph, rewrite, F4, refine, GNN. Does not decide wins.
3. **Course / Studio / FlowLab** — teaching. `FLOW_VARIANT=learn` and
   `flowlab` are **locked**.

Do not mix the three. Do not promote a lab result to a product win.

## Forbidden

- `if design ==` in tuner, space, score, coordinator, or transfer. Ranges are
  offsets on `config.mk` defaults.
- `FLOW_VARIANT` in `{flowlab, learn, base}`. The wrapper must refuse.
- Krylov / MOR on AES (~50–70k-R).
- Restamping gold GCD Dynamic IR **45.298 mV**.
- Overwriting `results/.../gcd/flowlab/` or `learn/sim/dse/memory_aes.jsonl`
  row `febe6804241c`.
- TPE on spi @ 1 ns.
- Bayesian finish surrogate below ~40 per-design finishes
  (`next_iteration_plan.md` §7).
- New proposers (LLM / RL / GNN / white-box) as product.
- `pkill -f`. Kill by PID only.
- Committing leftovers: `memory_flowlab_nl.jsonl`,
  `memory_camp_spi_dse.index.json`, `dse_camp_spi_dse.json`.

## One job

One heavy cook at a time. Wrapper uses `prlimit --as`.
TPE is ask → `cook_one` → tell, serial. Do not precompute 4 trials.

## Tests

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
```

Fast suite: synthetic or gcd-scale. One `test_dse.py` at a time.
Live F4 last. Do not launch AES finish “just to see”.

## Documentation

- Index: `docs/README.md`. Tree: `docs/architecture.md`.
  Lab: `docs/lab.md`. Course: `docs/course.md`.
  Scripts: `docs/script.md`. Plans: `docs/plans.md`.
- Frozen plans are not rewritten after data (`tpe_plan.md`,
  `product.md`, `arch_review.md` §4–§6, I1–I5, §5 P0–P7).
- Human recipe titles, not `camp_*_tpe_*` hashes.
- Always report area, power, leakage, IR together. Honest win/lose.
- Contributing: `CONTRIBUTING.md`.

## Branch

`cursor/` prefix, agent-assigned suffix. Do not leave product work on `main`.
No force-push. Do not merge on your own.

## Origin

Origin repo: use `origin` (not `gh`) for forge CLI.
Create/update PRs with the agent PR tool.
