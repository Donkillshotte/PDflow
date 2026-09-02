# Results (honest)

Registry: `learn/sim/dse/campaign_experiments.jsonl`.
Verdict = `win_rule`, not the TPE score.

Percentages = metric change vs the slot base.
Negative on area / power / leakage / IR = smaller (better).

## Per slot

| Slot | Base | OFAT | TPE | Min/finish |
|---|---|---|---|---|
| gcd | −37 ps | 3 wins (Denser placement, Padding +1, …) | 8 cooks, **0 new wins** | ~0.9 |
| spi | +612 ps | 0 wins (10 ties) | not admissible | ~0.6 |
| ibex | +22 ps | 4 wins | 8 cooks, **6 new wins** | ~7 |
| aes | −8.9 ps | 3 wins | 8 cooks, **5 new wins** | ~8 |
| dynamic_node | +3354 ps | 1 win (Tighter clock buffers) | not yet | ~4.5 |

## What worked

- **Ibex:** OFAT combos (sparser place + pad, denser place + pad) and IR mixes
  down to −38%, slack within 5 ps. Area / power / leakage ~0 or under +10%.
- **Aes:** closes timing (base was open). Area / power / leakage rise a bit
  (up to +7%), all under 10%. SHA `6_report` = disk truth.
- **Same-slot enqueue:** the 2 immediate aes wins were combo deepen
  (Sparser placement + Setup margin; Setup + Tighter clock buffers).

## What did not work

- **Gcd:** continuous TPE did not beat OFAT. Close miss: IR −19% with
  slack −7.4 ps (constraint, not a blind proposal).
- **Cell padding +2:** 5 fails (3 gcd, 2 ibex). Place may close;
  finish does not. Now a wall.
- **Sparser placement + CTS 80 on aes:** lose, slack −30 ps.
- **Placement without timing-driven on aes:** STOP at place (WNS −0.78 / −0.47 ns).
- **Hierarchical synthesis:** 0 wins on 5 designs. Wall.

## Transfer (after live runs)

`learn/dse/tune_transfer.py`: pad=2 and synth_hier are not recooked;
up to 3 cross-design win mechanisms queued for TPE.
«Sparser placement + setup margin» is a catalog recipe.

Transfer success criterion (frozen in `arch_review.md`):
on the next live slot, zero pad=2, one cross-design enqueue in the first 3,
first win within 3 cooks — or an honest verdict that the slot has no win.
