# ASAP7 layer 1 import plan

Living plan. Not a frozen DSE plan. Not a course switch.
Not a product win. Do not restamp gold Dynamic IR **45.298 mV**.
Do not overwrite `nangate45/gcd/flowlab`. Do not write `.lvs.ok`.

Question: the leftover that this image cannot close is **layer 1**
(the academic PDK: techlib, BSIM-CMG, Calibre). How is it shipped,
what can we import here, and what stays gated?

**Answer: layer 1 is two downloads, not one.** GitHub ships the
public half (`asap7_pdk_r1p7`: HSpice `.pm`, Virtuoso `cdslib`,
docs, a **placeholder** `calibre/`). The real DRC/LVS/xACT decks
are an encrypted tarball from [asap.asu.edu](https://asap.asu.edu/)
and need Calibre **2017.3 / 2017.4**. This Cloud image can fetch
the GitHub half. It cannot fetch or run the ASU decks.

Checked on disk 2026-09-05.

---

## What layer 1 is

From `README_ASAP7PDK_INSTALL_201210a.txt` and
`Calibre_Usage_Instructions.txt` in
[asap7_pdk_r1p7](https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7):

| Piece | Path in the PDK | On GitHub? | On this image after fetch? |
|---|---|---|---|
| HSpice BSIM-CMG (level 72) | `models/hspice/7nm_{TT,SS,FF}_160803.pm` | Yes | Yes (gitignored) |
| Virtuoso techlib | `cdslib/asap7_TechLib_10/` (RVT/LVT/SLVT/SRAM) | Yes | Yes (unused: no Virtuoso) |
| Virtuoso setup | `cdslib/setup/` (`cds.lib`, `setup_asap7.csh`) | Yes | Yes (unused) |
| DRM + paper | `docs/asap7_drm_201207a.pdf`, `mej_paper_asap7.pdf` | Yes | Yes |
| Sample OA cells | `asap7ssc7p5t_05/` | Yes | Yes (OA, not ORFS) |
| Calibre DRC/LVS/xACT `.rul` | `calibre/ruledirs/{drc,lvs,rcx}/` | **Placeholder only** | **No decks** |
| Calibre runsets | `calibre/rundirs/` | Placeholder README | No |

The placeholder `calibre/ruledirs/*/README.txt` says: download from
asap.asu.edu and **replace** the GitHub `calibre/` tree.

ASU page: decks are **encrypted**. Register to download. Hammer
and the install note pin Calibre `aoi_cal_2017.4_19.14`. xACT in
2018.2 was already incompatible.

---

## How to import (this repo)

Do not vendor the PDK into git. Same pattern as CCS/CDL extras.

```bash
# GitHub half (~9.5 MB). Safe. Repeatable.
./learn/scripts/fetch_asap7_pdk.sh

# Inventory (gitignored report). Never stamps .lvs.ok.
PYTHONPATH=learn:learn/scripts python3 learn/scripts/lab_asap7_pdk.py
```

Views land under `learn/lab/asap7/pdk/` (gitignored).
Report: `learn/sim/reports/lab_asap7_pdk.json` (gitignored).

### Drop the ASU Calibre tarball when you have it

This image has no tarball and no Calibre binary. On a machine that
does:

1. Register at https://asap.asu.edu/ and download the Calibre decks.
2. Unpack. You should see
   `calibre/ruledirs/drc/drcRules_calibre_asap7.rul`,
   `calibre/ruledirs/lvs/lvsRules_calibre_asap7.rul`,
   `calibre/ruledirs/rcx/rcxControl_calibre_asap7.rul`.
3. Point the fetch at that tree (does **not** commit the decks):

```bash
ASAP7_CALIBRE_SRC=/path/to/unpacked ./learn/scripts/fetch_asap7_pdk.sh
PYTHONPATH=learn:learn/scripts python3 learn/scripts/lab_asap7_pdk.py
```

`lab_asap7_pdk.py` sets `calibre_ready` only when those three `.rul`
files exist. Even then: no Calibre 2017 binary here means
`calibre_ran=false`. Do not write `.lvs.ok`. Do not treat KLayout
79% cell-vs-CDL as Calibre.

---

## What we can do with the GitHub half (lab only)

| After fetch | Can do | Cannot do |
|---|---|---|
| Three `.pm` cards | Read BSIM-CMG params; **Xyce** inverter after a `level 72→107` patch | Drop into ngspice as-is. Run HSpice (not installed). Krylov on AES |
| `cdslib/` | Inventory transistor flavors | Open Virtuoso. Schematic → layout academic flow |
| DRM PDF | Read rules that the community KLayout deck lags | Calibre DRC |
| Placeholder `calibre/` | Prove the decks are missing | DRC / LVS / xACT |

Live Xyce check (this image): `lab_asap7_spice.py` joins HSpice
`+` cards, retargets **level 72 → 107** (Xyce BSIM-CMG v107), and
runs a tiny RVT inverter. Not AES. Not the Nangate IR reference
45.298 mV. Studio `/lab` `#asap7` and suite hook `asap7_layer1`
show the inventory, missing Calibre decks, and the Xyce result.
Wrapper: `run_lab_asap7_pdk.sh`.

---

## Fit to the three surfaces

Unchanged. Course and product stay Nangate45. Layer 1 is Lab
collateral. An ASAP7 Calibre run, if it ever happens on another
machine, is still not a `win_rule.py` win.

---

## Honest leftover after this import

| Leftover | Status |
|---|---|
| GitHub PDK clone | Closable here — `fetch_asap7_pdk.sh` |
| HSpice `.pm` on disk | Closable here |
| ASU Calibre tarball | Gated: register + encrypted download |
| Calibre 2017.3/2017.4 | Gated: not in this image |
| Virtuoso / Innovus academic flow | Gated: commercial tools |
| ngspice on these cards | Wrong tool |
| Product win / course swap | Forbidden |

Sources: ASU install note, Calibre usage note, asap.asu.edu,
UCSC chip-tutorials `asap7.md`, Hammer ASAP7 README.
