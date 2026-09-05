# ASAP7 research (investigation)

Living note. Not a frozen DSE plan. Not a course switch.

Question: ASAP7 looks like the best open kit for *our* research.
Is that true, and which open-source projects actually enlarge it?

**Answer: yes for Lab / EDA / FinFET research. No as a replacement
for the Nangate45 course or product campaign.** ASAP7 is the strongest
*predictive* open PDK in this tree (CCS, corners, multi-VT, FinFET
BEOL). It is not manufacturable. Do not migrate the course. Do not
promote an ASAP7 finish to a product win. Do not restamp gold
Dynamic IR **45.298 mV**. Do not overwrite `nangate45/gcd/flowlab`.

Checked on disk in this tree (2026-09-05). No ASAP7 `make finish`
was run for this note.

---

## What ASAP7 is

ASAP7 is a **predictive 7 nm FinFET** PDK from ASU (Lawrence Clark)
with ARM Research (2016). BSD-3. Official line from ASU: academic
and research aid only; designs are **not manufacturable**. No foundry
sign-off, no MPW, no Tiny Tapeout.

Paper to cite if we publish on it:

L. T. Clark et al., “ASAP7: A 7-nm finFET predictive process design
kit,” *Microelectronics Journal*, vol. 53, pp. 105–115, Jul. 2016.

Umbrella repo: https://github.com/The-OpenROAD-Project/asap7
ASU page: https://asap.asu.edu/

This ORFS tree ships a **slim pack** at
`tools/OpenROAD-flow-scripts/flow/platforms/asap7/` (PDK 1.7,
7.5-track cells v28). That is enough to run digital P&R. It is not
the full Calibre / Virtuoso / HSpice kit.

---

## What is actually better here than Nangate45 / sky130

On disk in this checkout:

| Thing | ASAP7 here | Nangate45 here | sky130hd here |
|---|---|---|---|
| Device | Predictive FinFET | Teaching planar 45 nm | Real 130 nm CMOS |
| Tapeout | None | None | Yes (test chips) |
| Liberty corners | FF / TT / SS (`CORNER=BC/TC/WC`) | One `typical.lib` | One `tt_025C_1v80` |
| Voltages | 0.77 / 0.70 / 0.63 V | One typical | 1.8 V typical |
| VT flavors | RVT, LVT, SLVT, SRAM (`ASAP7_USE_VT`) | One | HD (HS is a second pack) |
| CCS (`output_current`) | **Yes** — RVT FF only (5 unique libs; SIMPLE is a symlink) | No (PTM sidecar, leftover) | No |
| NLDM files | 106 | 1 | 1 |
| Designs in ORFS | 19 (gcd, gcd-ccs, aes, ibex, jpeg, riscv32i, mock-cpu, swerv, uart, ethmac, cva6, …) | Course + camp set | gcd, aes, ibex, jpeg, … |
| SRAM | FakeRAM2.0 blackboxes | Dummy / none | Real `sky130ram` |
| KLayout DRC | `asap7.lydrc` (community, FEOL on) | `FreePDK45.lydrc` | `sky130hd.lydrc` (`FEOL = false`) |
| LVS in this pack | **None** | Course KLayout LVS | `sky130hd.lylvs` |
| SPICE in this pack | **None** | PTM 45 | Not installed here |

That is why ASAP7 is the right *research* base: it is the only
platform in this tree with official CCS tables, a real slow/fast
pair, and a FinFET metal stack. Those are exactly the leftovers
that stay gated on Nangate45 (`learn/reference/gaps.md`).

ORFS GCD on ASAP7 is a smoke test: `clk_period` **310** with liberty
`time_unit` **1ps** (~3.2 GHz period), `PLACE_DENSITY` 0.35. That is
not the course 0.46 ns Nangate tutorial. `gcd-ccs` is the same design
with `LIB_MODEL=CCS`. Default `LIB_MODEL` is still NLDM; `CORNER`
defaults to **BC** (fast), not typical.

IR knobs exist (`PWR_NETS_VOLTAGES`, `IR_DROP_LAYER=M1`). They are
a new extract, not gold 45.298 mV.

---

## What is not better / what is fake

1. **Not silicon.** Numbers are a model of “7 nm-like”, not a foundry.
   Do not sell them as a real 7 nm result.
2. **CCS is partial.** Only RVT + FF. No SS/TT CCS, no LVT/SLVT CCS
   in this pack. `gcd-ccs` exercises that one corner.
