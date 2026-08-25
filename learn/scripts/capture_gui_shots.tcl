set odb $::env(ODB_FILE)
set shot_dir $::env(SHOT_DIR)
set stem $::env(SHOT_STEM)
file mkdir $shot_dir
read_db $odb

set block [ord::get_db_block]
set die [$block getDieArea]
set dx_um [ord::dbu_to_microns [$die dx]]
set dy_um [ord::dbu_to_microns [$die dy]]
puts "DIE_UM dx=$dx_um dy=$dy_um"

if { $dy_um < 5.0 } { set dy_um 40.0 }
set resolution [expr $dy_um / 1200.0]
if { $resolution <= 0 } { set resolution 0.02 }

set path [file join $shot_dir ${stem}.png]
if { [catch { save_image -resolution $resolution $path } err] } {
  puts "SAVE_FAIL $err"
} else {
  puts "WROTE $path"
}
