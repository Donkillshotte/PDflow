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
| [asap7_pdk_r1p7](https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7) | Full tech: HSpice BSIM-CMG, Calibre DRC/LVS/xACT, Virtuoso. Needed for transistor-level work. **Not in this VM.** |
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

## If we open an ASAP7 lab track later

Engineering cost, not slogans:

1. Own variant name (not `flowlab`, not `learn`, not `base`).
2. Do not call `signoff_all` from a cook. Do not write Nangate paths.
3. CCS vs NLDM is a first-class knob (`LIB_MODEL`, `gcd-ccs`).
   Report which one. Partial CCS is leftover, not “CCS closed”.
4. IR / EM are a new mesh. `comparable: false` vs gold 45.298.
5. FakeRAM and `*_FAKE.lib` stay named leftovers.
6. Full LVS/SPICE wants the PDK clone + Calibre or a patched Xyce
   card. This Cloud image has neither.
7. Do not launch AES finish “just to see”. GCD / `gcd-ccs` first.
8. Do not import BPR/PowerVia or LLM proposers into product.

A cheap next measurement, if someone asks to cook: ORFS
`DESIGN_CONFIG=./designs/asap7/gcd/config.mk` then `gcd-ccs`.
One heavy cook at a time. Not this investigation.

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
