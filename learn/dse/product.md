# Product vs lab

Fixed choices (not revised after data).

## Product

Search physical knobs (and ABC area synthesis method) on the **official
netlist**. Do not rewrite project Verilog.

The **floorplan is fixed**: same total area, same size, same shape as the
official run. Do not touch `CORE_UTILIZATION`, `CORE_ASPECT_RATIO`,
`DIE_AREA`. Product cooks lock `DIE_AREA`/`CORE_AREA` from the official
DEF. Historical runs that moved the die remain in lab (`wrong_die`); they
are not product wins.

Old DSE (e-graph, rewrite, IR F4, refine) remains **lab**. Not the
product. Not deleted; does not decide wins.

## Victory (new, includes power, leakage and IR)

Compare a challenger with the base of the same design and same clock.

- **Wins** if timing is not worse than 5 ps **and** at least one of area,
  power, leakage, IR worst is better than 10% **and** none of the four
  is worse than 10%.
- **Wins** also if timing is better than 5 ps **and** none of the four
  is worse than 10%.
- **Wins** if it closes (WNS≥0) and base does not, without worsening
  area/power/leakage/IR by 10%.
- **wrong_die** (lab, not a win) if it moved total area, size or shape
  of the official floorplan.
- **Loses** if timing is worse than 5 ps, **or** area or power or
  leakage or IR is worse than 10%.
- Otherwise **tie**.

The H1–H6 rule from P0–P7 campaign is not rewritten. This applies to the
product from here on.

## Cycle

One coordinator, no `if design == …`. Fixed RTL: explore from synthesis
onward. Registry review → decides next move:

1. **Cover.** If a catalog recipe is missing, cook it (from cheapest
   finish). Skip `synth_area` and **all** floorplan recipes.
2. **Improve.** If a slot has no win, invent: combos on open die, new
   knobs on already-closed die.
3. **Tune.** TPE on same die, same oven (CTS/route/finish). Replaces
   deepen in default. Frozen plan: `tpe_plan.md`. `--deepen` remains
   override (2-axis grid, not TPE).
4. **Stop.** Catalog covered, slots without wins exhausted, TPE budget
   finished or slot not admissible (e.g. spi already closed and without
   win).

`--cover-all` / `--improve` remain overrides. Default is review.

**spi @ 1 ns is exhausted** as slot without win. Do not launch TPE there.
Do not rewrite Verilog.

No TPE trial changes these choices: space, score, die pin and `cook_one`
follow `tpe_plan.md`.

Reading index: `docs/README.md`. After TPE v1: `arch_review.md`.
