# Lesson 05 — Clock Tree Synthesis (CTS)

CTS is where the course **teaches debug**. If everything passes on the first try, trigger a failure (LAB part 4).

The CTS report and log are the only source of truth for the active GCD
invocation. Use them to populate this table while running the lesson:

| Stage | Core | Area istanze | Util | Note |
|---|---|---|---|---|
| DPL pre-repair CTS | current log | current log | current log | clock buffers just inserted |
| After `repair_timing` CTS | current log | current log | current log | current buffer/diagnostic messages |
| WNS CTS final | | | | current report, including setup violations |
| Setup skew | | | | current clock-skew report |
| Finish (same invocation only) | | | | current finish report, if available |

Use the current diagnostic messages to decide whether timing is closed. If
repair remains incomplete, record the exact warning from this invocation;
the next action depends on the active SDC and utilization.

## Objectives

- Skew vs latency vs NDR, with numbers
- Count `CLKBUF*` pre/post
- Read the **Clock Tree Viewer** (PNG `orfs_cts_clock_tree.png`)
- Fix DPL-0038 with **one** knob

## Reading

- This README
- `walkthrough-cts.tcl.md`
- `debug-playbook.md` CTS section
- LAB 05
- Atlas §5.7 and §9 (ORFS heatmaps)

## The problem

N flip-flops, one pin `clk`. Star topology (one wire to all CK pins):

- bad slew (the clock is not a square wave)
- huge RC delay
- uncontrolled skew

CTS builds a tree of `CLKBUF*` / inverters with **similar latency** to the sinks.

In the viewer (`orfs_cts_clock_tree.png`) on the GCD see about:

- root (triangle) → 1 buffer → **fanout 4** → leaves (FF) around **0.07 ns** latency
- leaves nearly aligned in Y → small skew (consistent with report ~0)

## TritonCTS sequence in ORFS

1. `repair_clock_inverters`
2. `clock_tree_synthesis -sink_clustering_enable -repair_clock_nets`
3. `estimate_parasitics -placement`
4. `detailed_placement` ← **area breaking point** (DPL-0038)
5. `repair_timing` setup/hold (here produces 45 buffers and RSZ-0062)
6. second `detailed_placement` + `check_placement`

If step 4 fails: `save_progress 4_1_error` → `gui_4_1_error.odb`.

## Skew, latency, NDR

- **Latency** sink: delay from block pin `clk` → FF `CK`.
- **Skew**: difference in latency. Setup eats worst-case skew; hold hates inverted skew.
- **Ideal clock** (pre-CTS): STA pretends network latency = 0.
- **Propagated clock** (post-CTS): delay of `CLKBUF*`. WNS can change from
  placement to CTS even before signal wires are extracted.
- **NDR** `CTS_NDR_0`: wider rule on the clock. Inspector on net `clk` after route.

A tree beats a star because the star has RC/slew unacceptable at a few dozen
sinks. Count the current sequential cells in `synth_stat.txt` rather than
assuming a fixed register count.

## Link to lessons 01 + 03 + 04

```
tight clock → RSZ pre-CTS inflates area
small core (high util) → few free sites
CTS inserts CLKBUF + more RSZ
detailed_placement: util > 100% → DPL-0038
```

Read the current utilization in the log. DPL-0038 appears when the active
placement cannot legalize the requested cells; diagnose the current log rather
than a stored percentage. This is not an OpenROAD bug.

## Metrics to note

| Metric | Files |
|---|---|
| Skew / latency | `4_cts_final.rpt` (`report_clock_skew`) |
| WNS/TNS / viol count | same report |
| Buffer inserted | log `4_1_cts.log` `Inserted N buffers` |
| Util DPL | log `DPL-0006` |
| Tree | `reports/.../cts_core_clock.webp.png` (copied to `gui-shots/orfs_cts_clock_tree.png`) |

## GUI

```tcl
select -name "clk" -type Net
select -name "clkbuf*" -type Inst
```

PNG window: `win_cts.png`. Viewer: `orfs_cts_clock_tree.png`.  
View → Clock Tree Viewer if the menu responds; otherwise the ORFS PNG is the same information.

## Power & SPICE chain

CTS inserisce buffer clock → increases **Clock group** in `report_power`. See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-05-cts).

| Link | Where |
|---|---|
| FlowLab | [cts](/flow?phase=cts) |

## Duration

README+walkthrough 50–70 min, LAB 90–120 min (includes intentional debug), **total ~3 hours**.
