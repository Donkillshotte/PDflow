# Formati file — cosa aprire, con quale tool, cosa impari

Ogni fase del corso produce file diversi. Questa guida ti dice **come studiarli**.

---

## Verilog (`.v`)

| Quando | File esempio |
|---|---|
| Pre-synth | `designs/src/gcd/gcd.v` |
| Post-synth | `results/.../1_2_yosys.v` |
| Post-route | `results/.../6_final.v` |

**Tool:** editor testo, `yosys -p "read_verilog ..."`, OpenROAD `read_verilog`

**Cosa impari:** gerarchia RTL vs flat gate-level; nomi celle standard; connessioni clock/reset.

**Esercizio:** conta `DFF` in RTL vs `1_2_yosys.v`. Riferimento `learn`: 35 `DFF_X1` in `synth_stat.txt`.

---

## SDC (`.sdc`)

| File | Uso |
|---|---|
| `constraint.sdc` | Input utente |
| `1_synth.sdc`, `3_place.sdc`, … | Propagati per fase |

**Tool:** editor, `sta`, OpenROAD `read_sdc`

**Comandi chiave da saper spiegare a voce alta:**
```tcl
create_clock -name clk -period 0.46 [get_ports clk]
set_input_delay  ...
set_output_delay ...
```

**Esercizio:** modifica periodo e ricalcola input_delay manualmente.

---

## ODB (`.odb`)

**Tool:** OpenROAD GUI (`gui_<stem>.odb`), `read_db` in Tcl

**Contiene:** tech, celle piazzate, routing (se fase ≥ route), timing graph

**Perché è centrale:** ogni snapshot `.odb` è una "fotografia" del design a quella fase.

**Sequenza da aprire in una sessione GUI:**
1. `1_synth.odb`
2. `2_4_floorplan_pdn.odb`
3. `3_5_place_dp.odb`
4. `4_cts.odb`
5. `5_2_route.odb`
6. `6_final.odb`

Annota per ciascuno: numero istanze, presenza wire, presenza clock buffers.

---

## DEF (`.def`)

**Tool:** editor testo, KLayout, OpenROAD `read_def`

**Contiene:** componenti con coordinate, nets, routing (post-route)

**Esercizio:** apri `6_final.def`, cerca `( COMPONENTS` e `( NETS`. Quanto è grande vs `.v`?

---

## SPEF (`.spef`)

**Tool:** editor, OpenSTA con `read_spef`

**Contiene:** RC parassiti per ogni net/node

**Quando:** post-estrazione (finish). Timing **realistico**.

**Esercizio:** confronta WNS in report pre-SPEF vs post-SPEF (`6_finish.rpt`).
Riferimento `learn`: place **+0.01**, CTS **−0.04**, GRT **−0.05**, finish **−0.04** (TNS −0.60).

---

## GDS (`.gds`)

**Tool:** KLayout, viewer fab

**Contiene:** geometrie mask-ready

**Verifica batch:**
```bash
klayout -b -rd gds=results/.../6_final.gds -r check_script.rb
```

---

## Log (`.log`)

**Path:** `logs/nangate45/gcd/learn/<step>.log`

**Come leggere:**
```bash
rg -n 'ERROR|WARNING|Core area|slack|Utilization' logs/.../learn/*.log
```

**Regola:** il log è la *verità* di cosa ha fatto il tool. Il report è la *sintesi*.

---

## Report (`.rpt`, `.txt`)

| Report | Fase |
|---|---|
| `synth_stat.txt` | synth |
| `3_global_place.rpt` | place |
| `3_resizer.rpt` | place |
| `4_cts_final.rpt` | cts |
| `5_route_drc.rpt` | route |
| `6_finish.rpt` | finish |

**Esercizio workbook:** crea tabella Excel/markdown con WNS/TNS/area per 3 run con SDC diversi.

---

## Makefile / config.mk

**config.mk** — parametri del **tuo** design (utilization, SDC path, variant)

**platforms/nangate45/config.mk** — parametri **PDK** (layer, site, default density)

**Priorità conflitti:** command line > config design > platform defaults

---

## Mappa mentale

```
Tu scrivi:     Verilog + SDC + config.mk
Yosys produce: .v gate-level + rtlil
OpenROAD:      .odb (ogni fase) + .def + .spef + report
KLayout:       .gds
Tu impari:     log + GUI + report + modifiche SDC/config
```
