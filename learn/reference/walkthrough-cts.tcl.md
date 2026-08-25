# Walkthrough annotato — cts.tcl (ORFS 26Q2)

File: `flow/scripts/cts.tcl`  
Input: `3_place.odb` + `3_place.sdc`  
Output: `4_1_cts.odb`, `4_cts.sdc`  
Errore didattico: `4_1_error.odb` se `detailed_placement` fallisce.

GUI: [gui-atlas.md](./gui-atlas.md) §5.7; Inspector su `clk` (§4) dopo il route mostra `CTS_NDR_0` — la regola nasce qui.

---

## Flusso (mappa mentale)

```
load 3_place
  repair_clock_inverters
  clock_tree_synthesis          ← inserisce CLKBUF* / inverter
  estimate_parasitics -placement
  detailed_placement            ← DPL-0038 vive qui
  repair_timing_helper          ← setup/hold con clock già ad albero
  detailed_placement di nuovo
  check_placement
  report_metrics 4 "cts final"
```

CTS **non** è “aggiungere un buffer e via”. Cambia il netlist, poi **deve** rlegalizzare. Se il core era al 90% e RSZ+CTS aggiungono 15% di area, sei oltre il 100%.

---

## Load e inverter (righe 1–10)

```tcl
load_design 3_place.odb 3_place.sdc
source_step_tcl PRE CTS
repair_clock_inverters
```

`repair_clock_inverters` clona/sposta inverter di clock **vicino ai sink**. Senza questo, TritonCTS bufferizza clock *invertiti* in modo stupido (albero sull’inverso, skew peggiore).

**Esercizio:** nel log `4_1_cts.log` cerca `repair_clock_inverters`. C’è output? Su GCD a volte è silenzioso (pochi inverted clock).

---

## save_progress (righe 12–16)

```tcl
proc save_progress { stage } {
  puts "Run 'make gui_$stage.odb' to load progress snapshot"
  orfs_write_db $::env(RESULTS_DIR)/$stage.odb
  orfs_write_sdc $::env(RESULTS_DIR)/$stage.sdc
}
```

Quando fallisce il DPL, ORFS chiama `save_progress 4_1_error`. **Memorizza il comando GUI** stampato nel log. È il modo professionale di debug, non rilanciare alla cieca.

---

## clock_tree_synthesis (righe 18–36)

```tcl
set cts_args [list \
  -sink_clustering_enable \
  -repair_clock_nets]
append_env_var cts_args CTS_BUF_DISTANCE -distance_between_buffers 1
append_env_var cts_args CTS_CLUSTER_SIZE -sink_clustering_size 1
append_env_var cts_args CTS_CLUSTER_DIAMETER -sink_clustering_max_diameter 1
append_env_var cts_args CTS_BUF_LIST -buf_list 1
append_env_var cts_args CTS_LIB_NAME -library 1
if { [env_var_exists_and_non_empty CTS_ARGS] } {
  set cts_args $::env(CTS_ARGS)
}
set_dont_use $::env(DONT_USE_CELLS)
log_cmd clock_tree_synthesis {*}$cts_args
```

| Argomento | Ruolo didattico |
|---|---|
| `-sink_clustering_enable` | raggruppa FF vicini → meno foglie, albero più corto |
| `-repair_clock_nets` | sistema net clock dopo insert |
| `CTS_BUF_DISTANCE` | distanza max tra buffer (capacitance) |
| `CTS_BUF_LIST` | quali `CLKBUF_X*` usare |
| `CTS_ARGS` | override totale (esperti; nel corso non serve) |

Dopo questo comando, in GUI `select -name "clkbuf*" -type Inst` deve trovare **più** istanze che in `3_place.odb`.

NDR: OpenROAD applica spesso una **non-default rule** sul clock (wire più largo / spacing). In Inspector post-route la vedi come `CTS_NDR_0` sulla net `clk`.

---

## Parasitics e DPL (righe 38–53)

```tcl
log_cmd estimate_parasitics -placement
...
set_placement_padding -global \
  -left $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT) \
  -right $::env(CELL_PAD_IN_SITES_DETAIL_PLACEMENT)
set result [catch { detailed_placement } msg]
if { $result != 0 } {
  save_progress 4_1_error
  error "Detailed placement failed in CTS: $msg"
}
```

I buffer CTS hanno area. `detailed_placement` deve trovar loro un site. Se `Instances area / core > 1`:

```
[ERROR DPL-0038] Utilization greater than 100%
```

**Fix nel corso (uno alla volta):**

1. `CORE_UTILIZATION=30` (core più grande)
2. SDC 0.46 o 2.0 ns (meno RSZ pre-CTS)
3. Non alzare density addon nello stesso run in cui stringi il clock

Playbook: `debug-playbook.md` sezione CTS. LAB 05 parte 4: provocare e risolvere.

---

## repair_timing post-CTS (righe 61–86)

Con clock **propagato** (albero), gli skew sono reali. `repair_timing_helper` inserisce ancora buffer di *segnale* (non solo clock) per setup/hold. Poi **secondo** `detailed_placement` + `check_placement -verbose`.

Se `EQUIVALENCE_CHECK`/`LEC_CHECK` sono on (non nel tutorial): dump Verilog pre/post RSZ. Ignora nel corso.

`CTS_SNAPSHOTS=1` salva `4_1_pre_repair_hold_setup.odb` — utile se vuoi GUI *prima* del repair.

---

## Output e metriche

```tcl
report_metrics 4 "cts final"
orfs_write_db $::env(RESULTS_DIR)/4_1_cts.odb
orfs_write_sdc $::env(RESULTS_DIR)/4_cts.sdc
```

Report: `reports/.../4_cts_final.rpt` — skew, latency, WNS.  
SDC post-CTS può contenere latency *propagate*: non è più il vincolo “ideale” della lezione 01.

Confronta `3_place.sdc` e `4_cts.sdc` (`diff`). Cosa è comparso?

---

## GUI — procedura

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_4_cts.odb
```

```tcl
gui::fit
select -name "clk" -type Net
select -name "clkbuf*" -type Inst
```

PNG: `gui-shots/win_cts.png`, `06_cts.png`.

View → Clock Tree Viewer se disponibile; altrimenti l’Inspector sulla net basta per il corso.

---

## Checkpoint

1. Perché CTS richiama `detailed_placement`?
2. Differenza `4_1_error.odb` vs `3_5_place_dp-failed.odb`?
3. Un parametro config che riduce DPL-0038 senza toccare lo SDC?
4. Cosa misura lo **skew** (una frase, glossario)?
