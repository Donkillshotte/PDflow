# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-08-31T07:22Z — GCD relaxed RTL→GDS OK (this VM)

`./scripts/run_gcd_e2e_relaxed.sh finish` — variant `e2e_relaxed`, SDC **2.0 ns**.

| Item | Result |
|---|---|
| `1_synth.odb` | OK, chip area 628.824 µm², 35× DFF_X1 |
| `6_final.odb` / `.def` / `.gds` | OK (`6_final.gds` 508K) |
| DRC `5_route_drc.rpt` | **0** lines |
| STA finish | WNS 0.00, TNS 0.00, setup viol **0**, `period_min` 0.83 ns |
| Peak RSS (detail route) | 861 MB — far from the AES 73k Krylov thrash |
| Wall | ~30 s synth+P&R+GDS on this already-installed VM |

This proves the **small E2E** path. It does **not** yet prove a *fresh* agent booting from the new core-profile Build.

## 2026-08-31T07:25Z — core bootstrap landed (`cursor/core-cloud-env-86b9`)

| Gate | Result | Evidence |
|---|---|---|
| Prior Set-environment chat | FAIL | Session expired. Krylov MOR on AES ~73k-R mesh; VM thrashing (`cat` timed out). |
| This VM old full `cloud_agent_install.sh` | OK | `install-user.status=0`; log ends `Setup completato.` |
| Recurring Environment Build | OK | [`bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c) `SUCCEEDED`. |
| Static `test_cloud_bootstrap.sh` | OK | `CLOUD_BOOTSTRAP_TEST_OK` |
| `test_heavy_analysis.py` | OK | 73k-R / Krylov refused without flag |
| `cloud_agent_smoke.sh` | OK | OpenROAD 26Q2, Yosys 0.63 |
| AES F4/slice without flag | OK | both exit 2 `REFUSED` |
| Draft Build of this branch | IN_PROGRESS | [`bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-b6044d87-06e0-4138-abcf-b820da2aff9c) |
| Fresh-agent verify | pending | wait for draft SUCCEEDED |
| GCD synth + relaxed RTL→GDS | OK | see section above |

Do **not** run `run_aes_f4.py`, AES DSE, or Krylov on n_r>20k from setup.
