# Integrazioni OSS (GCD Nangate45)

Matrice onesta: ogni tool chiesto è **INTEGRATED**, **MAPPED** (equivalente OSS nel flusso studente), **PARTIAL**, o **GAP**. Il corso è pinnato **Nangate45 / FreePDK45** — non Sky130.

Legenda:

| Stato | Significato |
|---|---|
| **INTEGRATED** | Binario + script Studio + run verificato su GCD |
| **MAPPED** | Binario dedicato assente; lo stesso ruolo è coperto da un engine OSS già nel path |
| **PARTIAL** | Binario presente, ma PDK/tech incompatibile con Nangate45 |
| **GAP** | Commerciale o PDK sbagliato — non si finge l’integrazione |

Azioni Studio: `vectorless`, `yosys_equiv`, `formal_gcd`, `openrcx_report`, `analytical_pex`, `layout_tools`, `spice_engines`, `vyges_em_ir`, `dynamic_ir`, `tool_matrix`.

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_tool_matrix.sh
```

---

## Matrice tool

| Tool | Stato | Ruolo sul GCD | Evidenza | Equivalente se non INTEGRATED |
|---|---|---|---|---|
| **Yosys** | INTEGRATED | Synth ORFS + `stat` inspect + **equiv RTL↔synth** | `yosys -V` 0.63 · azione `yosys_equiv` · `sim/reports/yosys_equiv_flowlab.json` | — |
| **KLayout** | INTEGRATED | DRC/LVS signoff + GDS viewer | `klayout -v` · `drc_signoff` / `klayout_lvs` | — |
| **Magic** | PARTIAL | Installato (8.3); tech di default `minimum` | azione `layout_tools` · nessun `.tech` FreePDK45 | Signoff layout = **KLayout** |
| **Netgen** | PARTIAL | `netgen-lvs` 1.5.133 in PATH | stesso probe; no setup Nangate | Signoff LVS = **KLayout** `FreePDK45.lylvs` |
| **EQY** | MAPPED | CLI `eqy` assente | Yosys `equiv_make` / `equiv_induct` / `equiv_status` | Stesso engine di EQY |
| **SymbiYosys (`sby`)** | MAPPED | CLI `sby` assente; **z3** presente | Yosys `sat -tempinduct` su `reset \|-> resp_val=0` | Stesso backend SAT/BMC |
| **ngspice** | INTEGRATED | System PDN AC+TRAN + demo | `ngspice -v` 42 · `system_pdn` · `spice_engines` | — |
| **Xyce (Sandia)** | GAP | Non in apt / non in PATH | `spice_engines_*.json` `xyce_present: false` | **ngspice** copre AC/TRAN PDN educativo |
| **OpenRCX** | INTEGRATED | Dentro OpenROAD (`extract_parasitics`) | `6_final.spef` + `rcx_patterns.rules` · azione `openrcx_report` | — |
| **FasterCap** | MAPPED | Binario assente | Sakurai–Tamaru 1983 + FDM 2D Laplace · `analytical_pex` | Raphael-class 2-wire tutorial |
| **Raphael** | GAP | Synopsys commerciale, no licenza | documentato | OpenRCX SPEF + PEX analitico |
| **StarRC** | GAP | Synopsys commerciale, no licenza | documentato | **OpenRCX** SPEF a finish |
| **open_pdks** | GAP | Sky130 / gf180, **altro PDK** | corso pinnato Nangate45 | Non si mescola con FreePDK45 |
| **vyges-em-ir** | INTEGRATED | IR statico CG + transiente BE sulla mesh `write_pg_spice` | azione `vyges_em_ir` · `sim/reports/vyges_em_ir_flowlab.json` · binario v0.1.33 | — |
| **dynamic_ir (questo corso)** | INTEGRATED | I(t) per ITerm + **Solver A** (BE LU golden) + heatmap; B AMG / C MOR = GAP | azione `dynamic_ir` · `sim/reports/dynamic_ir_flowlab.json` + `.svg` | — |

---

## Formal / equiv (EQY · sby)

| Check | Script | Proprietà |
|---|---|---|
| Equiv | `learn/scripts/run_yosys_equiv.sh` | RTL GCD ≡ `synth -top gcd` (induzione sequenziale) |
| Safety | `learn/scripts/run_formal_gcd.sh` | `reset=1` ⇒ `resp_val=0` (`sat -tempinduct`) |
| Wrapper sby | `learn/formal/gcd_safety.v` | pronto se installi `sby` |

---

## PEX (OpenRCX · FasterCap · Raphael · StarRC)

Finish ORFS già chiama OpenRCX se `RCX_RULES` è settato (`platforms/nangate45/rcx_patterns.rules`). Il report `openrcx_*.json` conta `*D_NET` / `*CAP` / `*RES` sul SPEF reale.

FasterCap/Raphael non estraggono il full-chip: il tutorial 2-wire (`run_analytical_pex.py`) dà Cg/Cc in fF su geometria M2 FreePDK45-like, confrontabile in ordine di grandezza col SPEF.

---

## Layout (Magic · Netgen · KLayout · open_pdks)

KLayout è l’unico percorso **signoff** su questo PDK (runset vendored `learn/platforms/nangate45/lvs/FreePDK45.lylvs`). Magic/Netgen restano probe: utili su Sky130 via open_pdks, non su Nangate45.

---

## Power: vectorless + dynamic

Vedi [vectorless-power.md](./vectorless-power.md). OpenSTA 26Q2: usare `read_vcd`, **non** `read_power_activities` (arity rotta).

Engine IR/EM Apache-2.0 sulla stessa mesh: [vyges-em-ir.md](./vyges-em-ir.md) (binario reale, non un reimplement).
I(t) per pin + waveform + heatmap: [dynamic-ir.md](./dynamic-ir.md). Landscape OSS: [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

---

## Verifica

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_tool_matrix.sh
test -f learn/sim/reports/vectorless_flowlab.json
test -f learn/sim/reports/yosys_equiv_flowlab.json
test -f learn/sim/reports/vyges_em_ir_flowlab.json
test -f learn/sim/reports/dynamic_ir_flowlab.json
test -f learn/platforms/nangate45/lvs/FreePDK45.lylvs
```

Cross-ref: [signoff-matrix.md](./signoff-matrix.md) · [extended-flow.md](./extended-flow.md) · [tool-hooks.md](./tool-hooks.md)
