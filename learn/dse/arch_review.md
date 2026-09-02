# Architecture review after TPE v1 (gcd, ibex, aes)

Analysis and plan only. Choices in §4–§6 are pre-registered and are not
revised after data.

Status: §4.1–§4.3 implemented (`tune_transfer.py`, recipe
`place_sparse_setup`). §4.4 (cost-aware slot order) remains out of scope.

Fixed constraints this review does NOT touch: fixed die, real finishes,
one heavy job, unchanged win rule (`win_rule.py`), no new proposers
(LLM/RL/GNN/e-graph), and no Bayesian surrogate of the finish
(`next_iteration_plan.md` §7). Per-design linear gate (I2) remains
the only allowed model, and is already the policy.

## 1. What the numbers say (registry at this date)

Product cooks (`role=knob`) against slot base P0:

| Slot | Base | OFAT/deepen | TPE | Min/finish |
|---|---|---|---|---|
| gcd | −37 ps | 17 cook, 3 win | 8 cook, **0 win** (2 tie, 3 lose, 3 fail) | 0.9 |
| spi | +612 ps | 14 cook, 0 win (10 tie) | not admissible | 0.6 |
| ibex | +22 ps | 10 cook, 4 win | 8 cook, **6 win** (2 fail) | 7.1 |
| aes | −8.9 ps | 8 cook, 3 win | 8 cook, **5 win** (1 lose, 2 STOP) | 7.6 |
| dynamic_node | +3354 ps | 11 cook, 1 win | not launched yet | 4.5 |

Honest note: the 8 TPE aes rows have `runtime_s=0` because restamped
from on-disk logs after the `FLOORPLAN_DEF` fix; true cost is ~50 min.

Facts that matter:

1. **The pad=2 wall was paid 5 times** (3 gcd, 2 ibex), 4 of them after the
   first failed attempt. No finish with pad 2 ever completed, on any design.
2. **Mechanisms transfer partially.** On ≥2 designs:
   `sparse+setup` wins on aes+ibex and does not lose anywhere;
   `setup` wins on aes+ibex (loses on gcd); `cts_fitti` wins on
   aes+dynamic_node; `pad1` wins on gcd+ibex (loses on aes+dn).
   `synth_hier` never won on 5 designs. `aspect/core_*` is always
   `wrong_die`.
3. **GPL_TIMING_DRIVEN=0 depends on design**: on ibex 2 wins (IR −38%),
   on aes 2 STOP at place, on spi lose. Not a wall: an axis to
   sample, and TPE did it.
4. **TPE wins where the slot is open** (ibex: IR to combine; aes:
   timing to close) and does not win where the base is already tight (gcd).
   Not the sampler: on gcd the best misses were constraints (IR −19% with
   slack −7.4 ps), not blind proposals.
5. **The 2 immediate wins on aes (trial 1–2) were combo enqueue** from
   slot deepen. Transferred OFAT information pays on the first shot in TPE.
6. **Gate policy worked where it can**: 2 justified STOP on aes (place WNS −0.78/−0.47 ns). But gcd pad=2 fails passed the place gate (positive WNS) and died at finish: the WNS gate does not see detail/route walls.
7. **dynamic_node is admissible to tune with empty queue**: 1 win only
   (`cts_closer_bufs`), zero combo deepen to enqueue. TPE would start
   almost cold exactly where transfer would matter most.

## 2. Weak points of the current architecture

1. **Warm-start is blind outside the slot** (`slot_rows` filters by
   design). Walls and winning mechanisms do not cross designs: ibex repaid the pad=2 wall gcd had already paid.
2. **No promotion**: a TPE win stays a hash
   (`camp_aes_tpe_2fcef4b2e86a`), not a catalog recipe with a human title
   the next design cover tries first.
3. **Slot order is pure cheap-first**: it does not look at how open the slot is
   nor real finish cost (0.6–7.6 min). gcd was cheap but without headroom; 8 trials spent there were worth ~7 min, but the same information (0 win) was readable after 3–4.
