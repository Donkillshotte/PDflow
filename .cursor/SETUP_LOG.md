# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-08-31T15:33Z — GCD finish + per-solver IR + AES F5-lite OK

Safe subset under `prlimit --as=8GiB`. No AES Krylov. 73k-R / 6.954 mV untouched.

| Item | Result |
|---|---|
| GCD FlowLab `make finish` 0.46 ns | **OK** ~52 s, RSS ~913 MiB, `6_final.odb/gds/spef` |
| Dynamic IR A DirectLU | **OK** `n_r=5816`, droop **6.075 mV**, `A_direct_be` |
| Dynamic IR B SA-AMG | **OK** 6.075 mV, \|A−B\| ≈ 0 |
| Dynamic IR D RAS | **OK** 6.075 mV, \|A−D\| ≈ 0 |
| Dynamic IR C Krylov m=96 | **OK** 6.092 mV, \|A−C\| = 0.017 mV, RSS ~677 MiB |
| AES F5-lite 2 DRT, no CTS | **OK** id `25176b74aba8`, WNS **−2.0546 ns** (OpenSTA SPEF), SDC AES 0.82 ns, `top=aes_cipher_top`, `clock=ideal`, 53381 rc segs, 1106 s, DRT peak ~1074 MiB. Prior fails: DRT-0305 / TCL SIGNAL / 540 s timeout. |
| 73k-R pin | `febe6804241c` still `n_r=73139`, static **6.954 mV**, dynamic GAP |
| `test_designs.py` | **ALL PASSED** including live F5 SDC/top/clock and cloud 17.745 mV |

This FlowLab Dynamic IR is **6.075 mV**, not gold 45.298. Re-run F5: `ALLOW_HEAVY_ANALYSIS=1 ./scripts/run_aes_f5_lite_cloud.sh` (default timeout 1200 s). Do not set `AES_F5_ALLOW_CTS=1`.

Still out of scope: AES Krylov, F5-CTS, full AES DSE controller, gold restamp, combined A+B+C+D+VSS+electrothermal, uncapped `solve_f4`.

## 2026-08-31T13:50Z — analysis draft Build SUCCEEDED

[`bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914) **SUCCEEDED** (~19 min). Draft; warming skipped; does not become the default boot snapshot until activated.

| Check | Result |
|---|---|
| Profile | `Profilo analysis EDA_JOBS=2` |
| OpenSTA standalone | skipped |
| `libdpn.so` | OK, `ALL dpn_test PASSED` (synthetic only) |
| Studio npm | 453 packages |
| Smoke | `CLOUD_SMOKE_OK` (openroad 26Q2, yosys 0.63, klayout, sta 3.1.0) |
| Install | exit 0, snapshot ready |
| Heavy work during install | none (no AES / DSE / Krylov) |

## 2026-08-31T13:35Z — remaining jobs under 15 GiB

Executed the four remaining safe items. No Krylov. No overwrite of 73k-R / 6.954 mV.

| Item | Result |
|---|---|
| GCD FlowLab DSE `./scripts/run_dse_gcd_cloud.sh` budget 45 s, `prlimit --as=8GiB` | **OK** resume, 113 candidates, 2.41 s, RSS 56 MiB, exit 0. Did not wipe memory (`DSE_FRESH` refused). |
| AES F1–F3 `AES_SLICE_SKIP_F4=1` under 8 GiB | **OK** reuse F1 `c6c1a7e0ad2c` / F3 WNS −1.3258 ns / GPL `bd74975200c1`, 0.20 s. F4 left to the cloud wrapper. |
| AES F4 cloud wrapper | Without flag: **REFUSED** exit 2. With flag: **reuse** `8c589d0cc392` droop 17.745 mV in 0.42 s (no re-solve, `PDN_DISABLE_KRYLOV=1`). |
| Ingest new PDN candidate | **OK** id `8c589d0cc392`, `n_r=66295`, static 12.953 mV, droop **17.745 mV**, knobs `via=cloud_agent_directlu`. 73k-R row `febe6804241c` still 6.954 mV, dynamic GAP. Idempotent second ingest. `test_designs.py` PASSED including the new cloud asserts. |
| Install profile | `environment.json` now `PD_FLOW_PROFILE=analysis EDA_JOBS=2`. |
| Draft Build analysis | **SUCCEEDED** [`bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b83be3d2-8545-44ca-af90-90bd2e812914) — `CLOUD_SMOKE_OK`, `libdpn` + `dpn_test`, OpenSTA skipped. Draft only. |

Not run: AES F5, full AES DSE controller, gold 45.298, `run_dynamic_ir.sh` AMG+Krylov+RAS, uncapped `solve_f4`.

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
| AES static IR (parse+LU) | **OK** 12.953 mV, 49 282 nodes, RSS 201 MiB |
| AES F4 DirectLU dynamic | **OK** with `prlimit --as=8GiB` and `PDN_SOLVE_TIMEOUT_S=90`. Droop **17.745 mV**, static 12.953 mV, `A_direct_be`, 48 s, not gold. First uncapped attempt recycled the pod. |
| AES Krylov | still **REFUSED** on 15 GiB RSS budget |

Timeout yes (`PDN_SOLVE_TIMEOUT_S`). RAM no. AES F4 is testable here with DirectLU + RSS cap, not with Krylov. Re-run: `ALLOW_HEAVY_ANALYSIS=1 ./scripts/run_aes_f4_cloud.sh` (8 GiB `prlimit`, 90 s timeout). Do not overwrite the 6.954 mV / 73k-R row in `memory_aes.jsonl` — `test_designs.py` pins that mesh.

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
