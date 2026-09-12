# Educational rdl_route on a sidecar copy of a lab_asap7_* finish ODB.
# Never write_db back to 6_final.odb. Not C4. Not a product win.

if {![info exists ::env(RDL_ODB)]} { error "RDL_ODB unset" }
set odb $::env(RDL_ODB)
set lef $::env(RDL_LEF)
set out_odb $::env(RDL_OUT_ODB)
set out_def $::env(RDL_OUT_DEF)
if {[info exists ::env(RDL_ORIGIN)]} { set origin $::env(RDL_ORIGIN) } else { set origin "0.8 0.8" }
if {[info exists ::env(RDL_PITCH)]} { set pitch $::env(RDL_PITCH) } else { set pitch "1.8 1.8" }
if {[info exists ::env(RDL_PWR_LAYER)]} { set pwr_layer $::env(RDL_PWR_LAYER) } else { set pwr_layer "M9" }
if {[info exists ::env(RDL_PWR_WIDTH)]} { set pwr_w $::env(RDL_PWR_WIDTH) } else { set pwr_w "0.08" }
if {[info exists ::env(RDL_PWR_SPACING)]} { set pwr_s $::env(RDL_PWR_SPACING) } else { set pwr_s "0.08" }
if {[info exists ::env(RDL_SIG_LAYER)]} { set sig_layer $::env(RDL_SIG_LAYER) } else { set sig_layer "M9" }
if {[info exists ::env(RDL_SIG_WIDTH)]} { set sig_w $::env(RDL_SIG_WIDTH) } else { set sig_w "0.04" }
if {[info exists ::env(RDL_SIG_SPACING)]} { set sig_s $::env(RDL_SIG_SPACING) } else { set sig_s "0.04" }

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

make_io_bump_array -bump DUMMY_BUMP -origin $origin -rows 4 -columns 4 -pitch $pitch

make_pkg_pad PKG_PAD_VDD VDD -1500 200
make_pkg_pad PKG_PAD_VSS VSS -1500 2600
make_pkg_pad PKG_PAD_CLK clk 200 7600
make_pkg_pad PKG_PAD_RESET reset 2000 7600
make_pkg_pad PKG_PAD_REQ req_val 4000 7600
make_pkg_pad PKG_PAD_RESP resp_val 6000 7600

assign_io_bump -net VDD -terminal PKG_PAD_VDD/PAD BUMP_0_0
assign_io_bump -net VSS -terminal PKG_PAD_VSS/PAD BUMP_0_1

if {[catch {
  rdl_route -layer $pwr_layer -width $pwr_w -spacing $pwr_s -allow45 {VDD VSS}
} err]} {
  puts "RDL_ROUTE_PWR_ERROR $err"
} else {
  puts "RDL_ROUTE_CMD_OK layer=$pwr_layer"
}

assign_io_bump -net clk -terminal PKG_PAD_CLK/PAD BUMP_0_3
assign_io_bump -net reset -terminal PKG_PAD_RESET/PAD BUMP_1_3
assign_io_bump -net req_val -terminal PKG_PAD_REQ/PAD BUMP_2_3
assign_io_bump -net resp_val -terminal PKG_PAD_RESP/PAD BUMP_3_3

if {[catch {
  rdl_route -layer $sig_layer -width $sig_w -spacing $sig_s -allow45 {clk reset req_val resp_val}
} err2]} {
  puts "RDL_ROUTE_SIG_ERROR $err2"
} else {
  puts "RDL_ROUTE_CMD_OK layer=$sig_layer"
}

write_db $out_odb
write_def $out_def
puts "RDL_SIDECAR_ODB $out_odb"
puts "RDL_SIDECAR_DEF $out_def"
puts "RDL_SIDECAR_WRITTEN"
