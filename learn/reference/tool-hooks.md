# Hook e API dei tool open (OpenROAD · OpenSTA · Yosys · KLayout)

Questa nota cataloga i **punti di aggancio** usati (o usabili) dal corso e da
Studio. Non sostituisce i manuali ufficiali: è la mappa operativa per GCD/`learn`.

## OpenROAD (`openroad`)

| Hook | Cosa fa | Uso in Studio / corso |
|---|---|---|
| `-gui` | Qt layout viewer | `POST /api/open` · pulsante **Apri GUI** |
| `-web -web_port N -db file.odb` | Web viewer (Leaflet + WebSocket) | `POST /api/viewer` · **Apri Web Viewer** |
| `-db file.odb` | Carica ODB all’avvio | Viewer e sessioni Tcl |
| `-python` | API Python `odb` (DB) | `GET /api/inspect` → inst/net/die |
| `-metrics file.json` | Metriche flusso in JSON | utile in script ORFS / debug |
| `-no_init -no_splash -exit` | Batch non interattivo | smoke, inspect, capture |
| `gui::*` Tcl | fit, layer, highlight, save_image… | `learn/scripts/gui_session.tcl`, atlas |
| `make gui_<stem>.odb` / `gui_final` | ORFS wrapper | `learn_gui` nelle lezioni |

Esempio Web Viewer (Desktop / browser locale):

```bash
openroad -no_init -no_splash -web -web_port 43190 \
  -db tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/4_cts.odb
# apri http://127.0.0.1:43190/
```

Esempio Python ODB:

```bash
openroad -python -no_init -exit <<'PY'
import odb
db = odb.dbDatabase.create()
odb.read_db(db, "…/4_cts.odb")
b = db.getChip().getBlock()
print(b.getName(), len(b.getInsts()), len(b.getNets()))
PY
```

Documentazione GUI Tcl: [OpenROAD GUI README](https://openroad.readthedocs.io/en/latest/main/src/gui/README.html).

**OpenROAD -web** (viewer HTML) è il hook primario per ispezione layout senza Desktop Qt.

**Mappa flusso esteso** (RTL sim, activity, DRC, gridcheck, bump/RDL, thermal):
[extended-flow.md](./extended-flow.md).

## OpenSTA (`sta`)

| Hook | Cosa fa | Uso |
|---|---|---|
| `read_liberty` / `read_verilog` / `link_design` / `read_sdc` | Setup design | LAB 01–02, inspect |
| `read_spef` | Parasitiche post-route | finish / signoff |
| `report_wns` / `report_tns` / `report_worst_slack` | Slack aggregato | `GET /api/inspect` |
| `report_checks -format end` | Tabella endpoint | inspect UI |
| `report_checks -format json` | Path strutturati | inspect (`jsonPaths`) |
| `report_checks -format summary` | Path corti | LAB/debug |

**Attenzione build:** in questa OpenSTA, `-path_delay max` può dare
`sta_error 563`. Preferisci `-group_path_count N` / `-format end|json|summary`
(vedi `gui-atlas.md`).

Esempio pre-layout (netlist Yosys):

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

Post-layout con SPEF:

```tcl
read_verilog results/nangate45/gcd/learn/6_final.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
read_spef results/nangate45/gcd/learn/6_final.spef
report_wns
```

## Yosys

| Hook | Cosa fa | Uso |
|---|---|---|
| `stat` | Celle / area | synth LAB + inspect |
| `hierarchy -top` | Top module | script corso |
| `synth` / ORFS `1_2_yosys.v` | Netlist gate-level | fase synth |
| `equiv_make` / `equiv_induct` | Equiv RTL↔synth (EQY-class) | azione `yosys_equiv` |
| `sat -tempinduct` | Formal safety (sby-class) | azione `formal_gcd` |
| `-p "…"` | One-liner | `GET /api/inspect` |

## KLayout

| Hook | Cosa fa | Uso |
|---|---|---|
| `klayout file.gds` | Viewer interattivo | `POST /api/open` su `6_final.gds` |
| `klayout -b -r script` | Batch | lezione 07 |

## Altri tool (probe / mapped / gap)

Vedi la matrice in [oss-integrations.md](./oss-integrations.md).

| Tool | Stato qui | Nota |
|---|---|---|
| **Magic** | PARTIAL | installato; tech `minimum` — no FreePDK45 |
| **Netgen** | PARTIAL | `netgen-lvs`; LVS signoff = KLayout |
| **EQY / sby** | MAPPED | Yosys `equiv_*` e `sat -tempinduct` |
| **Xyce** | GAP | ngspice copre System PDN |
| **FasterCap / Raphael / StarRC** | MAPPED/GAP | OpenRCX + PEX analitico |
| **open_pdks** | GAP | Sky130/gf180, non questo corso |
| **Icarus** | INTEGRATED | `rtl_sim` + VCD |

## Come Studio li orchestra

| API / UI | Tool dietro |
|---|---|
| `/api/open` | OpenROAD `-gui`, KLayout, deep-link **run**, **webviewer** |
| `/api/viewer` | OpenROAD `-web` |
| `/api/inspect` | OpenROAD `-python`, OpenSTA, Yosys |
| `/api/suite` | matrice hook collaborativa (toolchain → signoff) |
| `/api/results` | File results/reports/logs ORFS |
| `/api/run/stream` | ORFS make + `rtl_sim` / `vectorless` / `vyges_em_ir` / `dynamic_ir` / `yosys_equiv` / `formal_gcd` / `openrcx_report` / `activity_power` / `chip_pdn_ir` / `system_pdn` / `power_chain` / `klayout_drc` |
| Ctrl+K | dashboard, run extended, Qt GUI, web viewer |
| Suite hub (`/` · `/strumenti#suite`) | stato hook live + Apri/Run |

Deep-link utili:

- `/strumenti?stage=cts&tab=results#inspect`
- `/strumenti?tab=run&action=rtl_sim`
- `/strumenti?tab=run&action=gridcheck`
- `/strumenti?tab=run&action=chip_pdn_ir`
- `/strumenti?tab=run&action=vyges_em_ir`
- `/strumenti?tab=run&action=dynamic_ir`
- `/strumenti?tab=run&action=system_pdn`
- `/strumenti?tab=run&action=power_chain`
- `/strumenti#suite`
