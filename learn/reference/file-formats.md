# File formats

These files carry different parts of one live flow:

| Format | Produced by | Used for |
|---|---|---|
| Verilog | RTL/Yosys | logic and mapped cells |
| SDC | design constraints | clocks and I/O timing |
| ODB | OpenROAD | physical database |
| DEF | OpenROAD | geometry and connectivity interchange |
| SPEF | OpenRCX | routed parasitics |
| GDS | detailed route/export | layout and DRC |
| CDL | netlist export | LVS |
| SPICE | `write_pg_spice` | power-network solve |
| VCD/SAIF | simulation/activity | switching evidence |
| JSON | reports | machine-readable current status |

An artifact is meaningful only with its design, variant, run id, and source
fingerprint. A JSON report may describe `READY`, `GAP`, `FAIL`, or `REFUSED`;
the status is part of the data.

For exercises, inspect the path printed by the current command and note the
tool, input, output, and validation performed. Do not use a number from an
unrelated report to fill a worksheet.

## Format details

### Verilog and SDC

The RTL Verilog is the functional source. Yosys emits a mapped netlist whose
cell instances are consumed by the physical flow. The SDC supplies clocks,
I/O delays, uncertainty, and exceptions. Timing observations are meaningful
only when the netlist and SDC belong to the same invocation.

### ODB, DEF, and GDS

ODB is OpenROAD's database and is the input for the native GUI and the
browser-safe layout viewer. DEF is a text interchange view of placement,
routing, rows, pins, and special nets. GDS is the stream layout delivered to
viewers or downstream mask tooling. A DEF export can be inspected without
claiming that a GDS stream was generated.

### SPEF and CDL

SPEF contains extracted parasitics for post-route timing. If OpenRCX is not
available, the report must say that timing uses an estimate. CDL is a circuit
netlist for LVS; it is not interchangeable with the timing netlist or with a
power SPICE deck. A SPEF header begins with `*SPEF` and identifies the format
before its name and capacitance sections.

### SPICE, VCD, and SAIF

`write_pg_spice` describes the power network and its supply/current sinks.
The dynamic solver consumes that mesh plus current events. VCD and SAIF carry
activity evidence and are joined to physical instances only when the names
and source fingerprints match. A missing activity source is a gap, not an
all-zero waveform.

### JSON reports

Reports should expose the action, status, run id, input fingerprints, output
paths, and comparison scope. Numeric fields are measurements from the
invocation that wrote the file. A report can contain a `GAP` for an optional
engine while still carrying a valid measurement from an available backend.

## App integration

Studio uses the format registry to select a tool target. The floorplan target
opens an ODB/DEF pair; after a native save, the app checks the file metadata
and reloads the current report. The package target uses its own sidecar and
never overwrites the core finish database. This separation keeps native-tool
edits, browser inspection, and report cards tied to the same live artifacts.

## Naming and containment

Stage artifacts use the ORFS stage prefix: `1_` for synthesis, `2_` for
floorplan, `3_` for placement, `4_` for CTS, `5_` for route, and `6_` for
finish. The variant directory is part of the path and is never supplied by
an unchecked user string. Studio accepts one artifact name at a time and
resolves it below the selected results directory.

When a tool emits a sidecar, the report records the sidecar path and the
protected source artifact. Sidecars are useful for package routing, analysis,
or a scratch ECO, but they do not silently replace the core finish database.
This makes it safe to inspect a package result while the die flow remains
available in its own app panel.

## Reading order

Read the current JSON status first, then the artifact metadata, then the tool
log. Use the viewer only after the path and revision are known. This order
prevents a screenshot or a browser cache from becoming the basis of a timing,
power, or signoff claim.
