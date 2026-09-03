# Post-finish ECO apply. Operates on a copied ODB — never the locked
# flowlab/learn/base 6_final.odb. Does not run signoff.
#
# Env: ECO_ODB, ECO_ODB_OUT, ECO_LIB, ECO_SDC, ECO_RC, ECO_FILL,
#      ECO_SETUP, ECO_HOLD

if {![info exists ::env(ECO_ODB)] || ![info exists ::env(ECO_ODB_OUT)]} {
  puts "FAIL eco_repair.tcl needs ECO_ODB and ECO_ODB_OUT"
  exit 1
}

read_db $::env(ECO_ODB)

if {[info exists ::env(ECO_LIB)] && $::env(ECO_LIB) != ""} {
  read_liberty $::env(ECO_LIB)
}
if {[info exists ::env(ECO_SDC)] && $::env(ECO_SDC) != "" && [file exists $::env(ECO_SDC)]} {
  read_sdc $::env(ECO_SDC)
}
if {[info exists ::env(ECO_RC)] && $::env(ECO_RC) != "" && [file exists $::env(ECO_RC)]} {
  source $::env(ECO_RC)
}

if {[info commands remove_fillers] != ""} {
  remove_fillers
}

if {[info exists ::env(ECO_SETUP)] && $::env(ECO_SETUP) == "1"} {
  if {[info commands repair_timing] != ""} {
    repair_timing -setup
  }
}
if {[info exists ::env(ECO_HOLD)] && $::env(ECO_HOLD) == "1"} {
  if {[info commands repair_timing] != ""} {
    repair_timing -hold
  }
}

if {[info commands detailed_placement] != ""} {
  detailed_placement
}

if {[info commands filler_placement] != ""} {
  set fills "FILLCELL_X1 FILLCELL_X2 FILLCELL_X4 FILLCELL_X8 FILLCELL_X16 FILLCELL_X32"
  if {[info exists ::env(ECO_FILL)] && $::env(ECO_FILL) != ""} {
    set fills $::env(ECO_FILL)
  }
  filler_placement $fills
}

write_db $::env(ECO_ODB_OUT)
puts "ECO_REPAIR_WROTE $::env(ECO_ODB_OUT)"

if {[info commands write_verilog] != ""} {
  set vout $::env(ECO_ODB_OUT)
  regsub {\.odb$} $vout {.v} vout
  write_verilog $vout
  puts "ECO_REPAIR_WROTE_V $vout"
}
