# Finish walkthrough

The finish stage consumes the current routed ODB and current SDC. It writes
GDS, SPEF, CDL, DEF, Verilog, and stage reports. OpenSTA must read the same
netlist, constraints, and parasitics that the report names.

```tcl
read_lef $::env(TECH_LEF)
read_lef $::env(CELL_LEF)
read_db $::env(ODB_IN)
read_liberty $::env(LIB)
read_verilog $::env(NETLIST)
link_design $::env(TOP)
read_sdc $::env(SDC)
read_spef $::env(SPEF)
report_checks -path_delay max -format full_clock_expanded
write_db $::env(ODB_OUT)
```

Inspect the current `6_report.json`, then run the signoff wrappers. A green
finish command is not proof that every optional signoff completed; use the
matrix and the explicit report status.
