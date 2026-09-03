# FasterCap (FastFieldSolvers)

LGPL 2.1 3D/2D capacitance field solver. Educational 2-wire extract on
FreePDK45-like M2 geometry — **not** Raphael/StarRC, **not** full-chip SPEF.

```bash
./learn/scripts/install_fastercap.sh
FLOW_VARIANT=flowlab python3 learn/scripts/run_analytical_pex.py
```

`lab_tools.sh` prepends this prefix. Binary is committed when the Cloud
image has a working build; otherwise run the install script.
