# Educational rdl_route on a sidecar copy of the GCD finish ODB.
# Never write_db back to 6_final.odb.

if {![info exists ::env(RDL_ODB)]} { error "RDL_ODB unset" }
set odb $::env(RDL_ODB)
set lef $::env(RDL_LEF)
set out_odb $::env(RDL_OUT_ODB)
set out_def $::env(RDL_OUT_DEF)

read_db $odb
read_lef $lef

# 2×2 scaled dummy bumps fit the ~88.8 µm GCD die.
make_io_bump_array -bump DUMMY_BUMP -origin {16 16} -rows 2 -columns 2 -pitch {28 28}

# Power: bump-to-bump on metal10. Signals: pin (M6) to bump (M6 port).
assign_io_bump -net VDD BUMP_0_0
assign_io_bump -net VDD BUMP_1_1
assign_io_bump -net VSS BUMP_0_1
assign_io_bump -net VSS BUMP_1_0

if {[catch {
  rdl_route -layer metal10 -width 0.8 -spacing 0.8 -allow45 {VDD VSS}
} err]} {
  puts "RDL_ROUTE_M10_ERROR $err"
} else {
  puts "RDL_ROUTE_CMD_OK layer=metal10"
}

assign_io_bump -net clk BUMP_0_0
assign_io_bump -net reset BUMP_0_1
assign_io_bump -net req_val BUMP_1_0
assign_io_bump -net resp_val BUMP_1_1

if {[catch {
  rdl_route -layer metal6 -width 0.14 -spacing 0.14 {clk reset req_val resp_val}
} err2]} {
  puts "RDL_ROUTE_M6_ERROR $err2"
} else {
  puts "RDL_ROUTE_CMD_OK layer=metal6"
}

write_db $out_odb
write_def $out_def
puts "RDL_SIDECAR_ODB $out_odb"
puts "RDL_SIDECAR_DEF $out_def"
puts "RDL_SIDECAR_WRITTEN"
