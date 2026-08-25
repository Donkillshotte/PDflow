# Lezione 02 — Synthesis (Yosys → OpenROAD)

## Obiettivi

- Capire cosa fa la **sintesi logica** (RTL → gate-level)
- Leggere netlist, log Yosys, statistiche area
- Aprire `1_synth.odb` in GUI e navigare le celle

## Cosa succede in synthesis

1. **Yosys** legge Verilog (`gcd.v`)
2. Elabora la gerarchia (`gcd` top module)
3. Mappa a celle della libreria Nangate45 (`DFF_X1`, `AND2_X1`, …)
4. **OpenROAD** importa il netlist in database `.odb`

## File prodotti

| File | Descrizione |
|---|---|
| `1_1_yosys_canonicalize.rtlil` | IR intermedio Yosys |
| `1_2_yosys.v` | Netlist strutturale gate-level |
| `1_2_yosys.sdc` | SDC propagato post-synth |
| `1_synth.odb` | Database OpenROAD |
| `logs/.../1_2_yosys.log` | Log completo Yosys |
| `reports/.../synth_stat.txt` | Statistiche celle/wire |

## Script Tcl rilevanti

- `flow/scripts/synth.tcl` — orchestrazione
- `flow/scripts/synth_stdcells.tcl` — mapping tecnologico
- `flow/scripts/synth_odb.tcl` — import in OpenROAD

## Concetti da osservare

- Numero di celle vs RTL (registri → flip-flop, operazioni → combinatoria)
- Assenza di placement: in GUI vedi celle **impilate**, non posizionate
- Clock e reset come porte top-level

## Durata stimata

45–75 minuti.
