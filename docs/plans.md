# Frozen plans

Do not edit after data. Reading index: [`docs/README.md`](README.md).

## Living RTL-to-signoff campaign (not frozen)

The leftover-free RTL-to-signoff goal was **stopped on 2026-09-04,
not achieved**. Done vs missing, live leftovers, and failed closes:
[`rtl_to_signoff.md`](rtl_to_signoff.md).

Next action (suite integrity, not leftover-free):
[`rtl_to_signoff_close_plan.md`](rtl_to_signoff_close_plan.md).

Do **not** copy that review or plan into the frozen files below.

sky130 vs Nangate45 (investigation, not a migration):
[`sky130_integration.md`](sky130_integration.md). Do not mix sky130
into the course.

ASAP7 as Lab research kit (investigation, not a migration):
[`asap7_research.md`](asap7_research.md). Do not mix ASAP7 into the
course or promote an ASAP7 finish to a product win.

## Product (from here on)

| File | Role | Do not |
|---|---|---|
| [`learn/dse/product.md`](../learn/dse/product.md) | Product vs lab, win, cycle | Rewrite the win rule in prose |
| [`learn/dse/win_rule.py`](../learn/dse/win_rule.py) | Win code | Add per-design exceptions |
| [`learn/dse/tpe_plan.md`](../learn/dse/tpe_plan.md) | TPE v1 (before trials) | Change space/score after cooks |
| [`learn/dse/arch_review.md`](../learn/dse/arch_review.md) | Walls + transfer post gcd/ibex/aes | Implement slot-order (#4) |

## Historic campaign and lab

| File | Role | Do not |
|---|---|---|
| [`learn/dse/experiment_campaign_plan.md`](../learn/dse/experiment_campaign_plan.md) | P0–P7, §5 criteria | Reinterpret H1–H6 |
| [`learn/dse/next_iteration_plan.md`](../learn/dse/next_iteration_plan.md) | I1–I5 | Bayesian finish surrogate |
| [`PLAN.md`](../PLAN.md) | Lab Phase 2 (closed) | Reopen steps A–E |
| [`learn/dse/eval_policy.md`](../learn/dse/eval_policy.md) | Historic eval policy | Promote to win_rule |
| [`learn/dse/joint_recipe_plan.md`](../learn/dse/joint_recipe_plan.md) | Pre-TPE combos | Replace the catalog |

## Writeups (archive, not law)

`campaign_writeup.md`, `next_iteration_writeup.md`, `eval_campaign.md`,
`eval_vs_base_flow.md`, `qor_compare.md`, `handoff_finish_plan.md`.
Useful for old numbers. Live verdict = jsonl + `win_rule`.
