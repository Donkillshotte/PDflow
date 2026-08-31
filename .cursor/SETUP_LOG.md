# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-08-31T08:41Z — timeout vs RAM

Tried raising timeout and RAM so AES F4 could run on this Cloud Agent.

| Item | Result |
|---|---|
| VM RAM | **cannot raise** — 15 GiB / 4 CPU / swap 0. `environment.json` has no memory/cpu fields; Cursor schema `unevaluatedProperties: false`. `swapon` fails. Docs: Enterprise support only. |
| F4 timeout | **can raise** — `PDN_SOLVE_TIMEOUT_S` (600 / 1800). Session timeout cannot. |
| RSS budget | AES Krylov 73k-R ~14.5 GiB **REFUSED** even with `ALLOW_HEAVY_ANALYSIS=1`. DirectLU estimated 828 MiB, allowed. |
| GCD F4 DirectLU `timeout=600` | **OK** `n_r=4656`, droop 16.642 mV, static 12.887 mV, 16 s, RSS 395 MiB |
| DirectLU 54 289-node 2D grid | **OK** factor 0.36 s, 130 solves 0.56 s, RSS 125–164 MiB |
| AES F1 remap | **OK** ~8 s |
| AES write_pg_spice | **OK** `n_r=66295` `n_i=9964` in 5.5 s |
| AES F4 DirectLU on that mesh | **FAIL** — pod recycled during `solve_f4` (no `aes_f4_direct_timeout.json`). Do not retry Krylov. Retry LU only with `prlimit` RSS cap. |

Knob: `PDN_SOLVE_TIMEOUT_S`. Picker prefers DirectLU when RSS fits; Krylov stays blocked on 15 GiB.

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
