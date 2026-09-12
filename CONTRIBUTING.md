# Contributing

Keep changes small, attributable, and reproducible on the local machine.

## Before changing code

1. Identify the surface: course, Studio, lab, or product.
2. Read [`learn/reference/live-analysis.md`](learn/reference/live-analysis.md).
3. Preserve user changes in a dirty worktree.
4. Use a fresh `PD_FLOW_RUN_DIR` for manual experiments.

## Data contract

Do not add committed campaign rows, frozen metric tables, or fallback reads
from a previous report. Current reports must include the run identity and
compatible artifact fingerprints. If a tool is unavailable, preserve that
fact in the report instead of substituting a value.

## Tests

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/test_dse_next.py
python3 learn/scripts/test_dse.py
python3 learn/scripts/test_signoff_honesty.py
./scripts/test_course.sh
```

For Studio changes:

```bash
cd studio
npm ci
npm run lint
npm run build
```

Use the `cursor/` branch convention, do not force-push, and do not merge on
behalf of the user.
