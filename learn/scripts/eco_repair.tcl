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

# ECO_PHASE=sizeup|buffer|io|all (default all). Size-up and I/O need SPEF.
# BufferMove cannot: SPEF in the same OpenROAD session is RSZ-0074 even
# after estimate_parasitics (live apply). Buffer runs in a fresh process
# with no SPEF. Close is still signoff_all.
set eco_phase "all"
if {[info exists ::env(ECO_PHASE)] && $::env(ECO_PHASE) != ""} {
  set eco_phase $::env(ECO_PHASE)
}
puts "ECO_PHASE $eco_phase"

set eco_read_spef 0
if {$eco_phase != "buffer"} {
  if {[info exists ::env(ECO_SPEF_IN)] && $::env(ECO_SPEF_IN) != "" && [file exists $::env(ECO_SPEF_IN)]} {
    read_spef $::env(ECO_SPEF_IN)
    set eco_read_spef 1
    puts "ECO_READ_SPEF $::env(ECO_SPEF_IN)"
  }
} else {
  puts "ECO_SKIP_SPEF BufferMove (SPEF in-session is RSZ-0074)"
}

if {[info commands set_propagated_clock] != "" && [info commands all_clocks] != ""} {
  if {[catch {set_propagated_clock [all_clocks]}]} {
    puts "WARN ECO set_propagated_clock skipped"
  }
}

# Pin-swap / resize notify GRT. Without this, OpenROAD SIGSEGVs in
# getPinGridPositions / addDirtyNet. A full global_route after size-up
# can fail pin coverage (GRT-0304) and TritonRoute DRT-0206; wrap DPL in
# start/end incremental so only dirty nets re-route. BufferMove is a
# second OpenROAD with no SPEF (ECO_PHASE=buffer).
set eco_grt 0
if {[info exists ::env(ECO_FASTROUTE)] && $::env(ECO_FASTROUTE) != "" && [file exists $::env(ECO_FASTROUTE)]} {
  source $::env(ECO_FASTROUTE)
}
if {[info commands pin_access] != ""} {
  if {[catch {pin_access} err]} {
    puts "WARN ECO pin_access: $err"
  } else {
    puts "ECO_PIN_ACCESS"
  }
}
if {[info commands global_route] != ""} {
  if {[catch {global_route -allow_congestion} err]} {
    puts "WARN ECO global_route: $err"
  } else {
    set eco_grt 1
    puts "ECO_GRT initialized"
  }
}

if {[info commands remove_fillers] != ""} {
  remove_fillers
}

# BufferMove matches the working probe: GRT parasitics before incremental,
# no SPEF in the timing graph. Size-up keeps SPEF and skips BufferMove.
if {$eco_phase == "buffer" && $eco_grt && [info commands estimate_parasitics] != ""} {
  if {[catch {estimate_parasitics -global_routing} err]} {
    puts "WARN ECO GRT parasitics: $err"
  } else {
    puts "ECO_PARASITICS GRT"
  }
}

if {$eco_grt && [info commands global_route] != ""} {
  if {[catch {global_route -start_incremental} err]} {
    puts "WARN ECO global_route -start_incremental: $err"
  } else {
    puts "ECO_GRT start_incremental"
  }
}

