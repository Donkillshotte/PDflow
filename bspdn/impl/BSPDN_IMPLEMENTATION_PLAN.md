# ASAP7 + BSPDN implementation plan

Status: Lab-only implementation tracker. This file records the contract
implemented by the repository; it does not authorize Product evaluation or a
foundry claim.

## Charter and hard locks

- Surface is `lab` or `lab_asap7`; the Product engine and suite hub remain
  outside this lane.
- `product_win`, `productWin`, `win_eligible`, and
  `comparable_to_gold_ir` are always `false`.
- The first executable track is Ladder B, using recipe
  `asap7_proxy_bpr_bs_m89_v0` and mesh `asap7_bspdn_proxy_m89`.
- Ladder B reports use `honesty=PROXY` for IR and a separate thermal pillar
  with `honesty=GAP`. `status` remains a tool outcome and never contains
  `PROXY`.
- `asap7_bpr_chip` and `asap7_bspdn_chip` are GAP-reserved and emit-forbidden
  until Ladder A has real BM*/BPR LEF/LIB, tech LEF, ORFS PDN setup, RC
  evidence, a mesh fingerprint, and a DRC map.
- ASAP7-BB is citation/education only until public LEF, LIB, tech LEF, and
  ORFS configuration inputs are available.
- Ladder B is independent of OpenROAD issue `#10547`; that issue is only
  Ladder C plumbing and never gates a proxy run.
- No fixed millivolt value is a pass oracle, and a proxy report never writes a
  finish artifact or a Product gold-IR report.

## Implemented slices

### D0/D1 — docs and schema contract

The public contract is frozen in `docs/asap7_eval_contract.md`. The
versioned field definitions are in:

- `docs/schemas/SCHEMA_ir_oracle_v0_1.md`
- `docs/schemas/SCHEMA_lab_leftover_honesty_v0.md`
- `docs/schemas/SCHEMA_lab_registry_bspdn_v0.md`
- `config/pdflow/schemas/lab-bspdn-report.schema.json`

### I0 — existing FS ASAP7 stamp

The existing `lab_asap7_chip_pdn` path remains Lab-only and carries the
firewall fields. Its `mesh_id` is `asap7_chip_tier_b`; it is not renamed to a
proxy mesh and is not comparable to a Ladder B report.

### I1 — Ladder B PROXY

`learn/scripts/lab_asap7_bspdn_proxy.py` emits a self-contained analytical
report from the canonical recipe. It records:

- the recipe/model IDs and SHA-256 recipe provenance;
- `rail_model_id`, `via_model_id`, and explicit `thermal_model_id: null` in
  the fingerprint inputs;
- `status=pass` for a completed analytical invocation,
  `honesty=PROXY`, `ok_claim=false`, and a non-empty leftover map;
- independent IR and thermal pillar records;
- `lab_admit.ok=true` while `signoff_all.ok=false`;
- no `_chip` emission and no finish-tree writes.

The paired validator is
`learn/scripts/validate_lab_asap7_bspdn_proxy.py`; focused contract coverage
is in `learn/scripts/test_asap7_bspdn_proxy.py`.

### I2 — `/lab` evidence surface

The Studio Lab surface reads the proxy report separately from the historical
FS report, displays claim class before tool outcome, and renders IR and
thermal honesty independently. Proxy evidence is not wired into
`/api/suite` or Product scoring.

The Lab-only registry projection is implemented by
`learn/scripts/lab_asap7_registry.py`; `/api/runs?surface=lab_asap7` exposes
the same guarded proxy row without forwarding it to the Product run list.

### I3 — leftover and thermal evidence

Community ASAP7 DRC/LVS/PKG emitters carry explicit tool status, claim class,
named leftovers, provenance, and `ok_claim=false` while retaining their
legacy fields for existing Lab consumers. `learn/scripts/lab_asap7_thermal.py`
can stamp an explicit `status=not_run`, `honesty=GAP` thermal row. It emits no
temperature or millivolt oracle; a future HotSpot PROXY must declare
`model_id` and `powermap_kind`.

### I4/I5 — gates

Community DRC/LVS/PKG evidence remains leftover-aware and non-promoting.
Relative Lab DSE must use strict same-mesh identity, including the fingerprint
and ASAP7 design/nickname. Ladder A is not implemented by this slice:
`*_chip` emitters stay disabled until the physical checklist is stamped.

## Required test matrix

The implementation must keep the following invariants green:

| ID | Invariant |
| --- | --- |
| T1–T4 | Enum, firewall, proxy honesty, and non-empty leftover checks |
| T5–T10 | Strict same-mesh and cross-topology/PDK comparison refusal |
| T11–T16 | No mV oracle, no gold restamp, oracle firewall, and suite isolation |
| T17–T20 | Product-surface refusal and independent IR/thermal axes |
| T21–T24 | `_chip` gate, `#10547` independence, fingerprint IDs, recipe gate |
| T25–T27 | Thermal GAP admit rule, provenance, and ASAP7-BB EDU-only rule |

Analytical unit fixtures may exercise a two-node RC or area-R calculation,
but they are excluded from suite QoR pins.

## Unlock boundary

Further Ladder A work requires an explicit Platform/ORFS stamp for checklist
items A1–A6 and a go from Alessandro/CoS. Until then, a test or caller that
requests `asap7_bpr_chip` or `asap7_bspdn_chip` must fail closed.
