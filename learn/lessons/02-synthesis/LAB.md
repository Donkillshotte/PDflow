# LAB 02 — Synthesis (75 min)

## Parte 1 — Leggi RTL (15 min)

File: `flow/designs/src/gcd/gcd.v`

Identifica:
- Modulo top `gcd`
- Porte: clk, rst, req_msg, resp_msg, ...
- Quanti always block?
- Dove ci sono registri?

## Parte 2 — Run synth (10 min)

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn synth
```

## Parte 3 — Confronto RTL vs netlist (25 min)

| Aspetto | gcd.v | 1_2_yosys.v |
|---|---|---|
| Moduli | | |
| always | | |
| Celle standard | 0 | ~250 |

```bash
rg -c 'module ' flow/designs/src/gcd/gcd.v
rg -c 'DFF_|AND2_|NAND' results/nangate45/gcd/learn/1_2_yosys.v
```

## Parte 4 — Log Yosys (15 min)

```bash
rg -n 'Printing statistics|Chip area|Warning' logs/nangate45/gcd/learn/1_2_yosys.log
```

## Parte 5 — GUI 1_synth (10 min)

`gui_1_synth.odb` — celle impilate, no placement.

## Superamento

- [ ] Contato celle in synth_stat.txt
- [ ] Spiegato cosa fa yosys vs cosa fa OpenROAD in synth_odb.tcl
