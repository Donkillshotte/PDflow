# LAB 01 — Constraints and SDC (90–120 minute session)

## Measurable objectives

By the end you must be able to:
- Explain every line of your `constraint.sdc` aloud
- Predict the effect of ±50% on the clock period before launching the flow
- Find WNS/TNS in a report without help

---

## Part 1 — Guided SDC reading (20 min)

Open: `learn/designs/nangate45/gcd-tutorial/constraint.sdc`

### Line by line

```tcl
current_design gcd
```
→ Tells OpenSTA which top module to analyze. Must match `DESIGN_NAME` in config.mk.

```tcl
set clk_period 0.46
```
→ **Period** in nanoseconds, not frequency. Frequency = 1/0.46 ≈ 2.17 GHz.

```tcl
create_clock -name $clk_name -period $clk_period $clk_port
```
→ Creates a virtual clock on port `clk`. All FFs in that domain inherit the period.

```tcl
set_input_delay [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs
```
→ Model: input signals arrive with delay relative to the clock edge. 20% of the period = IO budget.

**Write in your notebook:** input_delay = ______ ns

---

## Part 2 — File experiment (30 min)

### Run 1 — Baseline
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc learn/workbook/backup-sdc-default.sdc
./scripts/learn_physical_design.sh --lesson 01
# or only:
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
```

Notes from `reports/.../learn/3_resizer.rpt`:
- WNS worst setup
- Buffer count (search for "Inserted")

### Run 2 — Relaxed
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint_relaxed.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 \
     clean_synth clean_floorplan clean_place
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
```

**Question:** Did WNS improve? Did cell area decrease?

### Run 3 — Tight (optional, may fail later)
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint_tight.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

If CTS fails later → **educational success**. Open debug-playbook.

---

## Part 3 — config.mk (20 min)

Open `learn/designs/nangate45/gcd-tutorial/config.mk`

| Variable | Course value | What happens if you double it |
|---|---|---|
| CORE_UTILIZATION | 35 | smaller core → overflow risk |
| FLOW_VARIANT | learn | results separate from base |
| PLACE_DENSITY_LB_ADDON | 0.20 | placement density margin |

**Exercise:** add comment `# lesson01: my util=40 value` and try `CORE_UTILIZATION=40` from the CLI:

```bash
CORE_UTILIZATION=40 ./scripts/run_gcd_flow.sh floorplan
```

Compare core area in the log with util 35.

---

## Part 4 — GUI timing (20 min)

Prerequisite: Desktop Cursor open.

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_place.odb
```

GUI checklist:
1. [ ] Charts panel → Endpoint Slack visible
2. [ ] Click on endpoint with negative slack
3. [ ] View → Worst Path (highlighted path)
4. [ ] Identify a `DFF_X1` on the path

**Write:** name of the start and end pins of the worst path.

---

## Part 5 — OpenSTA standalone (15 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
sta -no_init <<'EOF'
read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_verilog results/nangate45/gcd/learn/1_2_yosys.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
report_checks -fields {slew cap input_pins fanout} -max_paths 5
EOF
```

Compare slack with the post-place report. Why do they differ? (hint: parasitics, placement)

---

## Part 6 — Written reflection (10 min)

Answer in `learn/workbook/mio-quaderno.md`:

1. What is the tradeoff between clock period and area?
2. Why does input_delay use a percentage of the period?
3. When would you use `set_false_path`? (search for examples online or in other ORFS designs)

---

## Pass criteria

- [ ] SDC sweep table completed (workbook A2)
- [ ] Worst path identified in GUI
- [ ] Explained `create_clock` to someone (or recorded aloud)
- [ ] Restored constraint.sdc default

Restore:
```bash
cp learn/workbook/backup-sdc-default.sdc learn/designs/nangate45/gcd-tutorial/constraint.sdc
```
