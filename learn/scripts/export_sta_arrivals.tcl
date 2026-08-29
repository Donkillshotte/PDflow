# Dump OpenSTA output-pin arrivals and the worst max path.
# Stdout is parsed by export_sta_arrivals.py.
# Env: STA_LIB STA_V STA_SDC
# Pin names join ODB insts after unescaping '\'. Does not invent times.
set lib $env(STA_LIB)
set v $env(STA_V)
set sdc $env(STA_SDC)

read_liberty $lib
read_verilog $v
link_design gcd
read_sdc $sdc
if {[info exists env(STA_SPEF)] && $env(STA_SPEF) ne "" && [file exists $env(STA_SPEF)]} {
  read_spef $env(STA_SPEF)
  puts "STA_SPEF_READ $env(STA_SPEF)"
} else {
  puts "STA_SPEF_SKIP ideal interconnect (set STA_SPEF for OpenRCX parasitics)"
}

set n 0
foreach pin [get_pins -hierarchical *] {
  if {[catch {get_property $pin direction} dir]} {
    continue
  }
  if {$dir ne "output"} {
    continue
  }
  if {![catch {get_property $pin is_hierarchical} hier]} {
    if {$hier} {
      continue
    }
  }
  set nm [get_full_name $pin]
  set ahz 0
  set duty 0
  set origin ""
  if {![catch {set act [get_property $pin activity]}]} {
    if {[llength $act] >= 1} { set ahz [lindex $act 0] }
    if {[llength $act] >= 2} { set duty [lindex $act 1] }
    if {[llength $act] >= 3} { set origin [lindex $act 2] }
  }
  puts "PIN $nm activity=$ahz duty=$duty origin=$origin"
  report_arrival -digits 8 $pin
  incr n
}
puts "STA_PATH_BEGIN"
report_checks -path_delay max -fields {input_pin} -digits 6 -format full -group_path_count 1
puts "STA_PATH_END"
puts "STA_ARRIVALS_DONE n=$n"
