# AGENTS

Regole operative per chi tocca questo repo. La legge del prodotto sta in
[`learn/dse/product.md`](learn/dse/product.md). Indice: [`docs/README.md`](docs/README.md).

## Tre superfici

1. **Prodotto** — knob fisici, netlist ufficiale, die fisso, finish vero.
   Win = `learn/dse/win_rule.py`. Ciclo: cover → improve → tune.
2. **Laboratorio** — e-graph, rewrite, F4, refine, GNN. Non decide i win.
3. **Corso / Studio / FlowLab** — didattica. `FLOW_VARIANT=learn` e
   `flowlab` sono **locked**.

Non mescolare le tre. Non promuovere un risultato lab a win di prodotto.

## Vietato

- `if design ==` nel tuner, nello spazio, nello score, nel coordinatore,
  nel transfer. I range sono offset sui default di `config.mk`.
- `FLOW_VARIANT` in `{flowlab, learn, base}`. Il wrapper deve rifiutare.
- Krylov / MOR su AES (~50–70k-R).
- Restampare l’oro GCD Dynamic IR **45.298 mV**.
- Sovrascrivere `results/.../gcd/flowlab/` o `learn/sim/dse/memory_aes.jsonl`
  riga `febe6804241c`.
- TPE su spi @ 1 ns.
- Surrogato bayesiano del finish sotto ~40 finish per-design
  (`next_iteration_plan.md` §7).
- Proposer nuovi (LLM / RL / GNN / white-box) come prodotto.
- `pkill -f`. Uccidere solo per PID.
- Committare leftover: `memory_flowlab_nl.jsonl`,
  `memory_camp_spi_dse.index.json`, `dse_camp_spi_dse.json`.

## Un job

Una cottura pesante alla volta. Wrapper con `prlimit --as`.
TPE è ask → `cook_one` → tell, seriale. Non precomputare 4 trial.

## Test

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
```

Suite veloce: sintetico o gcd-scale. Un `test_dse.py` alla volta.
Live F4 per ultimo. Non lanciare AES finish “per vedere”.

## Documentazione

- Indice: `docs/README.md`. Tree: `docs/architettura.md`.
  Lab: `docs/laboratorio.md`. Corso: `docs/corso.md`.
  Script: `docs/script.md`. Piani: `docs/piani.md`.
- Piani congelati non si riscrivono dopo i dati (`tpe_plan.md`,
  `product.md`, `arch_review.md` §4–§6, I1–I5, §5 P0–P7).
- Titoli di ricetta per gli umani, non gli hash `camp_*_tpe_*`.
- Sempre area, potenza, leakage, IR insieme. Win/lose onesti.
- Contribuire: `CONTRIBUTING.md`.

## Branch

Prefisso `cursor/`, suffisso assegnato dall’agente. Non lasciare `main`
per lavoro prodotto. Non force-push. Non mergiare da soli.

## Origin

Repo Origin: usare `origin` (non `gh`) dove serve il forge CLI.
Le PR si creano/aggiornano con lo strumento PR dell’agente.
