# PTM 45 nm HP (BSIM4)

`ptm45hp.pm` is the public Arizona State University Predictive Technology
Model, 45 nm high-performance bulk card (nominal Vdd = 1.0 V).

- Origin: [PTM](https://mec.umn.edu/ptm) (formerly ptm.asu.edu)
- Mirror used here: Verilog-to-Routing `vtr_flow/tech/PTM_45nm/45nm.pm`
- Cite: W. Zhao and Y. Cao, “New generation of predictive technology model
  for sub-45 nm early design exploration,” IEEE Trans. Electron Devices,
  vol. 53, no. 11, pp. 2816–2823, Nov. 2006.

Nangate CDL instances use `NMOS_VTL` / `PMOS_VTL`. The characterizer writes
a runtime alias wrapper; this file is the unmodified PTM card.

This is **not** the original Nangate characterization deck. CCS tables built
from it are educational re-characterization, not foundry CCS.
