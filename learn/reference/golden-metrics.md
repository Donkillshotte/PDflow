# Metrics d’oro — run di riferimento `learn`

Un flusso **completo** sul tutorial (`CORE_UTILIZATION=35`, `constraint.sdc` 0.46 ns,
OpenROAD **26Q2**, ORFS **26Q2**).

I tuoi numeri posare differire di qualche percento (thread, seed). Se divergono di
**un ordine di grandezza**, you used wrong variant, SDC or PDK.

## Comando unico (dalla cartella `flow/`)

Copia **intero**. Never `make ...` con puntini: senza `DESIGN_CONFIG` e `FLOW_VARIANT=learn`
ORFS ricade on the GCD upstream (different util, cartella `base`).

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` | `floorplan` | `place` | `cts` | `route` | `finish` | `gui_<stem>.odb`

Pulizia di una fase: `clean_synth` … `clean_finish` o `clean_all` (non `make clean`:
in this ORFS is disabilitato).

---

## Table maestra

| Stadio | Files | Cosa note | Valore riferimento |
|---|---|---|---|
| Synth | `synth_stat.txt` | celle / area / DFF_X1 | **496** / **628.824** / **35** |
| Floorplan | `2_1_floorplan.log` | Core area / eff. util | **1712.5 µm²** / **0.367** |
| Floorplan | same log | Design area | **629 µm² ~37%** |
| Place resize | `3_4_place_resized.log` | Design area | **684 µm² 40%** |
| Place | `3_resizer.rpt` | worst slack max | **+0.01 ns** (0 viol setup) |
| Place | stesso | `period_min` / fmax | **0.45 ns** / ~**2240 MHz** |
| CTS DPL | `4_1_cts.log` `DPL-0006` | util pre-repair | **40.5%** (693 / 1712 µm²) |
| CTS RSZ | same log | buffer / warning | **Inserted 45**, **RSZ-0062** |
| CTS DPL | stesso | util post-repair | **48.3%** (828 µm²) |
| CTS | `4_cts_final.rpt` | WNS / viol / skew | **−0.04** / **32** / ~**0.00** |
| GRT | `5_global_route.rpt` | WNS / viol | **−0.05** / **43** |
| DRC | `5_route_drc.rpt` | `wc -l` | **0** (clean) |
| Finish | `6_finish.rpt` | WNS / TNS / viol | **−0.04** / **−0.60** / **38** |
| Finish | stesso | `period_min` / fmax | **0.50 ns** / ~**2011 MHz** |
| Finish | stesso | setup skew | ~**0.00** |
| IR drop | `orfs_final_ir_drop.png` | scala | ~**0–5.2 mV** |

Lettura required: **fmax finish (2.01 GHz) < 1/0.46 (2.17 GHz)**.
`make finish` green ≠ timing closed al SDC period.

`period_min` is the smallest period for which STA does **not** see negative WNS
(con quel modello RC). fmax ≈ `1000 / period_min` in MHz se `period_min` is in ns.

Clock **ideale** a place (`period_min` 0.45) vs clock **propagato** + SPEF a finish (0.50):
the extra 0.05 ns is wires + tree, not a bug.

**RSZ-0062** su this run is atteso: il resizer CTS non chiude all le setup.
Il placement resta legale (util 48%, non 100%). **DPL-0038** is un altro errore
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

- Latency leaves ~ **0.07 ns**
- Secondo livello ~ **fanout 4**
- Foglie aligned in Y → skew piccolo (consistent with report ~0)

---

## Cosa is not “d’oro”

- Run `FLOW_VARIANT=base` o `designs/nangate45/gcd` **senza** `-tutorial`
- SDC tight 0.25 ns + util 55 → **DPL-0038** (exercise LAB 05, non this tabella)
- Yosys senza Tcl / ORFS master vs OpenROAD 26Q2 (`STA-2204`)

---

## How to use it in the notebook

Per every lesson: copia the row of the table, metti **your valore** accanto,
percent delta. If delta > 20% su area/celle, stop and open the playbook.
Il final project uses the same grid in `workbook/progetto-finale-template.md`.
