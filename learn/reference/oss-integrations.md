# Integrazioni OSS mirate (GCD Nangate45)

Documento di tracciabilità per componenti open-source **integrati o referenziati** nel corso — non un survey esaustivo del mondo EDA.

Legenda:

| Stato | Significato |
|---|---|
| **INTEGRATED** | Nel repo, script/Studio funzionanti |
| **VENDORED** | File copiato da upstream con attribuzione |
| **REFERENCED** | Documentato; esecuzione manuale o futura |
| **GAP** | Noto, non risolto in scope GCD educativo |

---

## Stack core (INTEGRATED)

| Progetto | Ruolo | Path corso |
|---|---|---|
| OpenROAD-flow-scripts 26Q2 | PD ORFS | `tools/OpenROAD-flow-scripts/` |
| OpenROAD / OpenSTA / Yosys | synth→finish | ORFS Makefile |
| KLayout | DRC/LVS/GDS viewer | `make drc`, `make lvs` |
| Icarus Verilog | RTL sim + VCD | `run_rtl_sim.sh` |
| ngspice | System PDN | `system_pdn_hier.py` |

---

## Signoff — gap chiusi in corso

### FreePDK45 LVS runset (VENDORED)

ORFS Nangate45 referenzia `platforms/nangate45/lvs/FreePDK45.lylvs` ma il file **mancava** nel tree upstream — LVS falliva con `No rule to make target ... FreePDK45.lylvs`.

| Item | Dettaglio |
|---|---|
| Upstream | [laurentc2/FreePDK45_for_KLayout](https://github.com/laurentc2/FreePDK45_for_KLayout) · `lvs/lvs_freepdk45.lylvs` |
| Vendored in repo | `learn/platforms/nangate45/lvs/FreePDK45.lylvs` |
| Runtime copy | `run_klayout_lvs.sh` → ORFS `platforms/nangate45/lvs/` + `KLAYOUT_LVS_FILE` |
| Licenza | Vedi repo upstream (FreePDK45 academic) |
| Nota | LVS su GCD completo può ancora **FAIL** educativamente — interpretare `.lvsdb` |

### DRC runset (INTEGRATED)

| Item | Path |
|---|---|
| KLayout DRC | `platforms/nangate45/drc/FreePDK45.lydrc` |
| Parser UI | `learn/scripts/parse_signoff_artifacts.py` |

---

## Packaging / thermal (INTEGRATED proxy)

| Componente | Stato | Script |
|---|---|---|
| System PDN ladder | INTEGRATED | `run_system_pdn.sh` |
| Chip IR mesh | INTEGRATED | `run_chip_pdn_ir.sh` |
| PKG bump edu | INTEGRATED | `run_pkg_bump.sh` |
| PKG RDL edu | INTEGRATED | `run_pkg_rdl.sh` |
| Thermal proxy | INTEGRATED | `run_thermal_signoff.sh` |
| HotSpot / 3D-ICE | GAP | extended-flow §9 |

---

## Non integrati (REFERENCED / GAP)

| Tool | Perché non in scope GCD |
|---|---|
| Verilator + GTKWave | Roadmap sim avanzata; VCD via Icarus ok |
| Magic DRC/LVS | Tech presente, path corso = KLayout |
| Sky130 / gf180 | Altro PDK; corso pinna Nangate45 |
| Xyce | ngspice sufficiente per ladder educativo |
| VoltSpot / HotSpot | Thermal full — solo proxy IR+droop |

---

## Verifica integrazione

```bash
# LVS runset presente (learn/platforms, non tools/)
test -f learn/platforms/nangate45/lvs/FreePDK45.lylvs

# Signoff scripts
./learn/scripts/run_drc_signoff.sh
./learn/scripts/run_klayout_lvs.sh
./learn/scripts/run_signoff_phase2.sh
```

Cross-ref: [signoff-matrix.md](./signoff-matrix.md) · [extended-flow.md](./extended-flow.md)
