# Open-source integrations

| Capability | Entry point | Contract |
|---|---|---|
| OpenROAD/ORFS | FlowLab and finish scripts | current ODB/DEF/GDS |
| OpenSTA | `run_sta_signoff.sh` | current netlist, SDC, SPEF |
| KLayout | DRC/LVS wrappers | current GDS and runset |
| Icarus | `run_rtl_sim.sh` | current RTL and testbench |
| ngspice | SPICE and package runners | current deck and model |
| Xyce | optional solver probe | current deck and model |
| HotSpot | thermal runner | current power trace and mesh |
| FasterCap | optional capacitance probe | current geometry |
| vyges-em-ir | EM/IR wrapper | current current/mesh inputs |

Tool discovery is runtime-based. A missing integration is a visible `GAP` and
never a reason to reuse a previous output.
