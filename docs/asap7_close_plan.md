# ASAP7 leftover close plan

Living investigation. Not a frozen DSE plan. Not a course switch.
Not a product win surface. Do not restamp gold Dynamic IR **45.298 mV**.
Do not overwrite `nangate45/gcd/flowlab`.

Question: the leftover list on the lab ASAP7 track looks like we
are missing a kit that “the people who researched this PDK” already
had. How did they structure it, and what can we actually close here?

**Answer: they had three layers, not one slim pack.** The academic
kit is structured. This Cloud image only has layer 3. Several leftovers
are **by design** in every published open flow (FakeRAM, no foundry
LVS, 310 ps as a smoke SDC). Others are **packaging**: CCS archives,
CDL, Calibre decks sit in the full clone / ASU download, not in ORFS.

Checked on disk 2026-09-05 plus public sources named below.

---

## Three layers (this is the structure)

| Layer | What it is | Who ships it | In this VM? |
|---|---|---|---|
| **1. Full PDK** | Virtuoso techlib, HSpice BSIM-CMG (`.pm`), Calibre DRC/LVS/xACT | [asap7_pdk_r1p7](https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7) + **Calibre tarball from [asap.asu.edu](https://asap.asu.edu/)** (not on GitHub) | No |
| **2. Cell library** | 7.5T v28: LEF, GDS, Verilog, **CDL**, QRC, datasheets, NLDM+CCS as `.7z` | [asap7sc7p5t_28](https://github.com/The-OpenROAD-Project/asap7) | Partial (ORFS extracted views only) |
| **3. Digital smoke pack** | LEF + Liberty + GDS + FakeRAM + KLayout + PDN | [ORFS `platforms/asap7`](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) | **Yes** — `tools/OpenROAD-flow-scripts/flow/platforms/asap7/` |

ORFS README on disk: “minimal file set require for designs, packaged
under OpenROAD” plus FakeRAM “to complete OpenROAD design flow”.
That sentence is the leftover policy of the OpenROAD project, not a
gap we invented.

The structured *commercial-tool* twin is [Hammer ASAP7](https://hammer-vlsi.readthedocs.io/en/stable/Technology/ASAP7.html):
Genus/Innovus, 4× LEF then `gdstk` shrink, MMMC corners, Calibre
**2017.3 only**, dummy SRAMs that **fail** DRC/LVS on purpose.

MSE 2017 (Clark / Vashishtha / Harris) is the paper that describes
layer 1+2 as a complete academic flow: schematic → layout → DRC/LVS
→ Liberate → Innovus APR → Calibre PEX → HSpice. PDF:
https://pages.hmc.edu/harris/research/asap7.pdf

---

## What “closed” means here

- **Close** = a leftover becomes a named, runnable lab path with
  honest numbers. Still not a product win.
- **Leftover forever** = the research community also left it open
  (no foundry, no real SRAM compiler, Calibre license, …).
- Do not stamp ASAP7 goldens. Live GDS only (`test_asap7_e2e.py`).

FO4 from MSE 2017 (extracted layout, 0.7 V): RVT **8.1 ps**, LVT
**6.8 ps**, SLVT **6 ps**. Use that as a budget, not as a gold.

---

## Leftover → how they close it → what we do

### 1. Timing open at 310 ps

**What we saw (live, not gold):** gcd NLDM TC WNS −116 ps; CCS BC
−22 ps; WC −312 ps; uart 270 ps WNS −18 ps. All open.

**What ORFS actually does:** `designs/asap7/gcd/constraint.sdc` is
`clk_period 310` (liberty `time_unit` 1 ps). CI `rules-base.json`
**allows** `finish__timing__setup__ws >= -32.2` (gcd) and
`>= -37.9` (gcd-ccs). They never claimed 310 ps is closed. Default
ORFS `CORNER` is **BC** (FF). Our TC cook is a slower corner than
their smoke.

**What papers do:** Hsu, engrXiv 2026, RV32I on ORFS ASAP7: first
close at **676 ps** (WNS +9.17 ps, 1.50 GHz); tighter 640 ps misses
(WNS −6.65 ps); they publish `report_clock_min_period` **646.65 ps**
= 1.55 GHz. VerCore (tanfer-meta) closes SLVT at **676 ps**.
Nobody closes a combinational-heavy GCD at 310 ps (~38 FO4) on RVT
TT with 20% I/O delay.

**Close path (lab, no gold):**

1. Keep 310 ps as the ORFS smoke SDC. Report it as **open**.
2. Add a live `period_min_ps = clk_ps + max(0, -wns_ps)` and
   `fmax_ghz = 1000 / period_min_ps`. That is how Hsu/ORFS talk.
3. Optional: one extra cook with `LAB_CLK_PS` set to
   `ceil(period_min)` (or 430 ps ≈ TC WNS −116 + 310) to **show**
   WNS ≥ 0. Same die. Not a product win.
4. WC cannot share 310 ps. SS / 0.63 V / 100 °C is a different
   budget (Hammer setup corner). Either a longer SDC or leftover.

Do not restamp 45.298. Do not treat fmax as a product win.

### 2. WC die overflows CTS (65% util)

**What we saw:** DPL-0036 on `dpath.a_reg.out[0]` after setup
repair at 93% util. GDS only with `CORE_UTILIZATION=40`.

**What they do:** Hammer MMMC uses SS for **setup** and a floorplan
that is not a 65% GCD smoke. ORFS GCD `CORE_UTILIZATION=65` is
sized for BC/TC, not for a 312 ps pile of repair buffers.

**Close path:** wrapper already passes `CORE_UTILIZATION` with no
`if design ==`. Default WC lab cooks to 40. Leftover stays named:
“310 ps + 65% die fails legalization at SS”.

### 3. LVS missing

**What they have:** Calibre `lvsRules_calibre_asap7.rul` — **not
in the GitHub PDK**. Download from asap.asu.edu; replace the
placeholder `calibre/` tree
([Calibre_Usage_Instructions.txt](https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7/blob/main/Calibre_Usage_Instructions.txt)).
Cell **CDL** lives in `asap7sc7p5t_28/CDL/`. Hammer: Calibre
**2017.3 only**. SiliconCompiler `lambdapdk` vendors the CDL
(`asap7sc7p5t_28_R.cdl`). vibeic-eda 0.2.25 reports KLayout
device-LVS **159/208 (76%) MATCH** on RVT TT — leftover, not
Calibre.

**On disk here:** no `*.cdl`, no `*lvs*` under
`platforms/asap7/`.

**Close path:**

| Step | Needs | Closes? |
|---|---|---|
| Fetch `asap7sc7p5t_28` CDL + Verilog | git, ~library clone | Netlist reference |
| Calibre nmLVS + ASU decks | Calibre 2017 + ASU tarball | Real LVS (this image: **no**) |
| KLayout/netgen on CDL (vibeic / lambdapdk) | Open decks, expect <100% | Lab leftover-named LVS |
| FakeRAM / `*_FAKE.lib` cells | LVS BOX / `GDS_ALLOW_EMPTY` | Never clean |

This Cloud image cannot run Calibre. Do not claim LVS closed.

### 4. CCS only RVT + FF

**On disk:** `lib/CCS/` is AO/INVBUF/OA/SIMPLE/SEQ **RVT FF only**
(SIMPLE has a 250407 symlink). 106 NLDM files cover all VT ×
corners.

**What they have:** ASU page: “Full CCS liberty files”. v28
`LIB/CCS/*.7z` — unpack with `p7zip`. ORFS slim pack did not
extract TT/SS or LVT/SLVT CCS.

**Close path:** fetch `asap7sc7p5t_28`, `7z x` CCS for TT/SS and
other VT, point `platforms/asap7/config.mk` at them **or** keep
them under `learn/lab/asap7/ccs/` (gitignored) and pass
`LIB_DIR`. Then `LIB_MODEL=CCS CORNER=TC` stops being a refuse.
Until those files exist, the refuse in `asap7_lab.py` stays.

Do not use ASAP7 CCS to “close” the Nangate CCS leftover.

### 5. 6-track is not a finish

**What they say:** UCSC chip-tutorials: “For digital flows you
almost always want `asap7sc7p5t_28`. The 6-track library exists
for area studies.” Repo: [asap7sc6t_26](https://github.com/The-OpenROAD-Project/asap7sc6t_26).
Liberty is `.7z`. ORFS platform is 7.5T sites/tracks/PDN.

BPR / PowerVia 6T (Yang / Lin, APCCAS 2024–2025;
[asap7_bb_pdk](https://github.com/VLSIDA/asap7_bb_pdk)) is a
**fork** (buried rails, backside metal, ICC2). Not a drop-in
`ASAP7_TRACK=6`.

**Close path:** `learn/scripts/fetch_asap7_sc6t.sh` already copies
views. A finish needs a second platform (site, tracks, tapcell,
filler, GDS map, PDN). That is a lab project, not a knob.
Leave `ASAP7_TRACK=6` refused until that platform exists.

### 6. FakeRAM / riscv32i-mock-sram

**What they do:** ORFS, Hammer, and TILOS MacroPlacement all use
[FakeRAM2.0](https://github.com/maliberty/FakeRAM2.0) or Hammer
dummy SRAMs. Hammer README: blank macros, **will not pass DRC &
LVS**. `asap7_sram_0p0` is a placeholder. MSE 2017 SRAM arrays
are custom Virtuoso + Liberate_MX — not in the slim pack.
OpenRAM has **no** official ASAP7 tech mapping.

**Close path:** keep FakeRAM named leftover. Do not cook
`riscv32i-mock-sram` as a “real SRAM” finish. A real compiler
is a new project.

### 7. uart `slang.so` / `EQUIVALENCE_CHECK`

**What they do:** ORFS uart sets `SYNTH_HDL_FRONTEND=slang` only
to pass `VERILOG_TOP_PARAMS = DATA_WIDTH 8`. The RTL default is
already 8. `minimal` is “not included in CI”.

**Close path (already live):**
`SYNTH_HDL_FRONTEND= EQUIVALENCE_CHECK=0`. Optional: install
yosys-slang if we want the official frontend. eqy is a separate
leftover.

### 8. Community KLayout DRC (33 items on gcd)

**What they do:** `asap7.lydrc` from
[laurentc2/ASAP7_for_KLayout](https://github.com/laurentc2/ASAP7_for_KLayout).
Hammer lists **expected** Calibre noise (FIN.S.1, LVT.W.1,
dummy-SRAM M4, via AUX). Community deck lags Calibre; several
via-width rules are off.

**Close path:** keep counts leftover-named. Calibre close = layer 1
decks + 2017 tool. Do not treat KLayout 33 as a fail or a gold.

### 9. SPICE / IR transistor-level

**What they have:** `models/hspice/7nm_{TT,SS,FF}.pm` (BSIM-CMG).
ngspice is the wrong first tool. Xyce needs a model-card patch
(already noted in `docs/asap7_research.md`).

**Close path:** lab only, after PDK clone. Do not run Krylov on
AES. Do not restamp gold IR.

### 10. AES / heavy designs

ORFS has aes / ibex / jpeg / cva6 / swerv. We refuse them without
`ALLOW_HEAVY_ANALYSIS=1`. Hsu’s 1.55 GHz core is a **small**
RV32I, not `riscv32i-mock-sram` and not AES. Do not launch AES
“just to see”.

### 11. `minimal` skips metrics

ORFS design: `SKIP_REPORT_METRICS=1`, empty SDC, GUI smoke.
CI excludes it. Not an e2e QoR path.

### 12. MMMC (they are more structured here)

Hammer defaults:

| Corner name | Type | V / T |
|---|---|---|
| `PVT_0P63V_100C` | setup | 0.63 V / 100 °C (our WC / SS) |
| `PVT_0P77V_0C` | hold | 0.77 V / 0 °C (our BC / FF) |

We cook **one** corner per variant. That is leftover vs MMMC, not
vs “no corners”. Close path: report the pair (WC setup + BC hold)
on the same netlist, still not a product win.

---

## Order of work (lab only)

Do one heavy cook at a time. No AES. No gold stamp.

1. **Report fmax / `period_min`** on the seven live GDS (no recook).
2. **One relaxed-clock gcd TC** (`LAB_CLK_PS` ≈ 430) to show WNS ≥ 0
   if we want a closed-timing *picture*. Honest leftover: different
   SDC than ORFS smoke.
3. **CCS extract** from `asap7sc7p5t_28` `.7z` when `p7zip` is
   present — then drop the RVT+BC refuse.
4. **CDL fetch** for a leftover-named KLayout/netgen LVS. Calibre
   stays gated on the ASU tarball + 2017 license.
5. **6T platform** only if someone wants density studies. Not a
   finish on 7.5T PDN.
6. FakeRAM, BPR/PowerVia, OpenRAM, LLM proposers: leftover /
   literature. `AGENTS.md` forbids LLM/RL/GNN as product.

---

## Sources (primary)

- Clark et al., *Microelectronics Journal* 53:105–115, 2016 — PDK.
- Clark / Vashishtha / Harris, MSE 2017 —
  https://pages.hmc.edu/harris/research/asap7.pdf — full flow.
- https://asap.asu.edu/ — Calibre decks (separate download).
- https://github.com/The-OpenROAD-Project/asap7 — umbrella.
- https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7 —
  install + Calibre usage notes.
- ORFS `platforms/asap7/README.md` and
  `designs/asap7/gcd/rules-base.json` (this tree).
- Hammer ASAP7 plugin README + `defaults.yml` (MMMC, 4×, dummy SRAM).
- UCSC chip-tutorials `asap7.md` — layer map, CCS `.7z`, 7.5T vs 6T.
- TILOS MacroPlacement ASAP7 enablement — FakeRAM2.0.
- Hsu, engrXiv 10.31224/6976, 2026 — 676 ps / 646.65 ps fmax.
- Yang / Lin, APCCAS 2024–2025; `VLSIDA/asap7_bb_pdk` — BPR fork.
- vibeic-eda 0.2.25 — open device-LVS 76% on RVT.

---

## Fit to the three surfaces

Unchanged: course and product stay Nangate45. This plan only
enlarges the **Lab** track. An ASAP7 WNS ≥ 0 at 430 ps is still
not a `win_rule.py` win.
