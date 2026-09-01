# Prodotto vs laboratorio

Scelte ferme (non si ritoccano dopo i dati).

## Prodotto

Cercare manopole fisiche (e metodo di sintesi ABC area) sulla **netlist
ufficiale**. Non si riscrive il Verilog di progetto.

La DSE vecchia (e-graph, rewrite, IR F4, refine) resta **laboratorio**.
Non è il prodotto. Non si cancella; non decide i win.

## Vittoria (nuova, include potenza e IR)

Confronta un challenger col base dello stesso design e stesso clock.

- **Vince** se il timing non è peggio di 5 ps **e** almeno uno tra area,
  potenza, IR worst è meglio del 10% **e** nessuno dei tre è peggio del 10%.
- **Vince** anche se il timing è meglio di 5 ps **e** nessuno dei tre è
  peggio del 10%.
- **Vince** se chiude (WNS≥0) e il base no, senza peggiorare area/potenza/IR
  del 10%.
- **Perde** se il timing è peggio di 5 ps, **oppure** area o potenza o IR è
  peggio del 10%.
- Altrimenti **pareggio**.

La regola H1–H6 della campagna P0–P7 non si riscrive. Questa vale per il
prodotto da qui in poi.

## Ciclo

Stato del circuito (slack, TNS, densità, IR, buffer, die bloccato) →
quali ricette del catalogo possono servire → place → stop o finish →
registro. Nessun `if design == …`. Si cucina solo se il ciclo lo decide.
