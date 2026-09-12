# Current capability gaps

This page describes capabilities that may be unavailable on a local install.
It is not a results ledger.

Examples include missing CCS/MCMM libraries, foundry extraction decks,
Calibre/StarRC/Raphael, optional ngspice/Xyce/FasterCap binaries, and PDK
models needed for package or thermal fidelity. The runner should state the
exact missing path or executable and emit `GAP`.

ASAP7 and Nangate45 have different PDK, geometry, and library contracts. They
can be run as separate live tracks but must not be compared in one result.

To close a gap, install the missing dependency, rerun the relevant stage, and
inspect the new report. Do not fill the gap by copying a prior JSON.
