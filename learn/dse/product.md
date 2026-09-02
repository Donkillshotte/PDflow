# Prodotto vs laboratorio

Scelte ferme (non si ritoccano dopo i dati).

## Prodotto

Cercare manopole fisiche (e metodo di sintesi ABC area) sulla **netlist
ufficiale**. Non si riscrive il Verilog di progetto.

Il **floorplan è fisso**: stessa area totale, stessa dimensione, stessa
forma del run ufficiale. Non si tocca `CORE_UTILIZATION`,
`CORE_ASPECT_RATIO`, `DIE_AREA`. I cook di prodotto inchiodano
`DIE_AREA`/`CORE_AREA` dal DEF ufficiale. I run storici che hanno
mosso il die restano in laboratorio (`wrong_die`); non sono win di
prodotto.

La DSE vecchia (e-graph, rewrite, IR F4, refine) resta **laboratorio**.
Non è il prodotto. Non si cancella; non decide i win.

## Vittoria (nuova, include potenza, leakage e IR)

Confronta un challenger col base dello stesso design e stesso clock.

- **Vince** se il timing non è peggio di 5 ps **e** almeno uno tra area,
  potenza, leakage, IR worst è meglio del 10% **e** nessuno dei quattro
  è peggio del 10%.
- **Vince** anche se il timing è meglio di 5 ps **e** nessuno dei
  quattro è peggio del 10%.
- **Vince** se chiude (WNS≥0) e il base no, senza peggiorare
  area/potenza/leakage/IR del 10%.
- **wrong_die** (laboratorio, non un win) se ha mosso area totale,
  dimensione o shape del floorplan ufficiale.
- **Perde** se il timing è peggio di 5 ps, **oppure** area o potenza o
  leakage o IR è peggio del 10%.
- Altrimenti **pareggio**.

La regola H1–H6 della campagna P0–P7 non si riscrive. Questa vale per il
prodotto da qui in poi.

## Ciclo

Un coordinatore, senza `if design == …`. RTL fisso: esplora dalla
sintesi in poi. Review del registro → decide la prossima mossa:

1. **Cover.** Se manca una ricetta del catalogo, cucinala (dal finish
   più economico). Salta `synth_area` e **tutte** le ricette floorplan.
2. **Improve.** Se uno slot non ha win, inventa: combo su die aperto,
   knob nuovi su die già chiuso.
3. **Tune.** TPE sullo stesso die, stesso forno (CTS/route/finish).
   Sostituisce deepen nel default. Piano congelato: `tpe_plan.md`.
   `--deepen` resta override (griglia 2 assi, non TPE).
4. **Stop.** Catalogo coperto, slot senza win esauriti, budget TPE
   finito o slot non ammissibile (es. spi già chiuso e senza win).

`--cover-all` / `--improve` restano override. Il default è il review.

**spi @ 1 ns è esaurito** come slot senza win. Non si lancia TPE lì.
Non si riscrive il Verilog.

Nessun trial TPE cambia queste scelte: spazio, score, pin del die e
`cook_one` seguono `tpe_plan.md`.

Indice di lettura: `docs/README.md`. Dopo TPE v1: `arch_review.md`.
