# Next iteration write-up (Q0–Q4)

Plan: `learn/dse/next_iteration_plan.md` (sha in `eval_policy.json`).
Win criteria §5 and I1–I5 bars are **frozen**. Source of truth: `6_report.json`.

## Product verdict

Physical knobs beat the ORFS default on this set. The first frozen §5
wins of the whole campaign come from `PLACE_DENSITY_LB_ADDON` /
`CORE_UTILIZATION`, not from DSE netlists or `abc_speed`.

| Design | Clock | Winner | Why |
|---|---:|---|---|
| gcd | 0.46 ns | `camp_gcd_q1_d25u35` | slack ±1.2 ps vs base, area **−10.5%** (842 vs 940 µm²) |
| ibex | 2.20 ns | `camp_ibex_q1_d20u60` | WNS **+42 ps** vs base +22 ps (area ~unchanged) |

Also §5 wins on ibex: `d15u50` (+36 ps) and `d25u50` (+40 ps).

## I1–I5

| ID | Outcome |
|---|---|
| I1 | **supported** (4 §5 wins; gcd range 8.4 ps, ibex 26.2 ps) |
| I2 | **supported** (13/13 Q* holdout within ±2σ per-design) |
| I3 | **supported** (STOP precision 100% on 11 already-paid rejects) |
| I4 | **not supported** (Q4 at 0.55 ns closes but area ≈ base) |
| I5 | **supported** (place Spearman 0.968 ≥ 0.6) |

## Q0

Zero-cost on P0–P7 registry. Place→finish Spearman 0.978 already before Q1.
The place-DP gate is an economical signal; F1 remains inverted on gcd (H1).

## Q1 knob grid

Offsets from config defaults (LB 0.20, gcd util 35, ibex util 50).

GCD 8 points (center already known). WNS range 8.4 ps. Only win: LB=0.25 / util=35.

Ibex 4 points. Three beat base WNS; util 40 is the only regression
(−6 ps). Range 26.2 ps.

## Q2 policy

`learn/dse/fidelity_policy.py`: STOP if `place + per_design_residual` is
worse than base by >2σ and outside the ±5 ps band. Wired to the
Next Level scheduler. I3 is a replay on DSE B/C already paid in P0/P1:
11/11 STOP correct. Q1 knobs (place ~+10–15 ps) remain EVALUATE,
correctly: one of them is a win.

`Candidate.delta` already existed (`qor_delta` vs parent). No DesignState.

## Q3 schema

No second state. Consumed what was there:

- `SolveResult` + `CurrentScenario` (`REAL/PARTIAL/SYNTHETIC/ABSENT`)
- `Candidate.pred` / `Candidate.delta`
- `pareto_status()` → dominated/non-dominated × feasible/infeasible/uncertain

## Q4 area-regime

`camp_gcd_q4_d25u35_c055` at the clock where A closes (0.55 ns): WNS +13.02 vs
base +13.36 (tie), area 698 vs 697. **I4 false** on this point: the
Q1 area advantage at 0.46 ns does not survive when both close
at the same util.

## Phase success

Both branches of the frozen criterion:

1. Real §5 wins (gcd area, ibex WNS).
2. Policy STOP ≥80% (100% on 11) + I2/I5 measured.

Gold 45.298 unrestamped. `febe6804241c` untouched. No overwrite
`flowlab`. No AES Krylov. No AI proposer.

## Multi-axis QoR (finish `6_report`, not slack only)

§5 remains WNS / area-tie / first-to-close. Power and leakage are extra axes
read from `finish__power__*` — the registry did not copy them before.

| Variant | §5 | ΔWNS | Δarea | Δpower | Δleak |
|---|---|---:|---:|---:|---:|
| gcd `d25u35` | win | −1.2 ps | **−10.5%** | **−12.7%** | **−14.1%** |
| ibex `d20u60` | win | +20 ps | −0.2% | −0.3% | ~0% |
| ibex `d25u50` | win | +17 ps | −0.1% | ~0% | ~0% |
| ibex `d15u50` | win | +14 ps | ~0% | ~0% | ~0% |

