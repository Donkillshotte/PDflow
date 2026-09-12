# IR oracle schema v0.1 — ASAP7 Lab extension

This is a docs-first schema for Lab reports. It is not a Product scoring
schema and it does not define a fixed voltage oracle.

## Required envelope

When IR evidence is present, the report contains:

```text
mesh_id: string
oracle: string
ok: boolean
ir_report_paths: string[]
platform: asap7
surface: lab | lab_asap7
topology: fs | proxy | bpr | bspdn | pkg
product_win: false
productWin: false                 # disk-compatible alias
win_eligible: false
comparable_to_gold_ir: false
honesty: GAP | PROXY | PARTIAL
honesty_reason: non-empty string
leftovers: array
```

The observation keys `scenario`, `n_r`, `droop_mv`, and `ir.droop_proxy` may
be present. `expected_mv` and `gold_mv` are forbidden.

## Mesh IDs

| Mesh ID | Topology | Emission |
| --- | --- | --- |
| `asap7_chip_tier_b` | `fs` | allowed for the existing FS Lab stamp |
| `asap7_bspdn_proxy_<short>` | `proxy` | allowed for Ladder B |
| `asap7_pkg_tier_c` | `pkg` | allowed only on the Lab PKG path |
| `asap7_candidate_<short>` | parent/candidate | allowed only for strict Lab DSE |
| `asap7_other_<short>` | tagged overflow | Lab-only |
| `asap7_bpr_chip` | `bpr` | forbidden until Ladder A |
| `asap7_bspdn_chip` | `bspdn` | forbidden until Ladder A |

`asap7_bb` is an education/docs track and is never a suite or Lab-admit
track. `asap7_pkg_tier_c` must never be aliased to `nangate_system_pdn`.

## Same-mesh predicate

`same_mesh` is true only when `mesh_id`, `mesh_fingerprint`,
`platform=asap7`, and the design/nickname identity match. A missing
fingerprint is fail-closed. Different topologies, candidate-vs-FS, and any
ASAP7-vs-Nangate comparison are refused.

## Proxy fingerprint

For `asap7_bspdn_proxy_*`, `mesh_fingerprint` is a SHA-256 digest over a
canonical JSON object containing at least:

```text
rail_model_id: non-empty string
via_model_id: non-empty string
thermal_model_id: string | null
recipe_id, model_id, mesh_id, topology
stack/topology/PDK revision and grid/source/load dimensions
```

The explicit null thermal key is part of the digest. Omitting either rail or
via identity is a schema failure.
