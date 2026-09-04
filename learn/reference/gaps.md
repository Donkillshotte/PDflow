# Remaining gaps

Two kinds of leftover. They look similar in Studio (a red or amber
hook) but they are not the same work.

| Kind | Meaning | Who can close it |
|---|---|---|
| **License / PDK gated** | The file or tool exists in the industry and is not in this tree. We will not invent a substitute and call it the real thing. | A license, a form, or a different PDK |
| **To build** | Missing flow, script, or check we can write here. | This repo |

Do not mix them on a roadmap. A gated item is not a sprint.

## License / PDK gated

| Item | What we have | Why it stays gated |
|---|---|---|
| Official Nangate **CCS** liberty | `typical.lib` is NLDM. Educational PTM sidecar on 19 GCD combo cells. | Si2/Silvaco 2008 CCS is form-gated. The sidecar is re-characterized, not that file. |
| **StarRC / Raphael** | OpenRCX SPEF + 2-wire FasterCap BEM | Commercial extractors. No license. |
| Board **S-parameter** (Touchstone) | Lumped VRM→board→pkg ladder | Public SI/PI decks are form-gated. Exporting the lump as `.sNp` would be false. |
| **MCMM** liberty (slow/fast) | Single `typical.lib` + one SDC | Nangate45 in ORFS ships one corner. Extra corners need the full kit or a foundry PDK. Not required for this educational close. |
| **Magic + Netgen** on FreePDK45 | KLayout DRC/LVS | No verified FreePDK45 Magic `.tech` in this environment. |
| **sky130** as the course PDK | Nangate45 only | Different PDK. Do not mix it into this course. |
| **PrimeTime / Tempus / Voltus** | OpenSTA + PDNSim + Xyce N4 | Different tools. We do not claim equivalence. |
| **EM current-density limits** | vyges-em-ir static/dynamic IR on the `write_pg_spice` mesh. `em_checked` is 0. | Nangate45 has no foundry `emlimit`. Adding a guessed limit would be a fake EM close. |
| **LVS must-connect on DFF_X2** | KLayout compare matches. lvsdb lists 2 well-tie warnings on `DFF_X2`. | Nangate split wells. Unpin, flatten-after-extract, flatten-all-before-extract, and flat extract all fail to clear the leftover without breaking the match. |
| **VIA_* flatten in LVS** | `blank_circuit("VIA_*")` after extract. | Routing vias have no CDL. Do not invent devices. |
| **Density / named ERC** | Antenna is in `FreePDK45.lydrc` (300:1). | Density and named ERC rules are not in the deck. |

## To build (or already built)

| Item | State |
|---|---|
| LVS on FlowLab GCD | Built: filter unused CDL, inject FILL from DEF, map wells to VDD/VSS, `blank_circuit` on empty FILL/TAP. KLayout compare must print a real match. `.lvs.ok` only on that line. Split-well leftover is PDK-gated (table above). |
| ECO after finish | Built: Propose on locked variants. Apply on an unlocked copy loads SPEF, wraps DPL in incremental GRT, then detailed_route (`-clean_patches`). BufferMove is unsafe (SIGSEGV / RSZ-0074). If TritonRoute cannot connect (DRT-0206), apply restores the source `6_final`. A legal size-up may still leave setup open; leftover is named. Never calls `signoff_all`. |
| Antenna in GDS DRC | Already in `FreePDK45.lydrc` (`antenna_check`, 300:1). |
| DSE as flow controller | Not to build. DSE stays a proposer. See `learn/dse/flow_role.py`. |
| IR mesh mixing | Built: `ir_mesh_ledger.py` stamps gold / current_run / chip / vyges / system into `power_signoff_*.json`. Numbers stay on their own meshes. |

## What this flow does not pretend to be

Educational Nangate45 / FreePDK45. Failed or gated checks stay labeled.
Gold Dynamic IR on the FlowLab mesh stays **45.298 mV**.
