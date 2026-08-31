# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-08-31T07:45Z — goal complete

| Gate | Result | Evidence |
|---|---|---|
| Prior Set-environment chat | FAIL | Session expired. Krylov MOR on AES ~73k-R mesh; VM thrashing. |
| Recurring Build (old full install) | OK | [`bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c) |
| Static bootstrap + AES refuse | OK | `CLOUD_BOOTSTRAP_TEST_OK`; `run_aes_f4.py` exit 2 |
| GCD relaxed RTL→GDS (this VM) | OK | `6_final.gds` 508K, DRC 0, WNS 0.00, setup viol 0, SDC 2.0 ns |
| Draft Build core | OK | [`bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c) — skipped OpenSTA+libdpn, `CLOUD_SMOKE_OK`, install exit 0 |
| Fresh agent on that Build | OK | Agent `bc-95543107-7d79-5ef7-b947-5349568b62e7` booted from the draft Build. Smoke OK, AES refused, `libdpn` absent, OpenSTA standalone absent, GCD synth `1_synth.odb` 608K |

No AES / Krylov / 73k-R mesh was run in this goal.

## 2026-08-31T07:22Z — GCD relaxed RTL→GDS OK (parent VM)

`./scripts/run_gcd_e2e_relaxed.sh finish` — variant `e2e_relaxed`, SDC **2.0 ns**.

| Item | Result |
|---|---|
| `1_synth.odb` | OK, chip area 628.824 µm², 35× DFF_X1 |
| `6_final.gds` | OK, 508K |
| DRC `5_route_drc.rpt` | **0** lines |
| STA finish | WNS 0.00, TNS 0.00, setup viol **0**, `period_min` 0.83 ns |
| Peak RSS (detail route) | 861 MB |
