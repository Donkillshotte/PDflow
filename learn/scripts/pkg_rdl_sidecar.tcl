# Educational rdl_route on a sidecar copy of the GCD finish ODB.
# Never write_db back to 6_final.odb.

if {![info exists ::env(RDL_ODB)]} { error "RDL_ODB unset" }
set odb $::env(RDL_ODB)
set lef $::env(RDL_LEF)
set out_odb $::env(RDL_OUT_ODB)
set out_def $::env(RDL_OUT_DEF)

read_db $odb
read_lef $lef

proc make_pkg_pad {name net x y} {
  set block [ord::get_db_block]
  set master [[ord::get_db] findMaster PKG_PAD]
  set inst [odb::dbInst_create $block $master $name]
  $inst setLocation $x $y
  $inst setPlacementStatus FIRM
  set pin [$inst findITerm PAD]
  $pin connect [$block findNet $net]
}

# 4×4 scaled dummy bumps fit the ~83.9 µm GCD die.  Power, return and
# functional signals use disjoint bump instances so assign_io_bump cannot
# overwrite an earlier package assignment.
make_io_bump_array -bump DUMMY_BUMP -origin {8 8} -rows 4 -columns 4 -pitch {16 16}

# PKG_PAD is a small core-cell endpoint for this educational sidecar. It
# gives rdl_route a real top-layer target while keeping the finish ODB intact.
# The endpoint is intentionally not presented as a foundry pad model.
make_pkg_pad PKG_PAD_VDD VDD 38000 80000
make_pkg_pad PKG_PAD_VSS VSS 36000 55000
make_pkg_pad PKG_PAD_CLK clk 81720 4860
make_pkg_pad PKG_PAD_RESET reset -1860 40700
make_pkg_pad PKG_PAD_REQ req_val -1860 37340
make_pkg_pad PKG_PAD_RESP resp_val -1860 47420

# Power/return: one explicit breakout endpoint per net in this compact map.
assign_io_bump -net VDD -terminal PKG_PAD_VDD/PAD BUMP_0_0
assign_io_bump -net VSS -terminal PKG_PAD_VSS/PAD BUMP_0_1

if {[catch {
  rdl_route -layer metal10 -width 0.8 -spacing 0.8 -allow45 {VDD VSS}
} err]} {
  puts "RDL_ROUTE_M10_ERROR $err"
} else {
  puts "RDL_ROUTE_CMD_OK layer=metal10"
}

assign_io_bump -net clk -terminal PKG_PAD_CLK/PAD BUMP_1_0
assign_io_bump -net reset -terminal PKG_PAD_RESET/PAD BUMP_1_1
assign_io_bump -net req_val -terminal PKG_PAD_REQ/PAD BUMP_2_0
assign_io_bump -net resp_val -terminal PKG_PAD_RESP/PAD BUMP_2_1

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
