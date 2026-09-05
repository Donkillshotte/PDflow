# sky130 integration (investigation)

Living note. Not a frozen DSE plan. Not a course switch.

Question: sky130 is a more complete open PDK. Should this repo
move the course or the product onto it?

**Answer: no, not as a replacement.** Use sky130 later as a *separate*
track if we want that work. Do not migrate the Nangate45 course,
FlowLab lock, or product campaign onto sky130.

Checked on disk in this tree (2026-09-05). No sky130 `make finish`
was run for this note.

---

## What is actually better on sky130

OpenROAD-flow-scripts already ships `sky130hd` and `sky130hs`:

- Designs: gcd, aes, ibex, jpeg, and others under
  `flow/designs/sky130hd/`.
- Stdcell LEF, GDS, CDL, KLayout DRC (`sky130hd.lydrc`) and LVS
  (`sky130hd.lylvs`).
- Real SRAM macros (`sky130ram`) and IO LEF (`sky130io`). Nangate45
  uses dummy pads.
- sky130 is a public process people tape out. Nangate45 / FreePDK45
  is a teaching kit.

That is why it *feels* like the right base.

---

## What is not better in *this* checkout

The copy of sky130 that sits in ORFS here is a slim teaching pack,
not a full `open_pdks` install.

| Expectation | On disk here |
|---|---|
| Many liberty corners (MCMM) | `sky130hd` has **one** stdcell liberty: `sky130_fd_sc_hd__tt_025C_1v80.lib`. Same class of leftover as Nangate `typical.lib`. `sky130hs` has two temperatures, still not a slow/fast pair. |
| Official CCS tables | That HD liberty has **no** `output_current` tables. NLDM, like Nangate. |
| Magic + Netgen “just work” | `magic` and `netgen` are **not on PATH**. `PDK_ROOT` is unset. No sky130 Magic `.tech` in this environment. Nangate45 does ship a `magic.tech` file in ORFS; we still use KLayout for course LVS. |
| Full foundry DRC | `sky130hd.lydrc` turns **FEOL off** (`FEOL = false`). Metal/BEOL checks run; front-end checks do not. |
| A cooked GCD we can compare | **No** `results/sky130hd/` in this tree. Course gold and Studio read `nangate45/gcd/flowlab`. |

Older notes in `learn/reference/remaining-gaps-evaluation.md` §7 say
sky130 would close Magic, Netgen, CCS, and real IO. IO/SRAM yes.
Magic/Netgen/CCS **not in this VM / this ORFS slim pack**. Treat that
section as aspirational, not as what is installed.

ORFS sky130hd GCD uses a **1.1 ns** clock (20% I/O delay), not the
course 0.46 ns Nangate tutorial. Different silicon, different timing
story.

---

## What a switch would throw away

Almost everything we already proved is pinned to Nangate45:

- Locked FlowLab GCD (`results/nangate45/gcd/flowlab/`) and gold
  Dynamic IR **45.298 mV**.
- Product wins and the campaign JSONL (gcd, spi, ibex, aes,
  dynamic_node) on official Nangate dies.
- Studio / signoff wrappers (`run_sta_signoff.sh`, LVS, DRC, ECO,
  IR, PKG). They hard-code `nangate45/gcd`.
- `learn/dse/designs.py`: every registered design defaults to
  `platform="nangate45"`.
- Leftover stamps (must-connect on `DFF_X2`, leftover no MCMM, …)
  are Nangate facts. They do not transfer.

Moving the course to sky130 is a new project: new goldens, new
lessons, new Studio paths, new product campaign. It does not “fix”
the current GCD.

---

## Integration problems (if we added a sky130 track)

These are the real engineering costs, not policy slogans:

1. **Two PDKs in one Studio.** Home, leftover chips, and
   `signoff_all` assume one GCD. A second PDK needs its own variant
   and must not overwrite `gcd/flowlab/`.
2. **Scripts.** Dozens of `learn/scripts/run_*.sh` assume Nangate
   paths, liberty, SDC, and KLayout decks.
3. **IR / EM.** Chip IR, gold mesh, and `em_checked` are Nangate
   extracts. sky130 needs its own mesh and, if we claim EM, its own
   limits — not a guessed copy of Nangate leftovers.
4. **Environment.** A serious sky130 LVS/extract path wants
   `open_pdks` + Magic/Netgen. This Cloud image does not have them.
