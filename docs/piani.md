# Piani congelati

Non si ritoccano dopo i dati. L’indice di lettura resta [`docs/README.md`](README.md).

## Prodotto (da qui in poi)

| File | Ruolo | Non fare |
|---|---|---|
| [`learn/dse/product.md`](../learn/dse/product.md) | Prodotto vs lab, win, ciclo | Riscrivere la win rule a parole |
| [`learn/dse/win_rule.py`](../learn/dse/win_rule.py) | Codice della vittoria | Aggiungere eccezioni per design |
| [`learn/dse/tpe_plan.md`](../learn/dse/tpe_plan.md) | TPE v1 (prima dei trial) | Cambiare spazio/score dopo i cook |
| [`learn/dse/arch_review.md`](../learn/dse/arch_review.md) | Muri + transfer post gcd/ibex/aes | Implementare lo slot-order (#4) |

## Campagna storica e lab

| File | Ruolo | Non fare |
|---|---|---|
| [`learn/dse/experiment_campaign_plan.md`](../learn/dse/experiment_campaign_plan.md) | P0–P7, criteri §5 | Reinterpretare H1–H6 |
| [`learn/dse/next_iteration_plan.md`](../learn/dse/next_iteration_plan.md) | I1–I5 | Surrogato bayesiano del finish |
| [`PLAN.md`](../PLAN.md) | Lab Fase 2 (chiusa) | Riaprire i passi A–E |
| [`learn/dse/eval_policy.md`](../learn/dse/eval_policy.md) | Policy eval storica | Promuoverla a win_rule |
| [`learn/dse/joint_recipe_plan.md`](../learn/dse/joint_recipe_plan.md) | Combo pre-TPE | Sostituire il catalogo |

## Writeup (archivio, non legge)

`campaign_writeup.md`, `next_iteration_writeup.md`, `eval_campaign.md`,
`eval_vs_base_flow.md`, `qor_compare.md`, `handoff_finish_plan.md`.
Servono a capire i numeri vecchi. Il verdetto vivo è il jsonl + `win_rule`.
