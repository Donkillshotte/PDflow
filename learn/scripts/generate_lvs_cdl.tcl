# Generate the design CDL for a completed OpenROAD run.
#
# Inputs are supplied through environment variables because the OpenROAD
# command-line accepts one Tcl file rather than positional script arguments:
#   PD_FLOW_LVS_ODB
#   PD_FLOW_LVS_SDC
#   PD_FLOW_LVS_LIBERTY
#   PD_FLOW_LVS_MASTERS (the CDL master library passed to write_cdl)
#   PD_FLOW_LVS_OUTPUT
#
# This script deliberately writes only a derived CDL artifact.  It never
# writes back to the ODB, which keeps the finish database immutable.

foreach name {PD_FLOW_LVS_ODB PD_FLOW_LVS_SDC PD_FLOW_LVS_LIBERTY PD_FLOW_LVS_MASTERS PD_FLOW_LVS_OUTPUT} {
  if {![info exists ::env($name)] || $::env($name) eq ""} {
    puts stderr "missing environment variable: $name"
    exit 2
  }
}

set odb [file normalize $::env(PD_FLOW_LVS_ODB)]
set sdc [file normalize $::env(PD_FLOW_LVS_SDC)]
set liberty [file normalize $::env(PD_FLOW_LVS_LIBERTY)]
set masters [file normalize $::env(PD_FLOW_LVS_MASTERS)]
set output [file normalize $::env(PD_FLOW_LVS_OUTPUT)]

foreach path [list $odb $sdc $liberty $masters] {
  if {![file isfile $path]} {
    puts stderr "missing input: $path"
    exit 3
  }
}

file mkdir [file dirname $output]
read_liberty $liberty
read_db $odb
read_sdc $sdc
set temporary "${output}.tmp"
file delete -force $temporary
write_cdl -masters $masters $temporary
file rename -force $temporary $output
puts "LVS_CDL_GENERATED $output"
