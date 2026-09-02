# Prodotto

Le scelte ferme stanno in [`learn/dse/product.md`](../learn/dse/product.md).
Questa pagina è la versione operativa.

## Cosa si cerca

Manopole fisiche (e ABC area) sulla **netlist Yosys ufficiale**.
Il Verilog di progetto non si riscrive. Il **floorplan è fisso**
(area, dimensione, shape del DEF ufficiale).

## Vittoria

Stesso design, stesso clock, contro il base P0.

- Timing non peggio di 5 ps **e** almeno uno tra area / potenza / leakage / IR
  better ≥10%, nessuno dei quattro worse ≥10%.
- Oppure timing better > 5 ps, senza peggiorare i quattro del 10%.
- Oppure chiude (WNS≥0) e il base no, senza peggiorare i quattro del 10%.
- Die mosso → `wrong_die` (laboratorio, non un win).
- Altrimenti lose o tie.

Codice: [`learn/dse/win_rule.py`](../learn/dse/win_rule.py).

## Ciclo

`PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py`

1. **Cover** — buchi del catalogo (titoli umani). Salta floorplan e `synth_area`.
   Salta i muri inferiti (oggi: Sintesi gerarchica).
2. **Improve** — solo slot con 0 win.
3. **Tune** — TPE, un finish alla volta, stesso die. Default dopo cover+improve.
4. **Stop** — catalogo coperto, improve esaurito, budget TPE finito, o slot
   non ammissibile (**spi @ 1 ns**).

`--deepen` è override (griglia 2 assi). `--cover-all` / `--improve` restano.

## Catalogo (titoli)

Una ricetta = un asse, stesso id su tutti i design.

| id | Titolo |
|---|---|
| `place_denser` | Place più denso |
| `place_sparser` | Place più sparso |
| `cell_pad_plus` | Padding celle +1 site |
| `repair_setup_margin` | Margine di setup sul repair |
| `repair_half_tns` | Repair TNS a metà |
| `cts_closer_bufs` | Buffer di clock più fitti |
| `place_sparse_setup` | Place più sparso + margine di setup |
| `synth_hier` | Sintesi gerarchica (muro: 0 win su 5 design) |
| `core_*` / `aspect_wide` | Laboratorio (`wrong_die`) |

Definizioni: [`learn/dse/knob_catalog.py`](../learn/dse/knob_catalog.py).

## Slot

Clock da `DESIGN_CATALOG`. Die dal DEF ufficiale (`floorplan.official_box`).

| id | clock | Tune |
|---|---|---|
| gcd | 0.46 ns | sì |
| spi | 1.0 ns | no (chiuso, 0 win) |
| ibex | 2.2 ns | sì |
| aes | 0.82 ns | sì (`FLOORPLAN_DEF`, niente DIE+DEF) |
| dynamic_node | 6.0 ns | sì |

Cheap-first: gcd → spi → ibex → aes → dynamic_node.

## Tuner

Spazio: 7 assi (densità, pad 0–2, TNS, setup, hold, CTS, timing-driven).
Mai util / aspect / die / ABC speed. Optuna solo in
[`learn/scripts/run_tpe.py`](../learn/scripts/run_tpe.py).

Warm-start dallo stesso die; poi combo deepen; poi fino a 3 meccanismi
vincenti su ≥2 design. Pad=2 è muro (mai finito su gcd e ibex).

Piani: [`tpe_plan.md`](../learn/dse/tpe_plan.md), [`arch_review.md`](../learn/dse/arch_review.md).
