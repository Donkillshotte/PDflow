# ASAP7 Lab Evaluation Contract

Status: P1 freeze for the ASAP7+BSPDN research lane.

This contract is deliberately scoped to `lab` and `lab_asap7`. It is not a
Product evaluation contract and it must never be used to create a Product
win, a Product-ready report, or a comparison against a gold IR oracle.

## Non-goals

- `product_win` / `productWin` is always `false`.
- `win_eligible` is always `false`.
- `comparable_to_gold_ir` is always `false`.
- ASAP7-BB is citation and education only until public LEF, LIB, tech LEF,
  and an ORFS `config.mk` are available.
- `asap7_bpr_chip` and `asap7_bspdn_chip` remain GAP-reserved and
  emit-forbidden until Ladder A is stamped.
- No ASAP7 or BSPDN readiness hook is added to the Product/suite hub.
- No fixed millivolt oracle is a pass criterion.

## Dual-axis status

`status` is the outcome of the tool or analytical runner:
`pass | fail | blocked | not_run`.

`honesty` is the claim class:
`GAP | PROXY | PARTIAL`.

The two axes are independent. In particular, an analytical Ladder B run may
have `status=pass` and `honesty=PROXY`. A missing compact thermal model has a
separate thermal pillar with `honesty=GAP`; it must not inherit the IR claim
class and it must not silently become thermal PASS.

## First track

The first track is the documented recipe
`asap7_proxy_bpr_bs_m89_v0`, which emits the mesh
`asap7_bspdn_proxy_m89`. The IR pillar is `honesty=PROXY`; the thermal pillar
is present with `honesty=GAP` until a declared compact HotSpot model is
stamped. The proxy is independent of OpenROAD issue #10547.

Every proxy report carries `tool_id`, `license_class`, `honesty_reason`, a
non-empty leftover map, and a `mesh_fingerprint`. The fingerprint includes
`rail_model_id`, `via_model_id`, and `thermal_model_id|null`, as well as the
stack/topology/PDK and recipe inputs. A missing rail or via model identifier
is a schema failure.

## Admit boundary

The Lab admit decision is separate from `signoff_all.ok`: a valid IR proxy
with firewall and provenance may be Lab-green while the thermal pillar is
GAP. `signoff_all.ok` never represents a foundry or Product PASS for this
lane.

This document is the unlock record for the later implementation slices. It
does not grant Ladder A or Product access.
