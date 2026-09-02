# Prodotto vs laboratorio

Scelte ferme (non si ritoccano dopo i dati).

## Prodotto

Cercare manopole fisiche (e metodo di sintesi ABC area) sulla **netlist
ufficiale**. Non si riscrive il Verilog di progetto.

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
- **Perde** se il timing è peggio di 5 ps, **oppure** area o potenza o
  leakage o IR è peggio del 10%.
- Altrimenti **pareggio**.

La regola H1–H6 della campagna P0–P7 non si riscrive. Questa vale per il
prodotto da qui in poi.

## Ciclo

Un coordinatore, senza `if design == …`. RTL fisso: esplora dalla
sintesi in poi. Review del registro → decide la prossima mossa:

1. **Cover.** Se manca una ricetta del catalogo, cucinala (dal finish
   più economico). Salta `synth_area` e floorplan su die bloccato.
2. **Improve.** Se uno slot non ha win, inventa: combo su die aperto,
   knob nuovi su die già chiuso.
3. **Deepen.** Se ci sono win, combina due assi che hanno già vinto
   (stessa netlist ufficiale). Niente coppie opposte (core stretto+largo).
4. **Stop.** Catalogo coperto, slot senza win esauriti, combo dei win
   già provate.

`--cover-all` / `--improve` restano override. Il default è il review.

**spi @ 1 ns è esaurito** come slot senza win. Gli altri slot hanno
win: il coordinatore approfondisce le combo. Non si riscrive il Verilog.
