# Configurazione didattica per il corso di physical design.
# Usa FLOW_VARIANT=learn per non sovrascrivere i run "base" del progetto.

export DESIGN_NAME = gcd
export PLATFORM    = nangate45
export DESIGN_NICKNAME = gcd

export VERILOG_FILES = $(DESIGN_HOME)/src/gcd/gcd.v
export SDC_FILE      = $(DESIGN_HOME)/nangate45/gcd-tutorial/constraint.sdc
export ABC_AREA      = 1
export ADDER_MAP_FILE :=

# Variante separata: results/.../gcd/learn/
export FLOW_VARIANT = learn

# Headroom per il repair timing durante gli esercizi
export CORE_UTILIZATION ?= 35
export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100
export SYNTH_REPEATABLE_BUILD ?= 1

export PDN_TCL ?= $(DESIGN_HOME)/nangate45/gcd/grid_strategy-M1-M4-M7.tcl
