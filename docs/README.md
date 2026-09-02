# Documentazione

Ingresso unico del repository. I piani congelati restano nei file originali;
qui si naviga. Non si riscrivono I1–I5 né §5 P0–P7.

## Tre superfici

| Superficie | Cosa è | Vittoria | Ingresso |
|---|---|---|---|
| **Prodotto** | Knob fisici sulla netlist ufficiale, die fisso, finish vero | [`win_rule.py`](../learn/dse/win_rule.py) | [prodotto.md](prodotto.md) |
| **Laboratorio** | e-graph, rewrite, IR F4, refine, GNN, solver PDN | non decide i win | [laboratorio.md](laboratorio.md) |
| **Corso / Studio** | Lezioni RTL→GDS, FlowLab, GUI | smoke corso, non QoR prodotto | [corso.md](corso.md) |

Non mescolarle. Un risultato lab non è un win di prodotto.

## Leggere in ordine

### Prodotto

1. [prodotto.md](prodotto.md) — vincoli, vittoria, ciclo, catalogo
2. [operazioni.md](operazioni.md) — comandi, test, refuse
3. [risultati.md](risultati.md) — cosa ha vinto, onesto (area / potenza / leakage / IR)
4. [../learn/dse/tpe_plan.md](../learn/dse/tpe_plan.md) — tuner (congelato prima dei trial)
5. [../learn/dse/arch_review.md](../learn/dse/arch_review.md) — muri e transfer dopo gcd/ibex/aes

### Laboratorio

1. [laboratorio.md](laboratorio.md)
2. [../PLAN.md](../PLAN.md) — Fase 2 controller IR (chiusa)
3. [../learn/reference/dse.md](../learn/reference/dse.md) — stack F0–F6
4. [../engine/README.md](../engine/README.md) — solver nativi

### Corso / Studio

1. [corso.md](corso.md)
2. [../learn/README.md](../learn/README.md) · [../learn/CURRICULUM.md](../learn/CURRICULUM.md)
3. [../studio/README.md](../studio/README.md)

## Mappa del tree

- [architettura.md](architettura.md) — directory, ownership, cosa non si sposta
- [script.md](script.md) — wrapper in `scripts/` e `learn/scripts/`
- [piani.md](piani.md) — indici dei piani congelati
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — come toccare il repo
- [../AGENTS.md](../AGENTS.md) — regole operative per agenti

## Codice prodotto

Mappa moduli: [`learn/dse/README.md`](../learn/dse/README.md).
