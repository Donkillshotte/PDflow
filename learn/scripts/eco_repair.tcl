# Post-finish ECO apply. Operates on a copied ODB — never the locked
# flowlab/learn/base 6_final.odb. Does not run signoff.
#
# Env: ECO_ODB (input), ECO_ODB_OUT (output), ECO_SETUP (0|1), ECO_HOLD (0|1)

if {![info exists ::env(ECO_ODB)] || ![info exists ::env(ECO_ODB_OUT)]} {
  puts "FAIL eco_repair.tcl needs ECO_ODB and ECO_ODB_OUT"
  exit 1
}

read_db $::env(ECO_ODB)

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

write_db $::env(ECO_ODB_OUT)
puts "ECO_REPAIR_WROTE $::env(ECO_ODB_OUT)"