3. **27 `*_FAKE.lib` files** for multi-bit FF clustering
   (`CLUSTER_FLOPS=1`). Name is honest: they are fake.
4. **SRAM is FakeRAM2.0**, not a compiled bitcell. Pins and timing
   exist so the flow completes. DRC/LVS around macros is not a
   foundry SRAM signoff. `GDS_ALLOW_EMPTY` includes `fakeram.*`.
5. **No LVS, no `.pm` SPICE** in the ORFS slim pack. Full PDK LVS
   is Calibre SVRF (Hammer: 2017-year Calibre). HSpice BSIM-CMG
   does not drop into ngspice; Xyce needs a model-card patch.
6. **4× scale history.** The ASU / Innovus academic kit sizes LEF
   4× so geometries stay above a 20 nm license floor, then stream
   GDS at 0.25× for Calibre. This ORFS pack already ships **1×**
   tech/cell LEF (`asap7_tech_1x_201209.lef`). Still treat published
   microns with care if mixing ASU 4× collateral and ORFS 1×.
7. **KLayout DRC is community** (`laurentc2/ASAP7_for_KLayout`),
   from `asap7_drm_201207a.pdf`. `OFFGRID = false`. Several via
   width rules are explicitly not checked. It lags Calibre.
8. **No cooked `results/asap7/`** in this tree. Course gold and
   Studio read `nangate45/gcd/flowlab`.
9. **OpenLane files here are experimental** and “not used directly
   by ORFS”. Digital research path is ORFS, not LibreLane/Tiny Tapeout.

---

## Open-source projects that enlarge ASAP7

These are the ones that actually add views, flows, or research
axes — not just “we ran GCD on ASAP7”.

### Kit and cells (use these)

