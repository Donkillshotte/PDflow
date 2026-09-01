# Configurazione campagna: SPI su nangate45 (non tocca i design ORFS).
export DESIGN_NAME = spi
export PLATFORM    = nangate45
export DESIGN_NICKNAME = spi

export VERILOG_FILES = $(DESIGN_HOME)/src/spi/spi.v
export SDC_FILE      = $(DESIGN_HOME)/nangate45/spi/constraint.sdc
export ABC_AREA      = 1
export ADDER_MAP_FILE :=

export CORE_UTILIZATION ?= 40
export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100
export SYNTH_REPEATABLE_BUILD ?= 1
