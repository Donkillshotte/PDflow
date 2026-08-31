# Cloud Agent setup log

Durable GitHub log. Newest entries first. If a session expires, read this
file and the PR comments before retrying heavy work.

## 2026-08-31T07:25Z — core bootstrap landed (`cursor/core-cloud-env-86b9`)

| Gate | Result | Evidence |
|---|---|---|
| Prior Set-environment chat | FAIL | Session expired. Krylov MOR on AES ~73k-R mesh; VM thrashing (`cat` timed out). |
| This VM old full `cloud_agent_install.sh` | OK | `install-user.status=0`; log ends `Setup completato.` |
| Recurring Environment Build | OK | [`bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c`](https://cursor.com/dashboard/cloud-agents/builds/bld-20260831-3ea76ff7-6371-421d-9dbf-14e8bb34157c) `SUCCEEDED`. Environment [`6f3814a5-a507-11f1-a7d1-d6b4613131ce`](https://cursor.com/dashboard/cloud-agents/environments/e/6f3814a5-a507-11f1-a7d1-d6b4613131ce). |
| Static `test_cloud_bootstrap.sh` | OK | `CLOUD_BOOTSTRAP_TEST_OK` — install has no AES/DSE/IR/GDS; default profile `core`; `EDA_JOBS=2`; no `nproc` in yosys/dpn. |
| `test_heavy_analysis.py` | OK | 73k-R / Krylov refused without `ALLOW_HEAVY_ANALYSIS=1`; 1000 R allowed. |
| `cloud_agent_smoke.sh` (this VM, already-installed tools) | OK | OpenROAD `26Q2-1164-g08f67ee5ec`, Yosys 0.63, KLayout, STA 3.1.0, ORFS, studio/node_modules. |
| AES F4/slice without flag | OK | both exit 2 `REFUSED` — will not repeat the 73k Krylov crash from setup. |
| Draft Build of this branch | pending | trigger after push; do not overlap with another install |
| Fresh-agent verify | pending | |
| GCD synth smoke (`e2e_relaxed`) | pending | next runtime gate on this VM if tools stay healthy |
| GCD relaxed RTL→GDS | pending | after synth; never AES F4 |

Do **not** run `run_aes_f4.py`, AES DSE, or Krylov on n_r>20k from setup.
