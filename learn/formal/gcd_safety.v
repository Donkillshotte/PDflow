// Formal safety wrapper for GCD (Yosys SAT / SymbiYosys-class).
// Property: while reset is held, resp_val stays 0 (synchronous reset).
module gcd_safety (
  input clk,
  input reset,
  input req_val,
  input resp_rdy
);
  wire req_rdy;
  wire resp_val;
  wire [15:0] resp_msg;

  gcd dut (
    .clk(clk),
    .reset(reset),
    .req_msg(32'b0),
    .req_val(req_val),
    .req_rdy(req_rdy),
    .resp_msg(resp_msg),
    .resp_rdy(resp_rdy),
    .resp_val(resp_val)
  );

`ifdef FORMAL
  always @(posedge clk) begin
    if (reset) assume (req_val == 1'b0);
    if (reset) assert (resp_val == 1'b0);
  end
`endif
endmodule
