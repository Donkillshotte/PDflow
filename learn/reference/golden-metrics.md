# Metriche d’oro — run di riferimento `learn`

Un flusso **completo** sul tutorial (`CORE_UTILIZATION=35`, `constraint.sdc` 0.46 ns,
OpenROAD **26Q2**, ORFS **26Q2**).

I tuoi numeri possono differire di qualche percento (thread, seed). Se divergono di
**un ordine di grandezza**, hai sbagliato variant, SDC o PDK.

## Comando unico (dalla cartella `flow/`)

Copia **intero**. Mai `make ...` con puntini: senza `DESIGN_CONFIG` e `FLOW_VARIANT=learn`
ORFS ricade sul GCD upstream (util diversa, cartella `base`).

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` | `floorplan` | `place` | `cts` | `route` | `finish` | `gui_<stem>.odb`

Pulizia di una fase: `clean_synth` … `clean_finish` o `clean_all` (non `make clean`:
in questa ORFS è disabilitato).

---

## Tabella maestra

| Stadio | File | Cosa annotare | Valore riferimento |
|---|---|---|---|
| Synth | `synth_stat.txt` | celle / area / DFF_X1 | **496** / **628.824** / **35** |
| Floorplan | `2_1_floorplan.log` | Core area / eff. util | **1712.5 µm²** / **0.367** |
| Floorplan | stesso log | Design area | **629 µm² ~37%** |
| Place resize | `3_4_place_resized.log` | Design area | **684 µm² 40%** |
| Place | `3_resizer.rpt` | worst slack max | **+0.01 ns** (0 viol setup) |
| Place | stesso | `period_min` / fmax | **0.45 ns** / ~**2240 MHz** |
| CTS DPL | `4_1_cts.log` `DPL-0006` | util pre-repair | **40.5%** (693 / 1712 µm²) |
| CTS RSZ | stesso log | buffer / warning | **Inserted 45**, **RSZ-0062** |
| CTS DPL | stesso | util post-repair | **48.3%** (828 µm²) |
| CTS | `4_cts_final.rpt` | WNS / viol / skew | **−0.04** / **32** / ~**0.00** |
| GRT | `5_global_route.rpt` | WNS / viol | **−0.05** / **43** |
| DRC | `5_route_drc.rpt` | `wc -l` | **0** (clean) |
| Finish | `6_finish.rpt` | WNS / TNS / viol | **−0.04** / **−0.60** / **38** |
| Finish | stesso | `period_min` / fmax | **0.50 ns** / ~**2011 MHz** |
| Finish | stesso | setup skew | ~**0.00** |
| IR drop | `orfs_final_ir_drop.png` | scala | ~**0–5.2 mV** |

Lettura obbligatoria: **fmax finish (2.01 GHz) < 1/0.46 (2.17 GHz)**.
`make finish` verde ≠ timing chiuso al periodo SDC.

`period_min` è il periodo più piccolo per cui lo STA **non** vede WNS negativo
(con quel modello RC). fmax ≈ `1000 / period_min` in MHz se `period_min` è in ns.

Clock **ideale** a place (`period_min` 0.45) vs clock **propagato** + SPEF a finish (0.50):
lo 0.05 ns in più è fili + albero, non un bug.

**RSZ-0062** su questo run è atteso: il resizer CTS non chiude tutte le setup.
Il placement resta legale (util 48%, non 100%). **DPL-0038** è un altro errore
(LAB 05 parte 4).

---

## Come estrarre i campi (copia-incolla)

Da `tools/OpenROAD-flow-scripts/flow`:

```bash
rg -n 'Number of cells|Chip area|DFF_X1' reports/nangate45/gcd/learn/synth_stat.txt
rg -n 'Core area|Effective utilization|Design area' logs/nangate45/gcd/learn/2_1_floorplan.log
rg -n 'worst slack|period_min|setup violation' reports/nangate45/gcd/learn/3_resizer.rpt
rg -n 'Inserted|DPL-0006|RSZ-0062' logs/nangate45/gcd/learn/4_1_cts.log
rg -n 'worst slack|setup violation|skew' reports/nangate45/gcd/learn/4_cts_final.rpt
wc -l reports/nangate45/gcd/learn/5_route_drc.rpt
rg -n 'wns max|tns max|period_min|setup violation' reports/nangate45/gcd/learn/6_finish.rpt
```

---

## Clock tree (viewer)

PNG: `gui-shots/orfs_cts_clock_tree.png`

- Latency foglie ~ **0.07 ns**
- Secondo livello ~ **fanout 4**
- Foglie allineate in Y → skew piccolo (coerente con report ~0)

---

## Cosa non è “d’oro”

- Run `FLOW_VARIANT=base` o `designs/nangate45/gcd` **senza** `-tutorial`
- SDC tight 0.25 ns + util 55 → **DPL-0038** (esercizio LAB 05, non questa tabella)
- Yosys senza Tcl / ORFS master vs OpenROAD 26Q2 (`STA-2204`)

---

## Come usarla nel quaderno

Per ogni lezione: copia la riga della tabella, metti **il tuo valore** accanto,
scarto percentuale. Se scarto > 20% su area/celle, ferma e apri il playbook.
Il progetto finale ha la stessa griglia in `workbook/progetto-finale-template.md`.