| Project | What it adds |
|---|---|
| [The-OpenROAD-Project/asap7](https://github.com/The-OpenROAD-Project/asap7) | Umbrella. Submodules: PDK 1.7, 7.5T v28, 6T v26, placeholder SRAM. |
| [asap7_pdk_r1p7](https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7) | Full tech: HSpice BSIM-CMG, placeholder Calibre, Virtuoso. GitHub half: `fetch_asap7_pdk.sh`. ASU Calibre tarball still gated. |
| [asap7sc7p5t_28](https://github.com/The-OpenROAD-Project/asap7) | Current 7.5-track library (what ORFS uses). NLDM + CCS archives in the full clone. |
| [asap7sc6t_26](https://github.com/The-OpenROAD-Project/asap7sc6t_26) | 6-track cells for density / track-height studies. Smaller cell set. Not in this ORFS platform. |
| [asap7_sram_0p0](https://github.com/The-OpenROAD-Project/asap7) | Official SRAM macros. Minimal. Usually replaced by FakeRAM. |

### Flow and macros (already wired or easy)

| Project | What it adds |
|---|---|
| [OpenROAD-flow-scripts `platforms/asap7`](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) | **This tree.** 1× LEF, NLDM/CCS, PDN, tapcell, KLayout, 19 designs including `gcd-ccs`. |
| [FakeRAM2.0](https://github.com/maliberty/FakeRAM2.0) (ABKGroup + Matt’s pin-access fork) | Blackbox SRAM/regfile LEF+lib+Verilog. Config in `fakeram.cfg`. How swerv / riscv32i-mock-sram finish. |
| [laurentc2/ASAP7_for_KLayout](https://github.com/laurentc2/ASAP7_for_KLayout) | Source of `asap7.lydrc` / layer views. Open DRC without Calibre. |
| [ucb-bar/hammer](https://github.com/ucb-bar/hammer) ASAP7 plugin | Commercial-tool flow (Genus/Innovus) + 4× GDS downscale (`gdstk`). Dummy SRAMs that **fail** DRC/LVS. Calibre 2017 decks. Documents known DRC noise (FIN.S.1, LVT.W.1, dummy-SRAM M4). |
| [TILOS MacroPlacement ASAP7](https://tilos-ai-institute.github.io/MacroPlacement/Enablements/ASAP7/) | 7.5T RVT + FakeRAM enablement for commercial **and** OpenROAD macro-placement research. |

### Research extensions (papers / forks — not in this pack)

| Work | What it adds | Use here? |
|---|---|---|
| Yang / Lin, APCCAS 2024 — BPR + backside metal | Buried power rail + backside stack; 6T library; ~13% area, better WNS/TNS/WL | Lab DTCO. New tech files. Not a drop-in for this ORFS platform. |
| APCCAS 2025 — PowerVia | Backside PowerVia 6T/5T libraries; large IR-drop cuts (paper: 64–82%) | Lab IR / PDN research. Same: new PDK fork. |
| Hsu, engrXiv 2026 — NL → 1.55 GHz GDS | RV32I on ORFS ASAP7, public LLM agent | Literature. **Not a product proposer.** `AGENTS.md` forbids LLM/RL/GNN proposers as product. |
| OpenRAM | Real SRAM compiler | No official ASAP7 tech mapping. A port would be a project, not a download. |
| Xyce + patched BSIM-CMG | Transistor SPICE without HSpice | Lab only. ngspice is the wrong first tool. |

OpenLane/LibreLane stay sky130/gf180/IHP-first. ASAP7-on-OpenLane in
this tree is a leftover experiment.

---

## Fit to this repo’s three surfaces

| Surface | ASAP7 fit |
|---|---|
| **Course / Studio / FlowLab** | **No.** Locked to Nangate45. Gold IR **45.298 mV**. Lessons, leftover chips, `signoff_all` assume one GCD. |
| **Product** | **No.** Wins are physical knobs on official Nangate netlists, fixed die, real finish (`win_rule.py`). An ASAP7 PPA number is a different die and a predictive kit. |
| **Lab** | **Yes — best open FinFET / CCS / MCMM bench we already have.** Separate variant. New goldens if we ever cook. Never overwrite `gcd/flowlab`. |

Scripts (`learn/scripts/run_*.sh`, `learn/dse/designs.py`) hard-code
or default `nangate45`. A lab track means new wrappers, not a
`if design ==` in the tuner.

---

## Lab track (open)

Wrapper: `scripts/run_lab_asap7.sh`. Space: `learn/dse/asap7_lab.py`.
Kit: [`learn/lab/asap7/README.md`](../learn/lab/asap7/README.md).
Variants are `lab_asap7_*`. Default cook is gcd / TC / RVT / NLDM /
7.5-track.

1. Own variant name (not `flowlab`, not `learn`, not `base`).
2. Do not call `signoff_all` from a cook. Do not write Nangate paths.
3. CCS vs NLDM is a first-class knob (`LIB_MODEL`, `gcd-ccs`).
   Report which one. Partial CCS is leftover, not “CCS closed”.
4. IR / EM are a new mesh. `comparable_to_gold_ir` is false vs 45.298.
5. FakeRAM and `*_FAKE.lib` stay named leftovers.
6. 6-track is fetch-gated leftover (6.8 GB upstream). Not a finish.
7. Full LVS/SPICE wants the ASU Calibre tarball + Calibre 2017 or
   a patched Xyce card. This Cloud image can clone the GitHub PDK
   (`learn/lab/asap7/pdk/`). It has neither Calibre decks nor a
   2017 license. See [`asap7_layer1_plan.md`](asap7_layer1_plan.md).
8. Do not launch AES finish “just to see”. GCD / `gcd-ccs` first.
9. Do not import BPR/PowerVia or LLM proposers into product.

---

## Recommendation

| Option | Verdict |
|---|---|
| Replace Nangate45 course + product with ASAP7 | **No.** Loses locked GCD, gold IR, all product wins. Predictive ≠ foundry. |
| Treat ASAP7 as the default *Lab* PDK for FinFET / CCS / corner / PDN research | **Yes.** Best open candidate in this tree for that job. |
| Pull 6T, FakeRAM, KLayout DRC, Hammer notes, BPR/PowerVia papers as lab reading | **Yes.** They enlarge the kit. They do not close course leftover. |
| Use ASAP7 CCS to “close” the Nangate CCS leftover | **No.** Different PDK. Official Nangate CCS stays form-gated. |
| LLM / agent proposer on ASAP7 as product | **No.** Lab literature only. |

ASAP7 is the best *open research FinFET kit* we already ship.
It is not a better course, not a tapeout PDK, and not a product
win surface.

Do not mix ASAP7 into the Nangate45 course. Do not recook locked
`gcd/flowlab`. Do not restamp gold Dynamic IR **45.298 mV**.

Live lab cooks write GDS under `results/asap7/<design>/lab_asap7_*`.
`learn/sim/reports/lab_asap7.json` is the last cook (gitignored).
Do not freeze those numbers. Do not copy `6_report.json` into reports.
Check with `learn/scripts/test_asap7_e2e.py`.

How the full academic kit is layered, and how to close (or name)
each leftover: [`asap7_close_plan.md`](asap7_close_plan.md).

---

## Backside PDN forks (BPR / PowerVia) — how they fork, how we compare

Living note (2026-09-05). Inspected clone of
[`VLSIDA/asap7_bb_pdk`](https://github.com/VLSIDA/asap7_bb_pdk)
(forked from [`YZU-EDALAB/asap7_bb_pdk`](https://github.com/YZU-EDALAB/asap7_bb_pdk)).
Not a frozen plan. Lab only. Not a product win. Not a course swap.
Do not restamp gold Dynamic IR **45.298 mV**.

### Two paper lines on the same ASAP7 base

| Line | Paper | Public fork | What changes vs ORFS 7.5T |
|---|---|---|---|
| **BPR + BSM** | Yang et al., APCCAS 2024 ([doi](https://doi.org/10.1109/apccas62602.2024.10808511)) | `asap7_bb_pdk` | Process tweaks + backside layers + **BPR6L** 6-track lib |
| **PowerVia** | Yu et al., APCCAS 2025 ([doi](https://doi.org/10.1109/apccas67402.2025.11377494)) | **No public repo found** | Backside metal + PowerVia rules + **PV-6T / PV-5T** libs (241 cells each) |

Both start from ASAP7 academic PDK (bb fork cites **r1p5**; this tree
ships **r1p7** via ORFS). Neither is a drop-in knob on
`platforms/asap7`. They are **DTCO forks**: new tech, new cells, new
PDN scripts, usually a commercial P&R stack.

`asap7sc6t_26` (upstream 6-track, `fetch_asap7_sc6t.sh`) is **not**
the same as BPR6L: standard 6T cells without buried rails or backside
metal. W11 (6-track ORFS platform) stays gated separately from this
backside fork.

### Three-layer fork anatomy (`asap7_bb_pdk`)

Papers do not “add an analyzer at the end”. They replace three layers.

**Layer 1 — Process / tech file**

Fork README lists modifications on top of base ASAP7:

- Single diffusion break (vs multi-break).
- Fin depopulation (fin height 32 nm → 49 nm).
- Contact over active gate (COAG).
- Buried power rail (BPR) + backside metal (BSM).

New layers in `tf/asap7_bb_TechLib.tf` (not in ORFS frontside stack):

| Layer | Role |
|---|---|
| `BPR` | Buried power rail inside stdcell footprint |
| `VBPR` | Via to BPR |
| `BM1`, `BM2` | Backside metal stack |
| `TSV` | Front↔back connection (StarRC `TSV.nxtgrd`) |

Frontside M1–M9 + Pad remain for signals; VDD/VSS delivery moves to
BPR → backside mesh.

**Layer 2 — Standard cell library**

```
layout/asap7bb6t.gds    # BPR6L macro GDS
layout/asap7bb6t.cdl    # 216 .SUBCKT entries (inspected 2026-09-05)
```

Cells are named `*_ASAP7_6t_fix` with BPR at top/bottom cell edges.
This is a **new lib**, not a reskin of `asap7sc7p5t_28` or
`asap7sc6t_26`.

**Layer 3 — Flow + PDN scripts**

Toolchain in the fork: **DC → ICC2 → StarRC → Calibre**. Not OpenROAD.

ICC2 `run.tcl` builds backside PDN explicitly:

1. PG **ring** on `BM2` / `BM1` (backside metals).
2. PG **rails** on `BPR` (`create_pg_std_cell_conn_pattern -layers {BPR}`).
3. PG **mesh/stripes** on `BM1`.
4. Signal routing on frontside M1–M5.

ORFS baseline (`openRoad/pdn/grid_strategy-M1-M2-M5-M6.tcl`) uses
M1 followpins → M5/M6 straps on the **front**. That is the structural
difference papers exploit for routability and IR.

Supporting artifacts:

| Path | Role |
|---|---|
| `ICC2/ASAP7_BPR_112.tluplus.gz` | Parasitics with backside layers |
| `RC/layermap.map` | StarRC map includes BPR, BM1, TSV |
| `calibre/calibreDRC.rul` | DRC (Innovus→ICC2 translation; README warns gaps) |
| `models/model_card.pm` | Modified BSIM-CMG card |

### Paper analysis methodology (what to copy)

Both lines use the same **A/B chip study**, not a package ladder alone.

**BPR/BSM (2024)** — same benchmark, baseline vs BPR6L:

- Area −13.1%, WNS −9.4%, TNS −42%, wire length −5.8%, via −19.9%.

**PowerVia (2025)** — adds explicit **max static IR drop**:

- PV-6T: area −15–18%, IR −64–79%.
- PV-5T: area −28–32%, IR −71–82%, util up to 94%, fmax ×1.39 avg.

Common recipe:

1. Same RTL / benchmark block.
2. Two platforms: **7.5T frontside baseline** vs **6T/5T backside fork**.
3. Same utilization target where possible.
4. Report **area, WNS/TNS, wire length, vias, power, max static IR,
   frequency** together — honest win/lose.
5. IR from **on-die power grid analysis** (ICC2 / Voltus class), not
   from an external lumped VRM→board ladder.

Our `lab_asap7_pkg` compact ladder is **system/package** level. Paper
IR numbers are **on-die backside grid** level. Keep them separate.

### Three IR tiers for PDflow lab ASAP7

| Tier | Question | This repo today | Paper fork |
|---|---|---|---|
| **On-die frontside** | M1/M5 grid droop on 7.5T cook? | `6_report` PDNSim (`ir_drop_vdd_mv` in folio) | Baseline in A/B |
| **On-die backside** | BPR/BM mesh droop? | **GAP** (no bb platform) | ICC2 PG + static IR |
| **System/package** | VRM→board→pkg bump? | `lab_asap7_pkg` lumped ladder | Not their focus |

Do not compare tier-3 droop (~1.6 mV compact) to tier-2 paper claims
(64–82% IR reduction). Different physics, different models.

### What we can take from them (repo-law safe)

**Now — inventory + methodology (no ICC2 cook required)**

1. **Baseline row** — keep 7.5T gcd folio (310→430→480 ps ladder) with
   area, power, leakage, IR, WNS from live `6_report`.
2. **Fork inventory** — optional `fetch_asap7_bb_pdk.sh` →
   `learn/lab/asap7/bb_pdk/` (gitignored), report layer diff vs ORFS,
   cell count, tool requirements (ICC2, Calibre 2017, StarRC).
3. **A/B schema in folio** — name a second platform slot
   `lab_asap7_bb_*` as **GAP** until a real backside platform exists;
   never fake paper IR numbers.
4. **Metric bundle** — always report area, power, leakage, IR together
   (same discipline as papers and `AGENTS.md`).
5. **Leftover honesty** — `product_win: false`,
   `comparable_to_gold_ir: false`, Calibre/ICC2 gated forever on this
   image.

**Later — W12 backside lab track (distinct from W11 standard 6T)**

W11 = second ORFS platform for **standard** `asap7sc6t_26` (site,
tracks, tapcell, frontside PDN). Still no BPR.

W12 (proposed) = backside fork track:

1. Inventory `asap7_bb_pdk` (layers, BPR6L CDL/GDS, ICC2 scripts).
2. If ICC2 + Calibre available: cook gcd on BPR6L, static IR from
   commercial PG analysis.
3. If OpenROAD ever exposes backside layers: port PDN TCL analog
   (BM ring, BPR followpins) — until then ICC2 is the honest path.
4. Folio compares **7.5T frontside vs 6T BPR** on same RTL; report
   deltas like the papers, live rows only, no gold stamp.
5. Optional: `write_pg_spice` mesh to couple on-die backside with
   `system_pdn_hier` — only after tier-2 mesh exists.

**Do not**

- Import BPR/PowerVia into product `win_rule.py`.
- Swap course / FlowLab to backside ASAP7.
- Treat `fetch_asap7_sc6t.sh` as BPR (it is standard 6T).
- Claim paper IR cuts without a backside cook and grid analysis.

### Sources (primary)

- Yang et al., APCCAS 2024 — BPR + backside metal; `asap7_bb_pdk`.
- Yu et al., APCCAS 2025 — PowerVia; no public kit found.
- Tong et al., ISCAS 2025 — 4.5-track BPR library on extended ASAP7.
- Repo close path: [`asap7_close_plan.md`](asap7_close_plan.md) §5 (6T)
  and §BPR.
- Live 7.5T e2e + package hook: [`asap7_e2e_plan.md`](asap7_e2e_plan.md).