On gcd the area win is also a power/leakage win (same netlist, die
unchanged, less buffering). On ibex the win is almost slack-only: total
power ~108 mW, unchanged.

IR (worst VDD drop) and GRT wirelength are extra axes read from
`6_report` / `5_1_grt.json`. There is no overflow fraction in these ORFS JSON
(`congestion_*_s` are runtimes). Table with **reference flow absolute values**
+ challenger + Δ: `learn/dse/qor_compare.md`.

| Variant | §5 | IR ref → cand | ΔIR | GRT WL ref → cand | ΔWL |
|---|---|---|---:|---|---:|
| gcd `d25u35` | win | 6.67 → 6.15 mV | **−7.7%** | 7589 → 6971 | **−8.1%** |
| ibex `d20u60` | win | 123.8 → 86.2 mV | **−30.3%** | 438851 → 420930 | **−4.1%** |

On ibex the slack win is also lower IR/WL; power stays ~flat. §5 does not
use IR/WL. 12 reference slots, 31 challengers (including J1 spi), all
with IR and GRT WL. The two J1 cooks are not §5 wins.

## Next direction (not design-based)

Do not update the Verilog. Update the **synthesis method** of
new challengers: ABC area (`learn/dse/synth_method.json`), because the wins
are all on the official netlist. Design-agnostic knob catalog
(synth / floorplan / place / repair / CTS): `learn/dse/knob_catalog.py`.
Readable names (what it does + payoff) in `qor_compare.md` § Recipes.
Plan: `learn/dse/joint_recipe_plan.md`. Extra metrics: IR mean, cell
density, congestion = WL/core.

## J1 transfer (spi, not used to choose knobs)

Two catalog recipes, same netlist `camp_spi_base`, place-first,
finish only because policy said EVALUATE. Names = what they do.

| Recipe | Knob | §5 | WNS | Area | Buffer | IR mean | GRT WL |
|---|---|---|---:|---:|---:|---:|---:|
| ORFS default | util 8, LB 0.20, TNS 100 | — | +612.2 ps | 267.6 | 22 | 0.53 mV | 2257 |
| Denser placement | LB 0.20→0.25 | tie | +610.7 ps (−1.5) | 268.1 (+0.2%) | 22 | 0.56 mV | 2205 |
| Half TNS repair | TNS 100→50 | no-op | +612.2 ps | 267.6 | 22 | 0.53 mV | 2257 |

No §5 win. spi is already closed by 612 ps on a sparse die (density 9.4%,
util default 8 for PDN-0185). The gcd lever “denser → fewer buffers”
has nothing to act on; halving TNS repair is a no-op when
TNS is already 0 (`6_report.json` byte-identical to default, sha
`b8826a8ee5356ac0`, different inode). Catalog, policy, and names work:
transfer is design-sensitive even though knobs are design-agnostic.

Did not cook the combo (would be a no-op) nor aes/ibex/dynamic_node.

## Full catalog on spi (J2)

The other 8 recipes were run. None beat default enough
to count as a win.

| Recipe | What changes | Result on spi |
|---|---|---|
| Sparser placement | wider cells | almost the same; wires +3% |
| Cell padding +1 | extra space between cells | almost the same; wires +5% |
| Setup margin | asks for 50 ps more | identical (already on time) |
| Denser clock buffers | clock every 80 µm | identical |
| Wider floorplan | 2:1 rectangle | worse: area +3%, IR up |
| Tighter core | smaller die (util 18) | area −2.6%, wires −18%, slack +3 ps, worse IR. Not a win |
| Looser core | larger die (util 5) | area +2%, slack unchanged |
| Hierarchical synthesis | Yosys without flatten | identical (Verilog already flat) |

Closest is **Tighter core**. Not enough: to win you need slack
better than 5 ps, or equal slack and area −10%.

All recipes are now run, not just written. On spi (already on
time, empty die) almost all do nothing. Wins remain gcd and ibex.
