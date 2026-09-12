# Lab BSPDN registry schema v0

Registry rows are the Studio-facing index for the Lab surface. They are not
the Product suite registry.

## Row contract

```text
version: string
runId: string
surface: lab | lab_asap7
variant: string
design: string
pdk: asap7
ok: boolean
productWin: false
win_eligible: false
reportPaths: string[]
resultsDir: path under tools/OpenROAD-flow-scripts/flow/results/asap7/<nick>/lab_asap7_*
track: asap7 | asap7_bspdn | asap7_bpr | asap7_pkg
```

For IR rows, also include `ir_report_paths`, `mesh_id`, `oracle`,
`comparable_to_gold_ir: false`, and, when available, `topology` and
`mesh_fingerprint`. A BSPDN/BPR row includes `honesty` and
`honesty_reason`; a PROXY row additionally includes `tool_id` and
`license_class`.

`track=asap7_bb` is permitted for citation/EDU documentation only and must be
refused by Lab-admit and suite paths. Registry consumers normalize
`productWin` and `product_win` once, then apply the false firewall.

## Path and comparison rules

`resultsDir` is path-guarded below the ASAP7 Lab result tree and never points
at the Product result tree. Relative comparisons require identical mesh ID,
fingerprint, platform, and design/nickname. Cross-topology, candidate-vs-FS,
and cross-PDK comparisons fail closed.

The registry can show `honesty=GAP` thermal evidence alongside a Lab-green
IR PROXY row. It must not convert that row to Product signoff or set
`signoff_all.ok=true`.