5. **Honesty tests.** `test_dse_next.py` and `test_signoff_honesty.py`
   refuse a course that *leads* with “switch to sky130”. That is
   deliberate so students do not think PDK-swap closes leftover.

Lesson `07-finish/run.sh` still says “try sky130hd/gcd” as a next
step. That is a post-course hint, not a migration plan.

---

## Recommendation

| Option | Verdict |
|---|---|
| Replace Nangate45 course + product with sky130 | **No.** Loses the locked GCD, gold IR, and all product wins. Does not automatically close leftover. |
| Keep Nangate45; allow ORFS `DESIGN_CONFIG=…/sky130hd/gcd` after the course | **Yes.** Already documented. Do not mix into FlowLab lessons. |
| New, separate sky130 product/lab later | Possible. New goldens, new scripts, new image with `open_pdks`. Not this campaign. |

sky130 is a better *public process kit*. It is not a better *drop-in
base* for the work already on Nangate45.

Do not mix sky130 into the Nangate45 course. Do not recook locked
`gcd/flowlab`. Do not restamp gold Dynamic IR **45.298 mV**.

---

## Other open PDKs (is sky130 “the best”?)

No. There is no single best open PDK. It depends on the job.
Checked against this ORFS tree and public sources (2026-09-05).

| Kit | What it is | Best for | Not best for |
|---|---|---|---|
| **sky130** (SkyWater + Google) | 130 nm CMOS. Manufacturable. | Digital + community + tapeout. Tiny Tapeout default (`sky130A`). OpenLane / LibreLane. ChipFoundry MPW. Most tutorials. | Analog/RF vs IHP. Corners vs gf180 in this tree. Official GitHub still says **not for production**; OK for test chips. Some analog model caveats (weak-inversion PFET notes). |
| **gf180mcu** (GlobalFoundries + Google) | 180 nm MCU CMOS. | More liberty corners **in this ORFS tree** (`ff`/`ss`/`tt`, several temps, 1.8 / 3.3 / ~5 V). MCU / higher-voltage analog. Tiny Tapeout also supports it. | Older, larger node. Smaller community than sky130. Also labeled experimental preview. No `fs`/`sf` in this ORFS pack. |
| **IHP SG13G2** | 130 nm **SiGe BiCMOS**. | Open **analog / RF**: HBTs ~350 GHz fT / ~450 GHz fmax. IHP Open PDK (Apache-2). Tiny Tapeout IHP shuttles exist. This ORFS tree has **slow/typ/fast** stdcell + SRAM liberty (more corners than sky130hd here). IHP’s 2025 MOS-AK talk compares SKY130 / SG13G2 / GF180. | Preview / alpha, not a finished production PDK. Digital community smaller than sky130. No CCS tables in this ORFS pack (NLDM `table_lookup`). Tiny Tapeout IHP chips are on **loan** (IHP property ~2 years); EU/CH shipping. |
| **ASAP7** | Predictive **7 nm FinFET** (ASU / ARM). | Research and EDA benchmarking. FinFET teaching. **This ORFS tree ships a CCS folder** (the only platform here with `output_current`). | **Not manufacturable.** No MPW. Numbers are not a real 7 nm foundry. |
| **Nangate45 / FreePDK45** | Academic 45 nm teaching kit. | **This** course, gold IR, product wins. | Not a foundry-open tapeout PDK. |
| Commercial NDA PDKs | TSMC / GF / … | Industrially more complete. HEP 2025 (open vs commercial **on IHP**): open tools work for proto/teaching; commercial still wins area/power. | Not open. Not in this repo. |

Public sources used: Tiny Tapeout FAQ and shuttle pages; google/skywater-pdk and google/gf180mcu-pdk READMEs; IHP Open PDK + Herman MOS-AK 2025; UCSC chip-tutorials ASAP7 page; ChipFoundry / efabless MPW notes; Analog Zoo gm/ID sky130 caveats.

**Pick by job, not by hype:**

- Best open **digital + community + tapeout access** → sky130.
- Best open **analog / RF** → IHP SG13G2.
- Best open **liberty corners / MCU voltages in this tree** → gf180.
- Best **FinFET / CCS / corner research** (no silicon) → ASAP7.
  See [`asap7_research.md`](asap7_research.md).
- Best base **for this product/course** → still Nangate45.

ORFS here already ships all four open platforms
(`sky130hd`/`hs`, `gf180`, `asap7`, `ihp-sg13g2`). That is an
after-course experiment path, not a reason to migrate the locked
Nangate45 course.
