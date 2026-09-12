# Ladder-B ASAP7 BSPDN PROXY recipe

Status: landed in the Lab contract on 2026-09-12. This is a research recipe,
not a foundry deck and not a Product evaluation input.

## Canonical row

| Field | Value |
| --- | --- |
| `recipe_id` | `asap7_proxy_bpr_bs_m89_v0` |
| `model_id` | `asap7_bspdn_proxy_m89` |
| `mesh_id` | `asap7_bspdn_proxy_m89` |
| `platform` | `asap7` |
| `topology` | `proxy` |
| IR claim | `honesty=PROXY` |
| thermal claim | `honesty=GAP` until a declared compact HotSpot model is stamped |
| OpenROAD #10547 | independent; never a gate for Ladder B |

## Stand-in stack

The public stock ASAP7 route is used as a geometric host. The backside rail
and via layers are represented analytically by a documented remap; the remap
does not claim real BM* layers or PowerVia extraction.

```text
BM1 -> M9 stand-in
BM2 -> M8 stand-in
BM3 -> M7 stand-in
topology -> analytical rail + via network over stock ASAP7
```

The analytical defaults are an educational range, not a calibrated oracle:

```text
rail_model_id       = gupta_ted20_edu_range_v0
rail_r_ohm_per_um   = 120.0       # range estimate; do not pin a pass value
via_model_id        = literature_via_range_v0
via_R_ohm           = 0.02        # range estimate; do not reverse-fit mV
rail_length_um      = 1.0         # effective educational path length
current_a           = 0.010      # uniform experiment load
thermal_model_id    = null
n_r                 = 89
n_sources           = 4
```

The rail range is anchored to Gupta et al., *Buried Power Rail Integration
With FinFETs for Ultimate CMOS Scaling*, IEEE Transactions on Electron
Devices 67(12), DOI [`10.1109/TED.2020.3033510`](https://doi.org/10.1109/TED.2020.3033510).
The reported value is retained as educational provenance only; it is not a
calibration target or a pass threshold for this proxy.

The emitter uses these inputs in a transparent two-node reduction:

```text
Rrail_eq          = rail_r_ohm_per_um * rail_length_um / n_sources
Rvia_eq           = via_r_ohm / n_sources
R_eq              = Rrail_eq + Rvia_eq
droop_proxy_mv    = current_a * R_eq * 1000
```

This value is a model observation only. There is no expected-voltage or gold
millivolt threshold in the recipe.

The cited resistance range is retained for education and provenance only.
It cannot promote the report to `PARTIAL` or Product PASS. A later compact
HotSpot run must carry its own `model_id` and `powermap_kind` (`uniform` or
`workload`); it must not silently reuse the Nangate model.

## Fingerprint

`mesh_fingerprint` is a SHA-256 digest over the canonical JSON inputs. At a
minimum the input object contains `rail_model_id`, `via_model_id`, and the
explicit `thermal_model_id` key whose value may be `null`. It also contains
the stack, topology, PDK revision, grid pitches, source/load models, spice
hash (when available), and recipe dimensions. Identical `mesh_id` values with
different or missing fingerprints are not `same_mesh`.

## Emission and admit rules

The emitter writes only `lab_asap7_bspdn_proxy_*` reports and never emits
`asap7_bpr_chip` or `asap7_bspdn_chip`. Those identifiers remain
GAP-reserved until Ladder-A has a real BM*/BPR LEF/LIB, tech LEF, ORFS PDN
configuration, RC honesty, mesh fingerprint, and DRC map.

Every row has `product_win=false`, `productWin=false`, `win_eligible=false`,
and `comparable_to_gold_ir=false`. `status` is a tool outcome; `honesty` is a
claim class. Thermal GAP is visible and required, but it is not the sole
reason to reject a valid Lab PROXY admit. `signoff_all.ok` remains false for
the Lab row and is never a Product/foundry verdict.

## Provenance

The default analytical implementation is an Apache-2.0-compatible PDflow
calculation with `tool_id=analytical_two_node_rc` and
`license_class=Apache-2.0`. License-gated tools, Calibre, FakeRAM, BeGAN,
and AGPL evidence cannot promote this recipe.
