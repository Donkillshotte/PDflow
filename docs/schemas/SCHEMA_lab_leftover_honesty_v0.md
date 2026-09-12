# Lab leftover and honesty schema v0

The schema separates whether a tool ran from what the evidence can honestly
claim.

```text
status: pass | fail | blocked | not_run
honesty: GAP | PROXY | PARTIAL
honesty_reason: non-empty string
leftovers: [{ id: string, message: string, count?: number }]
ok_claim: false
tool: string
license_class: string
deck_id?: string
pdk: asap7
surface: lab | lab_asap7
product_win: false
productWin: false
win_eligible: false
comparable_to_gold_ir: false
pillars:
  ir: { status, honesty, honesty_reason, leftovers, ... }
  thermal: { status, honesty, honesty_reason, leftovers, ... }
signoff_all: { ok: boolean, ... }
```

`honesty=PROXY` is never serialized as `status`. On the first Ladder B track,
the IR pillar is `honesty=PROXY` and the thermal pillar must be present with
`honesty=GAP` (or a later declared thermal `PROXY`). The thermal axis never
inherits IR honesty.

The analytical proxy may have `status=pass` and `lab_admit.ok=true`; this
means the analytical invocation and Lab firewall passed. It does not make
`signoff_all.ok` true and it cannot create Product eligibility. A GAP pillar
must never become a PASS verdict merely because another pillar ran.

PROXY rows require `tool_id` and `license_class`. Calibre, FakeRAM, BeGAN,
and AGPL evidence cannot promote a report. Missing or unavailable inputs are
represented as `blocked`/`not_run` with an explicit leftover, never as a
historical green result.
