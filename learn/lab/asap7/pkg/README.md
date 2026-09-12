# Lab ASAP7 compact package (leftover-named)

Dummy bump LEF + lumped VRM→board→pkg→die ladder for the optional ASAP7 lab
track. It is not C4, Touchstone, or Ansys CPA, and is not a product result.
It writes only sidecar artifacts for the selected live invocation.

Entry point: `python3 learn/scripts/lab_asap7_pkg.py`
(also run from `run_asap7_e2e.py` after cooks).

The run publishes a versioned live manifest at
`learn/sim/reports/pkg_manifest_<variant>.json`. It validates the finish
checkpoint, the 4×4 configured bump array, the six mapped package nets, the
sidecar RDL coverage and the compact System PDN result. `PROXY` means the
evidence is complete for this educational invocation; it never means Product
signoff.
