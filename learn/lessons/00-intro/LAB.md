# LAB 00 — First contact (60–90 minutes)

This is not a “hello world”. At the end of this LAB you know **where** every file lives and **why** Cursor Preview does not show OpenROAD.

## Measurable objectives

- [ ] `--check` all green
- [ ] Can name the 6 macro-stages RTL→GDS aloud
- [ ] Created `learn/workbook/mio-quaderno.md`
- [ ] Can open Desktop (not Preview) and explain the difference
- [ ] Found `gcd.v`, `constraint.sdc`, `floorplan.tcl` without using this file as a map

Time: **60 min** if tools are already installed; **90 min** if this is your first time in the repo.

---

## Part 1 — Environment (10 min)

```bash
./scripts/learn_physical_design.sh --check
openroad -version
yosys -V | head -1
sta -version
klayout -v | head -1
```

Write in your notebook: OpenROAD version (expected `26Q2-…`). If a tool is missing, **stop** and use `learn/reference/debug-playbook.md` toolchain section — do not “try random things”.

Wrapper:

```bash
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --status
```

`--list` must show `00-intro` … `07-finish`. If a lesson is missing, the course is incomplete — not your fault.

---

## Part 2 — Folder scavenger hunt (20 min)

Open a file manager or `ls`. **Without** copy-pasting paths from here, find:

| # | What | Path you found |
|---|---|---|
| 1 | GCD RTL | |
| 2 | **Tutorial** `config.mk` (not upstream `designs/nangate45/gcd/config.mk`) | |
| 3 | Tutorial `constraint.sdc` | |
| 4 | `flow/scripts/cts.tcl` | |
| 5 | PDK LEF (nangate45) | |
| 6 | Folder where `6_final.gds` will land for `learn` variant | |

Solution (look **after** you try):

```
1  tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v
2  learn/designs/nangate45/gcd-tutorial/config.mk
    (ORFS sees it as flow/designs/nangate45/gcd-tutorial/ via symlink)
3  learn/designs/nangate45/gcd-tutorial/constraint.sdc
4  tools/OpenROAD-flow-scripts/flow/scripts/cts.tcl
5  tools/OpenROAD-flow-scripts/flow/platforms/nangate45/
6  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/
```

**Trap:** `designs/nangate45/gcd/` is the **upstream** ORFS design (`FLOW_VARIANT=base` if you run wrong). The course uses **`gcd-tutorial`** + **`FLOW_VARIANT=learn`**.

---

## Part 3 — Stage contracts (10 min)

Copy into your notebook and complete from memory:

```
Verilog+SDC → ______ → gate-level netlist
            → ______ → die/core/PDN
            → ______ → cell (x,y)
            → ______ → clock tree
            → ______ → DRC wire
            → ______ → GDS+SPEF
```

Answers: synth, floorplan, place, CTS, route, finish.

Open `learn/reference/file-formats.md` and for **ODB, SDC, SPEF, GDS** write one line each: tool + purpose.

---

## Part 4 — Active glossary (10 min)

Open `learn/reference/glossary.md`. Without reading everything, define **in your own words**:

1. Core utilization  
2. Skew  
3. WNS  
4. DRC  
5. FLOW_VARIANT  

Then compare with the glossary. If you copied phrases, redo it.

---

## Part 5 — Smoke synth (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 00
```

Or:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth
ls -lh results/nangate45/gcd/learn/1_synth.odb
```

If `1_synth.odb` is missing: log `logs/nangate45/gcd/learn/1_2_yosys.log`. Playbook synth section.

Open `reports/nangate45/gcd/learn/synth_stat.txt` (or search `Printing statistics` in the Yosys log). Note: cell count, area. Compare with `learn/reference/golden-metrics.md` Synth row (496 / 628.824 / 35 DFF).

---

## Part 6 — GUI: Desktop vs Preview (10 min)

1. In Cursor chat, **do not** use Preview for OpenROAD.
2. Open **Desktop** on the agent page.
3. Compare with `learn/reference/gui-atlas.md` section 1 (anatomy). You do not need to launch the GUI in this lesson if desktop is not ready; in that case describe rectangles A–G from PNG `win_anatomy_labeled.png`.

Question to write: why can an HTTP iframe not show a Qt/VNC window?

---

## Part 7 — Notebook (5 min)

```bash
cp learn/workbook/notes-template.md learn/workbook/mio-notebook.md
```

Fill the first session: date, duration, 3 observations.

---

## Pass criteria

- [ ] Scavenger hunt table completed
- [ ] Six stages in order, from memory
- [ ] `1_synth.odb` exists in `.../gcd/learn/`
- [ ] Notebook created
- [ ] Can explain Preview vs Desktop

**Do not** run `--all` in auto mode: it burns through the course.
