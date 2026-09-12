# Script catalogue

Root launchers:

| Script | Purpose |
|---|---|
| `../install.sh` | install the complete native Linux workstation |
| `install_pdflow.sh` | implementation of the native installer |
| `install_node_runtime.sh` | install/check the pinned user Node runtime |
| `install_bazelisk.sh` | install/check the pinned native Bazelisk helper |
| `pdflow` | launch the AppImage, browser Studio, or native verification |
| `run_studio.sh` | start the local Studio app |
| `run_design_finish.sh` | run an isolated design finish |
| `run_dse_gcd_cloud.sh` | run the bounded DSE wrapper |
| `run_dynamic_ir_cloud.sh` | run Dynamic IR with the heavy-analysis guard |
| `run_aes_f4_cloud.sh` | run the AES F4 analysis wrapper |
| `run_aes_f5_lite_cloud.sh` | run the AES F5-lite wrapper |
| `learn_physical_design.sh` | launch course lessons |
| `test_course.sh` | course structure and smoke tests |
| `test_all_phases.sh` | phase and signoff checks |
| `test_installer.sh` | offline installer and launcher contract tests |

The `learn/scripts/` directory contains the DSE, PDN, signoff, package, and
tool-matrix runners. Reports are written to the current run scope and include
their input paths. See [`../learn/reference/live-analysis.md`](../learn/reference/live-analysis.md).
