# Joint recipe plan (synthesis + physical stages), design-agnostic

Plan only. No finish starts from this commit. §5 remains frozen.

## What we learned (not rewritten)

- §5 wins come from the **official netlist** (ABC area) + physical knobs.
- ABC delay and DSE rewrites: 0 wins. Project Verilog is not touched.
- Update the **synthesis method** of *new* challengers: ABC area,
  not ABC speed, unless explicitly a control.
- Knobs are **offsets from config default**, equal on every design.
  There is no `if design == gcd` branch.

## Space (catalog)

`learn/dse/knob_catalog.py`, stages: synth, floorplan, place, repair, CTS.
Each recipe has `title` / `does` / `payoff`. Filesystem id is
`camp_<design>_<recipe_id>` (readable). Combine at most 2 axes per
cook; place-first, finish only if policy says EVALUATE.

## Metrics to always report (not in §5 verdict)

WNS, TNS, area, power, leak, **IR worst**, **IR mean** (whole die),
cell density (util%), congestion as **WL/core** (ORFS JSON has no
overflow fraction), GRT WL, fmax, setup viol, repair buffers.

## Names

Never just `d25u35`. Tables show `title`. Payoff lives in
`qor_compare.md` § Recipes.

## Success

A §5 win on a design *not* used to choose knobs (design-agnostic
transfer), or an honest measurement that a new axis (aspect, CTS,
repair) does not move finish. Tie is a valid answer.
