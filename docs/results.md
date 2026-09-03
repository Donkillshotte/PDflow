# Results (honest)

Registry: `learn/sim/dse/campaign_experiments.jsonl`.
Verdict = `win_rule`, not the TPE score.

Percentages = metric change vs the slot base.
Negative on area / power / leakage / IR = smaller (better).

Live counts below are `win_rule` on the JSONL, not archived prose.

## By slot

| Slot | Base | OFAT / catalog | TPE | Min/finish |
|---|---|---|---|---|
| gcd | −37 ps | **3 wins** (`q1_d25u35`, Cell padding +1, Sparser placement + setup margin). No `place_denser` catalog row. | 8 cooks, **0 new wins** | ~0.9 |
| spi | +612 ps | 0 wins (ties). `place_sparse_setup` is a tie (slack +1.1 ps, no 10% axis). | not admissible | ~0.6 |
| ibex | +22 ps | 4 catalog wins | 8 cooks, **6 new wins** (10 total) | ~7 |
| aes | −8.9 ps | 3 catalog wins | 8 cooks, **5 new wins** (8 total) | ~8 |
| dynamic_node | +3354 ps | 1 win (Tighter clock buffers). `place_sparse_setup` is a **lose** (slack +38 ps, IR +14.6%). | next live slot (`arch_review.md` §6) | ~13 |

Coordinator dry-run after this cover: **catalog holes empty**. Decision is TPE. Frozen success criterion is `dynamic_node`, not gcd (gcd is also admissible). Do not TPE spi.

## What worked

- **Ibex:** OFAT combos (sparser place + pad, denser place + pad) and IR mixes
  down to −38%, slack within 5 ps. Area / power / leakage ~0 or under +10%.
- **Aes:** closes timing (base was open). Area / power / leakage rise a bit
  (up to +7%), all under 10%. SHA `6_report` = disk truth.
- **Same-slot enqueue:** the 2 immediate aes wins were combo deepen
  (Sparser placement + Setup margin; Setup + Tighter clock buffers).

## What did not work

- **Gcd:** continuous TPE did not beat OFAT. Close miss: IR −19% with
  slack −7.4 ps (constraint, not a blind proposal). Catalog
  `place_sparse_setup` later won: IR −11% with slack −4.1 ps (inside 5 ps).
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
