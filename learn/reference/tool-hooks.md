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
| `-p "…"` | One-liner | `GET /api/inspect` |

## KLayout

| Hook | Cosa fa | Uso |
|---|---|---|
| `klayout file.gds` | Viewer interattivo | `POST /api/open` su `6_final.gds` |
| `klayout -b -r script` | Batch | lezione 07 |

## Altri tool open (non installati di default qui)

| Tool | Perché considerarlo | Nota |
|---|---|---|
| **Magic** | Layout editor classico, DRC | utile con PDK open; non nel path attuale |
| **Netgen** | LVS | tipicamente dopo GDS |
| **OpenLane / LibreLane** | Flow all-in-one | ORFS è già il flusso del corso |
| **GTKWave** | Waveform sim | fuori physical design |
| **Icarus / Verilator** | Sim RTL | utile pre-synth, non PD |

Non li scarichiamo automaticamente: il corso resta centrato su **ORFS + Nangate45**.
Se ti servono Magic/Netgen, installali a parte e documenta i path in note personali.

## Come Studio li orchestra

| API / UI | Tool dietro |
|---|---|
| `/api/open` | OpenROAD `-gui`, KLayout |
| `/api/viewer` | OpenROAD `-web` |
| `/api/inspect` | OpenROAD `-python`, OpenSTA, Yosys |
| `/api/results` | File results/reports/logs ORFS |
| Ctrl+K | deep-link dashboard + GUI |

Deep-link utili: `/strumenti?stage=cts&tab=results#inspect`.
