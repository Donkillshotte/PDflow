# Piano: ricetta congiunta (sintesi + stadi fisici), design-agnostic

Solo piano. Nessun finish parte da questo commit. §5 resta frozen.

## Cosa abbiamo imparato (non si riscrive)

- I win §5 arrivano dalla **netlist ufficiale** (ABC area) + knob fisici.
- ABC delay e i rewrite DSE: 0 win. Il Verilog di progetto non si tocca.
- Si aggiorna il **metodo di sintesi** dei *nuovi* challenger: ABC area,
  non ABC speed, salvo controllo esplicito.
- I knob sono **offset dal default di config**, uguali su ogni design.
  Non esiste un ramo `if design == gcd`.

## Spazio (catalogo)

`learn/dse/knob_catalog.py`, stadi: synth, floorplan, place, repair, CTS.
Ogni ricetta ha `title` / `does` / `payoff`. L'id filesystem è
`camp_<design>_<recipe_id>` (leggibile). Combinare al più 2 assi per
cottura; place-first, finish solo se la policy dice EVALUATE.

## Metriche da riportare sempre (non nel verdetto §5)

WNS, TNS, area, power, leak, **IR worst**, **IR mean** (tutto il die),
cell density (util%), congestion come **WL/core** (i JSON ORFS non hanno
overflow fraction), GRT WL, fmax, setup viol, repair buffers.

## Nomi

Mai solo `d25u35`. In tabella si legge il `title`. Il payoff sta in
`qor_compare.md` § Ricette.

## Successo

Un win §5 su un design *non* usato per scegliere i knob (transfer
design-agnostic), oppure la misura onesta che un asse nuovo (aspect, CTS,
repair) non muove il finish. Pareggio è una risposta.
