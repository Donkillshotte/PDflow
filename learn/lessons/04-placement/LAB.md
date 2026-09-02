# LAB 04 — Placement (90–120 minutes)

Here the design **occupies space**. Bring open: GUI atlas §5.5–5.6 and `walkthrough-global_place.tcl.md`.

## Measurable objectives

- [ ] Distinguish GP and DP on screenshot or GUI (not in vague words)
- [ ] Extracted WNS/TNS/buffer from `3_resizer.rpt`
- [ ] Found at least one resizer prefix (`rebuffer*`, `fanout*`, …)
- [ ] Connected tight clock → more buffer → more area → CTS risk

---

## Part 1 — Operational theory (15 min)

Reread `lessons/04-placement/README.md` sub-stage tables.

In one sentence each:

1. What does **global placement** optimize?
2. What does **detailed placement** forbid?
3. Why does ORFS do GP, **then** resizer, **then** DP (and not DP before resizer)?

Hint: resizer buffers must be legalized.

---

## Part 2 — Walkthrough Tcl (20 min)

Open `flow/scripts/global_place.tcl` and the walkthrough.

Mark:

| Line / block | What it does | If you remove it… |
|---|---|---|
| `buffer_ports` | | slew on I/O pins |
| `GPL_TIMING_DRIVEN` | | GP ignores slack |
| `-density` | | overflow / holes |
| `estimate_parasitics -placement` | | STA blind to wires |

Then `flow/scripts/detail_place.tcl`: `detailed_placement`, `improve_placement`, `optimize_mirroring`, `check_placement`.

**Question:** why does `3_5_place_dp-failed.odb` exist?

---

## Part 3 — Run place (15 min)

```bash
./scripts/learn_physical_design.sh --deep --lesson 04
```

Or:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 place
ls results/nangate45/gcd/learn/3_3_place_gp.odb \
   results/nangate45/gcd/learn/3_4_place_resized.odb \
   results/nangate45/gcd/learn/3_5_place_dp.odb
```

---

## Part 4 — Report (25 min)

Read **in full** (they are short on GCD):

```bash
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_global_place.rpt
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt
```

Extract in the notebook:

| Metric | Value | File |
|---|---|---|
| GP overflow | | 3_global_place / log 3_3 |
| WNS | | 3_resizer |
| TNS | | 3_resizer |
| Buffer inserted | | log `3_4_place_resized` (`Inserted`) |
| Resize / upsize | | same log |

```bash
rg -n 'Inserted|Resize|WNS|TNS|overflow' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/3_4_place_resized.log \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  | head -40
```

Workbook **C2**: same number in the notebook.

---

## Part 5 — GUI comparison GP vs DP (30 min)

Desktop. Two loads (or two terminals):

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_3_place_gp.odb
# another shell, same cwd:
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_5_place_dp.odb
```

Use `learn/reference/gui-atlas.md`:

- GP: `win_place_gp.png` / `04_place_gp_labeled.png` — blob, possible visual overlap
- DP: `win_place_dp.png` / `05_place_dp.png` — row alignment

Checklist:

- [ ] Fit (`F`) on both
- [ ] I/O triangles on edge (GP after IOP)
- [ ] Visible PDN straps
- [ ] Heatmap Placement Density if available in View (red = full)

Find: `rebuffer`, `clkbuf` (pre-CTS there are few clkbuf).

If you do not have Desktop: note the differences **on PNG reports** — that is accepted, but try the GUI at least once in the course.

---

## Part 6 — Bridge to CTS (10 min)

Write the chain (lessons 01+03+04):

```
Tight SDC → negative WNS → RSZ buffer → area ↑ → same core (util 35%)
  → at CTS detailed_placement may hit DPL-0038
```

Predict: with `constraint_tight.sdc` do buffers in `3_4` rise or fall?

---

## Pass criteria

- [ ] Resizer metrics table
- [ ] One GP/DP difference documented (screenshot or atlas reference)
- [ ] Resizer prefix explained
