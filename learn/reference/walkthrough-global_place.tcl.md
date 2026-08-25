# Walkthrough annotato — global_place.tcl

File: `flow/scripts/global_place.tcl`

## Input / output

- **Input:** `3_2_place_iop.odb` + `2_floorplan.sdc`
- **Output:** `3_3_place_gp.odb` (via step successivi fino a `3_place.odb`)

## Blocco load (righe 1–5)

Identico pattern floorplan: metrics → load.tcl → load_design → PRE hook.

## buffer_ports (righe 17–22)

Inserisce buffer sulle porte IO se `DONT_BUFFER_PORTS` non è set.  
**Perché:** porte input/output devono rispettare slew/cap prima del GP.

## Timing-driven GP (righe 29–35)

Se `GPL_TIMING_DRIVEN=1`:
```tcl
lappend global_placement_args {-timing_driven}
```

Il placer considera timing estimate, non solo wirelength.

## global_placement (proc do_placement)

Parametri chiave:
- `-density` — target density (da `place_density_with_lb_addon`)
- `-pad_left/right` — padding in sites tra celle
- `-timing_driven` — opzionale

**Effetto visivo GUI:** celle si "spargono" nel core; wirelength diminuisce iterativamente.

## Cosa osservare nel log `3_3_place_gp.log`

- Overflow (deve tendere a 0)
- Iterazioni GP
- Density finale

## Esercizio

Confronta `gui_3_2_place_iop.odb` vs `gui_3_3_place_gp.odb`: le celle si muovono dal bordo?
