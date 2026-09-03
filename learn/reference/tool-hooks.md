# Open tool hooks and APIs (OpenROAD · OpenSTA · Yosys · KLayout)

This note catalogs the **hook points** used (or usable) by the course and
Studio. It does not replace official manuals: operational map for GCD/`learn`.

## OpenROAD (`openroad`)

| Hook | What it does | Use in Studio / course |
|---|---|---|
| `-gui` | Qt layout viewer | `POST /api/open` · **Open GUI** button |
| `-web -web_port N -db file.odb` | Web viewer (Leaflet + WebSocket) | `POST /api/viewer` · **Open Web Viewer** |
| `-db file.odb` | Load ODB at startup | Viewer and Tcl sessions |
| `-python` | Python `odb` API (DB) | `GET /api/inspect` → inst/net/die |
| `-metrics file.json` | Flow metrics in JSON | useful in ORFS scripts / debug |
| `-no_init -no_splash -exit` | Non-interactive batch | smoke, inspect, capture |
| `gui::*` Tcl | fit, layer, highlight, save_image… | `learn/scripts/gui_session.tcl`, atlas |
| `make gui_<stem>.odb` / `gui_final` | ORFS wrapper | `learn_gui` in the lessons |

Web Viewer example (Desktop / local browser):

```bash
openroad -no_init -no_splash -web -web_port 43190 \
  -db tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/4_cts.odb
# open http://127.0.0.1:43190/
```

Python ODB example:

```bash
openroad -python -no_init -exit <<'PY'
import odb
db = odb.dbDatabase.create()
odb.read_db(db, "…/4_cts.odb")
b = db.getChip().getBlock()
print(b.getName(), len(b.getInsts()), len(b.getNets()))
PY
```

GUI Tcl documentation: [OpenROAD GUI README](https://openroad.readthedocs.io/en/latest/main/src/gui/README.html).

**OpenROAD -web** (HTML viewer) is the primary hook for layout inspection without Desktop Qt.

**Extended flow map** (RTL sim, activity, DRC, gridcheck, bump/RDL, thermal):
[extended-flow.md](./extended-flow.md).

## OpenSTA (`sta`)

| Hook | What it does | Use |
|---|---|---|
| `read_liberty` / `read_verilog` / `link_design` / `read_sdc` | Setup design | LAB 01–02, inspect |
| `read_spef` | Post-route parasitics | finish / signoff |
| `report_wns` / `report_tns` / `report_worst_slack` | Aggregate slack | `GET /api/inspect` |
| `report_checks -format end` | Endpoint table | inspect UI |
| `report_checks -format json` | Structured paths | inspect (`jsonPaths`) |
| `report_checks -format summary` | Short paths | LAB/debug |

**Build warning:** in this OpenSTA, `-path_delay max` may give
`sta_error 563`. Prefer `-group_path_count N` / `-format end|json|summary`
(see `gui-atlas.md`).

Pre-layout example (Yosys netlist):

```bash
cd tools/OpenROAD-flow-scripts/flow
sta -no_init -exit <<'EOF'
read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_verilog results/nangate45/gcd/learn/1_2_yosys.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
report_wns
report_checks -format end -group_path_count 5
EOF
```

Post-layout with SPEF:

```tcl
read_verilog results/nangate45/gcd/learn/6_final.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
read_spef results/nangate45/gcd/learn/6_final.spef
report_wns
```

## Yosys

| Hook | What it does | Use |
|---|---|---|
| `stat` | Cells / area | synth LAB + inspect |
| `hierarchy -top` | Top module | course script |
| `synth` / ORFS `1_2_yosys.v` | Gate-level netlist | synth stage |
| `equiv_make` / `equiv_induct` | Equiv RTL↔synth (EQY-class) | action `yosys_equiv` |
| `sat -tempinduct` | Formal safety (sby-class) | action `formal_gcd` |
| `-p "…"` | One-liner | `GET /api/inspect` |

## KLayout

| Hook | What it does | Use |
|---|---|---|
| `klayout file.gds` | Interactive viewer | `POST /api/open` on `6_final.gds` |
| `klayout -b -r script` | Batch | lesson 07 |

## Other tools (probe / mapped / gap)

See the matrix in [oss-integrations.md](./oss-integrations.md).

| Tool | Status here | Note |
|---|---|---|
| **Magic** | PARTIAL | installed; tech `minimum` — no FreePDK45 |
| **Netgen** | PARTIAL | `netgen-lvs`; LVS signoff = KLayout |
| **EQY / sby** | MAPPED | Yosys `equiv_*` and `sat -tempinduct` |
| **Xyce** | INTEGRATED | `install_xyce.sh` · N4 dual-solver gold · ngspice still covers System PDN |
| **FasterCap / Raphael / StarRC** | MAPPED/GAP | OpenRCX + analytical PEX |
| **open_pdks** | GAP | Sky130/gf180, not this course |
| **Icarus** | INTEGRATED | `rtl_sim` (RTL VCD) + `gate_sim` (name-join VCD) |
| **HotSpot** | INTEGRATED | `thermal_signoff` architecture °C |
| **FasterCap** | INTEGRATED | `analytical_pex` 3D BEM 2-wire vs Sakurai–Tamaru |

## How Studio orchestrates them

| API / UI | Tool behind |
|---|---|
| `/api/open` | OpenROAD `-gui`, KLayout, deep-link **run**, **webviewer** |
| `/api/viewer` | OpenROAD `-web` |
| `/api/inspect` | OpenROAD `-python`, OpenSTA, Yosys |
| `/api/suite` | collaborative hook matrix (toolchain → signoff) |
| `/api/results` | ORFS results/reports/logs files |
| `/api/run/stream` | ORFS make + `rtl_sim` / `gate_sim` / `vectorless` / `vyges_em_ir` / `dynamic_ir` / `yosys_equiv` / `formal_gcd` / `openrcx_report` / `activity_power` / `chip_pdn_ir` / `system_pdn` / `power_chain` / `thermal_signoff` / `pkg_rdl` / `spice_engines` / `klayout_drc` |
| Ctrl+K | dashboard, run extended, Qt GUI, web viewer |
| Suite hub (`/` · `/tools#suite`) | live hook status + Open/Run |

Useful deep-links:

- `/tools?stage=cts&tab=results#inspect`
- `/tools?tab=run&action=rtl_sim`
- `/tools?tab=run&action=gate_sim`
- `/tools?tab=run&action=thermal_signoff`
- `/tools?tab=run&action=pkg_rdl`
- `/tools?tab=run&action=spice_engines`
- `/tools?tab=run&action=gridcheck`
- `/tools?tab=run&action=chip_pdn_ir`
- `/tools?tab=run&action=vyges_em_ir`
- `/tools?tab=run&action=dynamic_ir`
- `/tools?tab=run&action=system_pdn`
- `/tools?tab=run&action=power_chain`
- `/tools#suite`
