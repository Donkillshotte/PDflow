# Xyce (Sandia) local prefix

Not vendored (binary + MPI/OpenBLAS deps). Install:

```bash
./learn/scripts/install_xyce.sh
```

Puts `Xyce` in `learn/tools/xyce/bin`. `lab_tools.sh` prepends that path and
`LD_LIBRARY_PATH`. Studio action `spice_engines` runs the existing N4 deck
(`pdn_vrm.xyce_vrm_die_gold`). ngspice stays the System PDN engine.

Do not restamp gold Dynamic IR 45.298 from Xyce numbers.