4. **Gate sees only place WNS**: downstream crashes (DPL/route with pad=2) are not predicted nor recorded as a wall.
5. **Tuner does not distinguish** “failed on known wall” from “failed by chance”: a failed fingerprint is only a locally infeasible trial.

## 3. Techniques evaluated against fixed constraints

| Technique | Scope | Why |
|---|---|---|
| Cross-design transfer (walls + order prior) | **YES, first** | Direct evidence: pad=2 repaid, mechanism matrix, aes trial 1–2. Zero new dependencies. |
| Win → catalog promotion | **YES** | Product is recipes. `sparse+setup` is already a ≥2-design candidate without lose. |
| Cost-aware slot order | **YES, small** | Expected win per minute: dynamic_node (4.5 min, open slot) before returns on gcd. |
| Multi-fidelity Bayesian (BOHB/Hyperband) | NO now | Forbidden by §7 with these numbers. Linear I2 gate is already poor multi-fidelity and worked (2 justified STOP). |
| Change sampler (MOTPE/NSGA-II/CMA-ES) | NO | Sampler was not the bottleneck in any slot. gcd failed for headroom and walls, not proposal. |
| Finish surrogate (GP/GNN) | NO | Frozen §7: underdetermined (max ~34 finish per design). Revisit only above ~40 finish per-design. |
| LLM/RL proposer, white-box OpenROAD | NO | Lab, frozen. |
| New space axes (routability, target density) | After | Consume paid information first; space v2 only after measuring transfer. |

## 4. Proposal (priority order, pre-registered)

1. **Wall memory** (`tune_transfer.py`, new, without Optuna).
   From global registry: a mechanism with ≥2 fail/never-win on ≥2
   designs (today: `cell_pad=2`, `synth_hier`) becomes a wall. Tuner imports it as infeasible trial and does not repropose; `enqueue` skips it.
   Test without ORFS: on ibex live replay, trials 5–6 (pad=2) are not cooked.
2. **Cross-design order prior.** At warm-start, win vectors from other designs (same space, mechanism win on ≥2 designs) are enqueued after slot deepen combos, max 3. Absolute scores from other designs are not imported as completed trials: different bases, different distributions. Only trial order transfers.
3. **Promotion to recipe.** A mechanism win on ≥2 designs without lose
   becomes a catalog recipe with human title. First candidate:
   `sparse+setup` → «Sparser place + setup margin». Next slot cover tries it like other recipes.
4. **Cost-aware slot order in tune.** Among admissible slots, priority to
   (slot openness) / (median min/finish) instead of pure cheap-first.
   Openness = base not very-closed, or IR/leakage with ≥10% margin never reached. With today's numbers it picks dynamic_node.

What stays as-is: space v1 (7 axes), score and constraints from `win_rule`,
`cook_one`, phase T1, fingerprint, budget ≤8 finish per slot, stop on
plateau, spi not admissible.

## 5. What we do NOT do (and when to revisit)

- No finish surrogate below ~40 finish per-design.
- No new sampler: TPE stays until it is demonstrably the bottleneck (one open slot, no walls, where TPE does not find wins a grid finds).
- No new v1 axes. Expanding space is v2, after transfer.
- Verilog is not rewritten; floorplan does not move.

## 6. Success criterion (frozen)

Transfer is a method success if, on the next live slot
(dynamic_node, ≤8 finish):

1. Zero cooks on already-known walls (pad=2, synth_hier).
2. At least one cross-design enqueue among the first 3 trials.
3. First win (if the slot has one) within 3 cooks, as aes did with combo enqueue — or honest verdict that the slot has no win in space v1.
4. «Sparser place + setup margin» exists in catalog with label test, and cover proposes it on a design that has not tried it.

If (3) is no, do not change sampler and do not add a model: declare that order transfer is not enough on that slot and measure the next before touching architecture.
