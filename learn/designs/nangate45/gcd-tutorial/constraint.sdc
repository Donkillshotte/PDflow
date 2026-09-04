# Course SDC (conservative start).
# Lesson 01 explains each line and offers variants.

current_design gcd

set clk_name core_clock
set clk_port_name clk

# 0.46 ns ≈ 2.17 GHz — moderate so the lesson is learnable without area overflow
set clk_period 0.46
set clk_io_pct 0.2

set clk_port [get_ports $clk_port_name]
create_clock -name $clk_name -period $clk_period $clk_port

set non_clock_inputs [all_inputs -no_clocks]
set_input_delay  [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs
set_output_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_outputs]
