# Dump OpenSTA output-pin arrivals. Stdout is parsed by export_sta_arrivals.py.
# Env: STA_LIB STA_V STA_SDC
# Pin names join ODB insts after unescaping '\'. Does not invent times.
set lib $env(STA_LIB)
set v $env(STA_V)
set sdc $env(STA_SDC)

read_liberty $lib
read_verilog $v
link_design gcd
read_sdc $sdc

set n 0
foreach pin [get_pins *] {
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
puts "STA_ARRIVALS_DONE n=$n"
