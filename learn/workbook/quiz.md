# Self-assessment quizzes

Fai i quiz **dopo** LAB of the lesson. Solutions in fondo. Do not scroll.

---

## Quiz 00 — Intro

1. List the 6 ORFS macro-stages in order.
2. What distinguishes `results/.../base` da `results/.../learn`?
3. Why does Preview Cursor not show OpenROAD?

## Quiz 01 — SDC

1. `create_clock -period 0.46` is frequency or period? What is it in GHz?
2. `clk_io_pct 0.2` with period 0.46: input_delay = ?
3. Why clock 0.25 ns + util 55% can make CTS fail?

## Quiz 02 — Synth

1. Who produces `1_2_yosys.v` and who `1_synth.odb`?
2. Le celle in `gui_1_synth.odb` already placed?
3. Is an inferred latch a problem? Why?

## Quiz 03 — Floorplan

1. How many floorplan init methods does ORFS accept? Which do we use?
2. `CORE_UTILIZATION` higher → larger or smaller core?
3. Is PDN placement of logic cells?

## Quiz 04 — Place

1. Global vs detailed placement difference in one sentence.
2. What does the resizer do?
3. What does instance prefix `rebuffer*` mean?

## Quiz 05 — CTS

1. What is skew?
2. Where is saved the snapshot se detailed placement CTS fallisce?
3. Error code for utilization > 100%?
4. RSZ-0062 e DPL-0038 are the same problema?

## Quiz 06 — Route

1. `route.guide` is mask geometry-ready?
2. Files DRC post detailed route?
3. Why GRT before di DRT?

## Quiz 07 — Finish

1. SPEF you need a STA o a Yosys?
2. Do fill cells change logic function?
3. List 4 signoff deliverables.
4. Se SDC is 0.46 ns e `period_min` a finish is 0.50 ns, did you close the frequency target?
5. OpenRCX produce quale file?
6. `*D_NET` in SPEF is an RC net or a make command?

## Quiz GUI — atlas

1. In a window 1680×1000, the Display Control is on the left or right?
2. `metal2` in Nangate45 in *this* GUI is red or green?
3. Why `gui_1_synth.odb` has black canvas?
4. `gui::set_display_controls "Rows" visible true` on 26Q2: what happens?
5. Inspector: `CTS_NDR_0` su net `clk` means the clock is still ideal?
6. What does a **gcell** measure in the heatmap congestion?

## Quiz metrics / messaggi tool

1. **RSZ-0062** vs **DPL-0038**: which of the two makes fail `detailed_placement` for util > 100%?
2. **IFP-0028** a crash?
3. fmax da `period_min=0.50` ns is about how many MHz?
4. Sul run d’oro, WNS a place is positive or negative? A finish?

---

**00:** (1) synth, floorplan, place, cts, route, finish. (2) FLOW_VARIANT. (3) Preview is HTTP iframe; OpenROAD is Qt/VNC → Desktop.

**01:** (1) Period; ~2.17 GHz. (2) 0.092 ns. (3) RSZ inflates area beyond the core.

**02:** (1) Yosys; OpenROAD synth_odb. (2) No. (3) Yes, unexpected timing/async.

**03:** (1) Four (DEF, footprint, DIE+CORE, utilization); we use utilization. (2) Smaller. (3) No, it is power grid.

**04:** (1) GP approximates; DP legalizes on sites. (2) Buffer/upsize/clone for timing. (3) Buffer inserted for timing.

**05:** (1) Clock arrival difference between sinks. (2) `4_1_error.odb`. (3) DPL-0038. (4) No: 0062 = timing not repaired; 0038 = util > 100% at DPL.

**06:** (1) No, are guide. (2) `5_route_drc.rpt`. (3) DRT needs guides/congestion map.

**07:** (1) STA. (2) No. (3) GDS, DEF, SPEF, SDC (e netlist .v). (4) No: fmax is 1/0.50 ≈ 2.01 GHz, the target 0.46 ns ≈ 2.17 GHz is not closed. (5) SPEF (`6_final.spef`). (6) Net with lumped capacitance + RC.

**GUI:** (1) Left (zone C). (2) Rosso. (3) Die 0×0, cells not placed. (4) `[ERROR GUI-0013]`. (5) No: is a non-default routing rule on the clock, sign that CTS touched that net. (6) Global router capacity unit (grid cell).

**Metrics:** (1) DPL-0038. (2) No: snapping to the site grid. (3) ~2000 MHz (1000/0.50). (4) Place +0.01 (positivo); finish −0.04 (negativo).
