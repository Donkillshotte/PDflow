# Post-finish ECO apply. Operates on a copied ODB — never the locked
# flowlab/learn/base 6_final.odb. Does not run signoff.
#
# Env: ECO_ODB, ECO_ODB_OUT, ECO_LIB, ECO_SDC, ECO_RC, ECO_FILL,
#      ECO_SETUP, ECO_HOLD, ECO_DEF_OUT, ECO_V_OUT, ECO_CDL_OUT,
#      ECO_CDL_MASTERS, ECO_SPEF_OUT, ECO_RCX

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

# Post-route slack. Without SPEF, repair_timing sees an ideal netlist
# and prints "No setup violations" while OpenSTA+SPEF still has WNS < 0.
if {[info exists ::env(ECO_SPEF_IN)] && $::env(ECO_SPEF_IN) != "" && [file exists $::env(ECO_SPEF_IN)]} {
  read_spef $::env(ECO_SPEF_IN)
  puts "ECO_READ_SPEF $::env(ECO_SPEF_IN)"
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

if {[info exists ::env(ECO_DEF_OUT)] && $::env(ECO_DEF_OUT) != ""} {
  write_def $::env(ECO_DEF_OUT)
  puts "ECO_REPAIR_WROTE_DEF $::env(ECO_DEF_OUT)"
}

if {[info exists ::env(ECO_V_OUT)] && $::env(ECO_V_OUT) != ""} {
  set vout $::env(ECO_V_OUT)
} else {
  set vout $::env(ECO_ODB_OUT)
  regsub {\.odb$} $vout {.v} vout
}
if {[info commands write_verilog] != ""} {
  if {[catch {find_physical_only_masters} phys]} {
    write_verilog $vout
  } else {
    write_verilog $vout -remove_cells $phys
  }
  puts "ECO_REPAIR_WROTE_V $vout"
}

if {[info exists ::env(ECO_CDL_OUT)] && $::env(ECO_CDL_OUT) != "" && [info exists ::env(ECO_CDL_MASTERS)] && [file exists $::env(ECO_CDL_MASTERS)]} {
  write_cdl -masters $::env(ECO_CDL_MASTERS) $::env(ECO_CDL_OUT)
  puts "ECO_REPAIR_WROTE_CDL $::env(ECO_CDL_OUT)"
}

if {[info exists ::env(ECO_SPEF_OUT)] && $::env(ECO_SPEF_OUT) != "" && [info exists ::env(ECO_RCX)] && [file exists $::env(ECO_RCX)]} {
  if {[catch {
    define_process_corner -ext_model_index 0 X
    extract_parasitics -ext_model_file $::env(ECO_RCX)
    write_spef $::env(ECO_SPEF_OUT)
    puts "ECO_REPAIR_WROTE_SPEF $::env(ECO_SPEF_OUT)"
  } rcx_err]} {
    puts "WARN ECO rcx: $rcx_err"
  }
}
