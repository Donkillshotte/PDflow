# Quiz di autovalutazione

Fai i quiz **dopo** LAB della lezione. Soluzioni in fondo. Non scrollare.

---

## Quiz 00 — Intro

1. Elenca le 6 macro-fasi ORFS in ordine.
2. Cosa distingue `results/.../base` da `results/.../learn`?
3. Perché la Preview Cursor non mostra OpenROAD?

## Quiz 01 — SDC

1. `create_clock -period 0.46` è frequenza o periodo? Quanto vale in GHz?
2. `clk_io_pct 0.2` con periodo 0.46: input_delay = ?
3. Perché clock 0.25 ns + util 55% può far fallire CTS?

## Quiz 02 — Synth

1. Chi produce `1_2_yosys.v` e chi `1_synth.odb`?
2. Le celle in `gui_1_synth.odb` sono già piazzate?
3. Un latch inferito è un problema? Perché?

## Quiz 03 — Floorplan

1. Quanti metodi di init floorplan accetta ORFS? Quale usiamo?
2. `CORE_UTILIZATION` più alto → core più grande o più piccolo?
3. PDN è placement di celle logiche?

## Quiz 04 — Place

1. Differenza global vs detailed placement in una frase.
2. Cosa fa il resizer?
3. Prefisso istanza `rebuffer*` significa?

## Quiz 05 — CTS

1. Cos'è lo skew?
2. Dove si salva lo snapshot se detailed placement CTS fallisce?
3. Codice errore utilization > 100%?
4. RSZ-0062 e DPL-0038 sono lo stesso problema?

## Quiz 06 — Route

1. `route.guide` è geometria mask-ready?
2. File DRC post detailed route?
3. Perché GRT prima di DRT?

## Quiz 07 — Finish

1. SPEF serve a STA o a Yosys?
2. Fill cells cambiano la funzione logica?
3. Elenca 4 deliverable di signoff.
4. Se SDC è 0.46 ns e `period_min` a finish è 0.50 ns, hai chiuso il target di frequenza?

## Quiz GUI — atlante

1. In una finestra 1680×1000, il Display Control sta a sinistra o a destra?
2. `metal2` in Nangate45 in *questa* GUI è rosso o verde?
3. Perché `gui_1_synth.odb` ha il canvas nero?
4. `gui::set_display_controls "Rows" visible true` su 26Q2: cosa succede?
5. Inspector: `CTS_NDR_0` su net `clk` significa che il clock è ancora unideal?

---

**00:** (1) synth, floorplan, place, cts, route, finish. (2) FLOW_VARIANT. (3) Preview è HTTP iframe; OpenROAD è Qt/VNC → Desktop.

**01:** (1) Periodo; ~2.17 GHz. (2) 0.092 ns. (3) RSZ gonfia area oltre il core.

**02:** (1) Yosys; OpenROAD synth_odb. (2) No. (3) Sì, timing/async inatteso.

**03:** (1) Quattro (DEF, footprint, DIE+CORE, utilization); usiamo utilization. (2) Più piccolo. (3) No, è power grid.

**04:** (1) GP approssima; DP legalizza sui site. (2) Buffer/upsize/clone per timing. (3) Buffer inserito per timing.

**05:** (1) Differenza arrivo clock tra sink. (2) `4_1_error.odb`. (3) DPL-0038. (4) No: 0062 = timing non riparato; 0038 = util > 100% al DPL.

**06:** (1) No, sono guide. (2) `5_route_drc.rpt`. (3) DRT ha bisogno di guide/congestion map.

**07:** (1) STA. (2) No. (3) GDS, DEF, SPEF, SDC (e netlist .v). (4) No: fmax è 1/0.50 ≈ 2.01 GHz, il target 0.46 ns ≈ 2.17 GHz non è chiuso.

**GUI:** (1) Sinistra (zona C). (2) Rosso. (3) Die 0×0, celle non piazzate. (4) `[ERROR GUI-0013]`. (5) No: è una non-default rule di routing clock, segno che CTS ha toccato quella net.