# The course SDC puts 20% of 0.46 ns on every I/O. OpenROAD then ranks
# resp_msg[*] as WNS and spends the budget there. OpenSTA register-to-
# register (dpath.a_reg) is repaired first (sizeup + BufferMove) with
# outputs false for that session. After R2R is MET, ECO_PHASE=io false-
# paths register-to-register so size-up hits the leftover output path.
# The SDC file is not rewritten.
if {[info exists ::env(ECO_SETUP)] && $::env(ECO_SETUP) == "1"} {
  if {!$eco_grt} {
    puts "WARN ECO setup repair skipped — GRT not initialized"
  } elseif {[info commands repair_timing] != ""} {
    if {$eco_phase == "io"} {
      if {[info commands set_false_path] != "" && [info commands all_registers] != ""} {
        if {[catch {set_false_path -from [all_registers] -to [all_registers]} err]} {
          puts "WARN ECO set_false_path registers: $err"
        } else {
          puts "ECO_SETUP_FOCUS outputs (R2R false during I/O repair)"
        }
      }
      if {[catch {repair_timing -setup -skip_buffering -skip_gate_cloning -sequence "sizeup,swap" -verbose} err]} {
        puts "WARN ECO io repair: $err"
      } else {
        puts "ECO_REPAIR_IO sizeup,swap"
      }
    } else {
      if {[info commands set_false_path] != "" && [info commands all_outputs] != ""} {
        if {[catch {set_false_path -to [all_outputs]} err]} {
          puts "WARN ECO set_false_path outputs: $err"
        } else {
          puts "ECO_SETUP_FOCUS register-to-register (I/O false during repair)"
        }
      }
      if {$eco_phase != "buffer"} {
        if {[catch {repair_timing -setup -skip_buffering -skip_gate_cloning -sequence "sizeup,swap" -verbose} err]} {
          puts "WARN ECO setup repair: $err"
        } else {
          puts "ECO_REPAIR_SETUP sizeup,swap"
        }
      }
      if {$eco_phase == "buffer"} {
        if {$eco_read_spef} {
          puts "WARN ECO buffer skipped — SPEF loaded (RSZ-0074); run ECO_PHASE=buffer in a fresh OpenROAD"
        } else {
          if {[catch {repair_timing -setup -skip_gate_cloning -sequence "buffer" -max_buffer_percent 20 -verbose} err]} {
            puts "WARN ECO buffer repair: $err"
          } else {
            puts "ECO_REPAIR_BUFFER"
          }
        }
      }
    }
  }
}
if {[info exists ::env(ECO_HOLD)] && $::env(ECO_HOLD) == "1"} {
  if {[info commands repair_timing] != ""} {
    if {[catch {repair_timing -hold -skip_buffering -skip_gate_cloning -verbose} err]} {
      puts "WARN ECO hold repair: $err"
    }
  }
}

# BufferMove / size-up cells are born without PG. write_cdl then emits
# _unconnected_ on VDD/VSS and KLayout compare fails. Finish calls
# global_connect for the same reason.
if {[info commands global_connect] != ""} {
  if {[catch {global_connect} err]} {
    puts "WARN ECO global_connect: $err"
  } else {
    puts "ECO_GLOBAL_CONNECT"
  }
}

if {[info commands detailed_placement] != ""} {
  detailed_placement
}

if {$eco_grt && [info commands global_route] != ""} {
  if {[catch {global_route -end_incremental -allow_congestion} err]} {
    puts "WARN ECO global_route -end_incremental: $err"
  } else {
    puts "ECO_GRT end_incremental"
  }
}

if {[info commands report_wns] != ""} {
  report_wns
  report_tns
}

if {[info commands detailed_route] != ""} {
  set drc_out $::env(ECO_ODB_OUT)
  regsub {\.odb$} $drc_out {.drc} drc_out
  if {[info exists ::env(ECO_DRC_OUT)] && $::env(ECO_DRC_OUT) != ""} {
    set drc_out $::env(ECO_DRC_OUT)
  }
  if {[catch {detailed_route -verbose 1 -clean_patches -output_drc $drc_out} err]} {
    puts "WARN ECO detailed_route: $err"
  } else {
    puts "ECO_DRT $drc_out"
  }
}

if {[info commands design_is_routed] != "" && ![design_is_routed]} {
  puts "WARN ECO design is not routed after size-up — restoring source ODB"
  # read_db cannot reload a populated db (ORD-0047). Copy the input file
  # and stop before write_def of the mutated netlist.
  file copy -force $::env(ECO_ODB) $::env(ECO_ODB_OUT)
  puts "ECO_RESTORE_SOURCE"
  puts "ECO_REPAIR_WROTE $::env(ECO_ODB_OUT)"
  exit 0
}

puts "ECO_ROUTED 1"

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
    read_spef $::env(ECO_SPEF_OUT)
  } rcx_err]} {
    puts "WARN ECO rcx: $rcx_err"
  }
}

if {[info commands report_wns] != ""} {
  puts "ECO_POST_ROUTE_STA"
  report_wns
  report_tns
}
