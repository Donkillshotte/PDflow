# Walkthrough annotato — cts.tcl

File: `flow/scripts/cts.tcl`

## Flusso logico

```
load 3_place.odb
  → repair_clock_inverters
  → clock_tree_synthesis
  → estimate_parasitics -placement
  → detailed_placement        ← qui spesso fallisce se area piena
  → repair_timing (setup/hold)
  → report_metrics
```

## repair_clock_inverters (riga 10)

Clona inverter clock vicino ai carichi per evitare che CTS bufferizzi clock invertiti in modo inefficiente.

## clock_tree_synthesis (righe 19–36)

```tcl
set cts_args [list -sink_clustering_enable -repair_clock_nets]
log_cmd clock_tree_synthesis {*}$cts_args
```

Opzioni env utili per esperimenti:
- `CTS_BUF_DISTANCE`
- `CTS_CLUSTER_SIZE`
- `CTS_BUF_LIST`

## detailed_placement post-CTS (righe 49–53)

```tcl
set result [catch { detailed_placement } msg]
if { $result != 0 } {
  save_progress 4_1_error
  error "Detailed placement failed in CTS: $msg"
}
```

**Questo è il blocco che genera DPL-0038** quando area istanze > core.

## save_progress 4_1_error

Salva ODB per debug GUI — **usalo sempre** quando CTS fallisce.

## repair_timing post-CTS

Dopo legalizzazione, OpenROAD tenta fix setup/hold con buffer sizing.

## Domande comprensione

1. Perché parasitics `-placement` prima del repair?
2. Cosa cambia in `4_cts.sdc` vs `3_place.sdc`?
3. Quale parametro config riduce probabilità DPL-0038?

Risposta 3: `CORE_UTILIZATION` più basso, o SDC più rilassato.
