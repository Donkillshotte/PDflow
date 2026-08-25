# Lezione 02 — Synthesis (Yosys → OpenROAD)

La synthesis è l'unico passo in cui il design è ancora **solo logica**. Dopo, ogni trasformazione è geometrica o temporale.

## Obiettivi

- Distinguere Yosys (mapping) da OpenROAD (import ODB)
- Leggere netlist gate-level e `synth_stat.txt`
- Capire flatten vs hierarchical
- Aprire `1_synth.odb` e accettare che le celle siano impilate

## Letture

- Questo README
- `learn/reference/walkthrough-synth.tcl.md` (obbligatorio)
- LAB 02
- RTL: `flow/designs/src/gcd/gcd.v`

## Pipeline reale ORFS 26Q2

```
gcd.v
  → synth_canonicalize.tcl → 1_1_yosys_canonicalize.rtlil
  → synth.tcl              → 1_2_yosys.v + 1_2_yosys.sdc
  → synth_odb.tcl          → 1_synth.odb + 1_synth.sdc
```

RTLIL è l'IR di Yosys. Se esiste, ORFS può evitare di riparsare Verilog.

## Cosa fa Yosys (intuizione)

1. `read_verilog` / checkpoint RTLIL
2. `proc` — always block → netlist
3. `opt` — dead code, const fold
4. `synth -flatten` — coarse + fine, un solo modulo
5. `abc` — mapping Boolean sulla liberty
6. `dfflegalize` — FF → `DFF_X1` ecc.

GCD è piccolo: flatten è il default corretto. Hierarchical synth serve su design con moduli da non esplodere (memorie, analog wrappers).

## File prodotti

| File | Descrizione | Apri con |
|---|---|---|
| `1_1_yosys_canonicalize.rtlil` | IR | editor (opaco) |
| `1_2_yosys.v` | Gate-level | editor, `sta` |
| `1_synth.odb` | DB OpenROAD | GUI |
| `synth_stat.txt` | Conteggio celle | editor |
| `1_2_yosys.log` | Verità operativa | `rg Warning` |

## Cosa osservare nel netlist

```bash
rg -c 'DFF_' results/nangate45/gcd/learn/1_2_yosys.v
rg '^module ' results/nangate45/gcd/learn/1_2_yosys.v
```

Confronta con `always @(posedge` nel RTL. Ogni registro RTL ≈ un DFF (più bit → più DFF).

**Latch:** se Yosys inferisce `DLATCH`, il RTL ha un always combinatorio incompleto. Su GCD non dovrebbe succedere.

## GUI

`gui_1_synth.odb`: zoom out. Celle in un punto **o canvas nero** (die 0×0). PNG: `gui-shots/win_synth.png`. Display → Instances ON, Nets OFF.  
Seleziona una `DFF_X1` → Inspector → master.

Non cercare un “chip”: il floorplan non è ancora esistito. Atlante: `gui-atlas.md` §5.1.

## Timing a questo stadio

`sta` + liberty + netlist + SDC = delay **senza wire**. WNS ottimistico o comunque non confrontabile col finish.

## Durata stimata

README + walkthrough 40 min, LAB 75 min, **totale ~2 ore**.
