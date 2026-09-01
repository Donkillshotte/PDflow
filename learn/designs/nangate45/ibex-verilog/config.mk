# Ibex campaign overlay: Verilog chameleon/ibex (no slang).
# Lives under learn/designs/; the wrapper symlinks it into ORFS as ibex-verilog.
export DESIGN_NAME = ibex_core
export PLATFORM    = nangate45
export DESIGN_NICKNAME = ibex

IBEX_V = $(DESIGN_HOME)/src/chameleon/ibex
export VERILOG_FILES = \
    $(IBEX_V)/ibex_pkg.v \
    $(IBEX_V)/ibex_alu.v \
    $(IBEX_V)/ibex_branch_predict.v \
    $(IBEX_V)/ibex_compressed_decoder.v \
    $(IBEX_V)/ibex_controller.v \
    $(IBEX_V)/ibex_core.v \
    $(IBEX_V)/ibex_counter.v \
    $(IBEX_V)/ibex_cs_registers.v \
    $(IBEX_V)/ibex_csr.v \
    $(IBEX_V)/ibex_decoder.v \
    $(IBEX_V)/ibex_dummy_instr.v \
    $(IBEX_V)/ibex_ex_block.v \
    $(IBEX_V)/ibex_fetch_fifo.v \
    $(IBEX_V)/ibex_icache.v \
    $(IBEX_V)/ibex_id_stage.v \
    $(IBEX_V)/ibex_if_stage.v \
    $(IBEX_V)/ibex_load_store_unit.v \
    $(IBEX_V)/ibex_multdiv_fast.v \
    $(IBEX_V)/ibex_multdiv_slow.v \
    $(IBEX_V)/ibex_pmp.v \
    $(IBEX_V)/ibex_prefetch_buffer.v \
    $(IBEX_V)/ibex_register_file_ff.v \
    $(IBEX_V)/ibex_wb_stage.v \
    $(IBEX_V)/prim_clock_gating.v

export SDC_FILE      = $(DESIGN_HOME)/nangate45/ibex-verilog/constraint.sdc
export ABC_AREA      = 1
export ADDER_MAP_FILE :=

export CORE_UTILIZATION ?= 50
export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100
export SYNTH_REPEATABLE_BUILD ?= 1
