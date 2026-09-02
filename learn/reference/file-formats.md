# Formati file — cosa aprire, con quale tool, cosa impari

Every fase del course produce file diversi. This guide ti dice **come studiarli**.

---

## Verilog (`.v`)

| Quando | Files esempio |
|---|---|
| Pre-synth | `designs/src/gcd/gcd.v` |
| Post-synth | `results/.../1_2_yosys.v` |
| Post-route | `results/.../6_final.v` |

**Tool:** editor testo, `yosys -p "read_verilog ..."`, OpenROAD `read_verilog`

**What you learn:** gerarchia RTL vs flat gate-level; nomi celle standard; connessioni clock/reset.

**Exercise:** conta `DFF` in RTL vs `1_2_yosys.v`. Riferimento `learn`: 35 `DFF_X1` in `synth_stat.txt`.

---

## SDC (`.sdc`)

| Files | Uso |
|---|---|
| `constraint.sdc` | Input utente |
| `1_synth.sdc`, `3_place.sdc`, … | Propagati per fase |

**Tool:** editor, `sta`, OpenROAD `read_sdc`

**Comandi chiave da saper spiegare aloud:**
```tcl
create_clock -name clk -period 0.46 [get_ports clk]
set_input_delay  ...
set_output_delay ...
```

**Exercise:** modifica periodo e ricalcola input_delay manualmente.

---

## ODB (`.odb`)

**Tool:** OpenROAD GUI (`gui_<stem>.odb`), `read_db` in Tcl

**Contains:** tech, celle piazzate, routing (se fase ≥ route), timing graph

**Why is centrale:** every snapshot `.odb` is una "fotografia" del design a quella fase.

**Sequenza da aprire in a session GUI:**
1. `1_synth.odb`
2. `2_4_floorplan_pdn.odb`
3. `3_5_place_dp.odb`
4. `4_cts.odb`
5. `5_2_route.odb`
6. `6_final.odb`

Note per ciascuno: numero istanze, presenza wire, presenza clock buffers.

---

## DEF (`.def`)

**Tool:** editor testo, KLayout, OpenROAD `read_def`

**Contains:** componenti con coordinate, nets, routing (post-route)

**Exercise:** apri `6_final.def`, search for `COMPONENTS` e `NETS`. Quanto is grande vs `.v`?

---

## Guide GRT (`route.guide`)

**Tool:** editor testo; GUI `gui_5_1_grt.odb`

**Contains:** per every net, fasce (layer + bounding box) — **non** polilinee GDS.

```bash
head -40 results/nangate45/gcd/learn/route.guide
wc -l   results/nangate45/gcd/learn/route.guide
```

On the GCD are **migliaia** di righe. Zero righe = GRT failed.

---

## SPEF (`.spef`)

**Tool:** editor, OpenSTA con `read_spef`

**Contains:** RC parasitics for every net/node (resistance, capacitance). Units in header.

**Quando:** post-extraction OpenRCX (finish). Timing **realistico**. Senza SPEF resti su `estimate_parasitics`.

Header reale del run `learn` (`6_final.spef`, OpenROAD 26Q2):

```
*SPEF "ieee 1481-1999"
*DESIGN "gcd"
*VENDOR "The OpenROAD Project"
*PROGRAM "OpenROAD"
*VERSION "26Q2-1164-g08f67ee5ec"
*T_UNIT 1 NS
*C_UNIT 1 PF
*R_UNIT 1 OHM
*NAME_MAP
*1 _000_
...
*D_NET *1 0.000304643
```

`*NAME_MAP` associa indici ai nomi net/pin. `*D_NET <id> <lumped_cap>` apre a net;
i numeri after are R/C del modello. You do not need decodificare every riga: you need sapere
che **is RC**, e che STA after `read_spef` use questi valori.

**Exercise:** `head -20 results/.../6_final.spef` — verifica `*SPEF` e `*DESIGN "gcd"`.
Compare WNS place **+0.01**, CTS **−0.04**, GRT **−0.05**, finish **−0.04** (TNS −0.60)
in `golden-metrics.md`.

---

## GDS (`.gds`)

**Tool:** KLayout, viewer fab

**Contains:** geometrie mask-ready

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

**Regola:** the log is the *truth* di cosa ha fatto il tool. Il report is the *summary*.

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

**Exercise workbook:** crea tabella Excel/markdown con WNS/TNS/area per 3 run con SDC diversi.

---

## Makefile / config.mk

**config.mk** — parametri del **tuo** design (utilization, SDC path, variant)

**platforms/nangate45/config.mk** — parametri **PDK** (layer, site, default density)

**Conflict priority:** command line > config design > platform defaults

---

## Mappa mental

```
Tu scrivi:     Verilog + SDC + config.mk
Yosys produce: .v gate-level + rtlil
OpenROAD:      .odb (every fase) + .def + .spef + report
KLayout:       .gds
Tu impari:     log + GUI + report + modifiche SDC/config
```
