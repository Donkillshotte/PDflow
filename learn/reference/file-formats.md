# File formats — what to open, with which tool, what you learn

Every course phase produces different files. This guide tells you **how to study them**.

---

## Verilog (`.v`)

| When | Example files |
|---|---|
| Pre-synth | `designs/src/gcd/gcd.v` |
| Post-synth | `results/.../1_2_yosys.v` |
| Post-route | `results/.../6_final.v` |

**Tool:** text editor, `yosys -p "read_verilog ..."`, OpenROAD `read_verilog`

**What you learn:** RTL hierarchy vs flat gate-level; standard cell names; clock/reset connections.

**Exercise:** count `DFF` in RTL vs `1_2_yosys.v`. `learn` reference: 35 `DFF_X1` in `synth_stat.txt`.

---

## SDC (`.sdc`)

| Files | Use |
|---|---|
| `constraint.sdc` | User input |
| `1_synth.sdc`, `3_place.sdc`, … | Propagated per phase |

**Tool:** editor, `sta`, OpenROAD `read_sdc`

**Key commands to be able to explain aloud:**
```tcl
create_clock -name clk -period 0.46 [get_ports clk]
set_input_delay  ...
set_output_delay ...
```

**Exercise:** change the period and recalculate input_delay manually.

---

## ODB (`.odb`)

**Tool:** OpenROAD GUI (`gui_<stem>.odb`), `read_db` in Tcl

**Contains:** tech, placed cells, routing (if phase ≥ route), timing graph

**Why it matters:** every `.odb` snapshot is a "photograph" of the design at that phase.

**Sequence to open in a GUI session:**
1. `1_synth.odb`
2. `2_4_floorplan_pdn.odb`
3. `3_5_place_dp.odb`
4. `4_cts.odb`
5. `5_2_route.odb`
6. `6_final.odb`

Note for each: instance count, presence of wires, presence of clock buffers.

---

## DEF (`.def`)

**Tool:** text editor, KLayout, OpenROAD `read_def`

**Contains:** components with coordinates, nets, routing (post-route)

**Exercise:** open `6_final.def`, search for `COMPONENTS` and `NETS`. How large is it vs `.v`?

---

## GRT guide (`route.guide`)

**Tool:** text editor; GUI `gui_5_1_grt.odb`

**Contains:** per net, corridors (layer + bounding box) — **not** GDS polylines.

```bash
head -40 results/nangate45/gcd/learn/route.guide
wc -l   results/nangate45/gcd/learn/route.guide
```

On the GCD there are **thousands** of lines. Zero lines = GRT failed.

---

## SPEF (`.spef`)

**Tool:** editor, OpenSTA with `read_spef`

**Contains:** RC parasitics for every net/node (resistance, capacitance). Units in header.

**When:** post-extraction OpenRCX (finish). **Realistic** timing. Without SPEF you stay on `estimate_parasitics`.

Real header from the `learn` run (`6_final.spef`, OpenROAD 26Q2):

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

`*NAME_MAP` maps indices to net/pin names. `*D_NET <id> <lumped_cap>` opens a net;
the numbers after are R/C of the model. You do not need to decode every line: you need to know
that **it is RC**, and that STA after `read_spef` uses these values.

**Exercise:** `head -20 results/.../6_final.spef` — verify `*SPEF` and `*DESIGN "gcd"`.
Compare WNS place **+0.01**, CTS **−0.04**, GRT **−0.05**, finish **−0.04** (TNS −0.60)
in `golden-metrics.md`.

---

## GDS (`.gds`)

**Tool:** KLayout, fab viewer

**Contains:** mask-ready geometries

**Batch verification:**
```bash
klayout -b -rd gds=results/.../6_final.gds -r check_script.rb
```

---

## Log (`.log`)

**Path:** `logs/nangate45/gcd/learn/<step>.log`

**How to read:**
```bash
rg -n 'ERROR|WARNING|Core area|slack|Utilization' logs/.../learn/*.log
```

**Rule:** the log is the *truth* of what the tool did. The report is the *summary*.

---

## Report (`.rpt`, `.txt`)

| Report | Phase |
|---|---|
| `synth_stat.txt` | synth |
| `3_global_place.rpt` | place |
| `3_resizer.rpt` | place |
| `4_cts_final.rpt` | cts |
| `5_route_drc.rpt` | route |
| `6_finish.rpt` | finish |

**Workbook exercise:** create an Excel/markdown table with WNS/TNS/area for 3 runs with different SDC.

---

## Makefile / config.mk

**config.mk** — parameters of **your** design (utilization, SDC path, variant)

**platforms/nangate45/config.mk** — **PDK** parameters (layer, site, default density)

**Conflict priority:** command line > design config > platform defaults

---

## Mental map

```
You write:     Verilog + SDC + config.mk
Yosys produces: .v gate-level + rtlil
OpenROAD:      .odb (every phase) + .def + .spef + report
KLayout:       .gds
You learn:     log + GUI + report + SDC/config changes
```
