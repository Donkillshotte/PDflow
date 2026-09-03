// Functional gate-level testbench for ORFS GCD (6_final.v + Nangate .v).
// Same handshake as tb_gcd.v. Dumps gcd_gate.vcd on the DUT so VCD scopes
// are gate instances. Not SDF / not timing-accurate GLS.
`timescale 1ns/1ps

module tb_gcd_gate;
  reg clk = 0;
  reg reset = 1;
  reg [31:0] req_msg = 0;
  reg req_val = 0;
  wire req_rdy;
  wire [15:0] resp_msg;
  reg resp_rdy = 1;
  wire resp_val;

  always #5 clk = ~clk; // 100 MHz functional (not the SDC period)

  gcd dut (
    .clk(clk),
    .reset(reset),
    .req_msg(req_msg),
    .req_val(req_val),
    .req_rdy(req_rdy),
    .resp_msg(resp_msg),
    .resp_rdy(resp_rdy),
    .resp_val(resp_val)
  );

  integer errors = 0;
  integer cycles = 0;

  task automatic do_gcd;
    input [15:0] a;
    input [15:0] b;
    input [15:0] expected;
    begin
      @(posedge clk);
      while (!req_rdy) @(posedge clk);
      req_msg = {a, b};
      req_val = 1;
      @(posedge clk);
      req_val = 0;
      while (!resp_val) begin
        @(posedge clk);
        cycles = cycles + 1;
        if (cycles > 20000) begin
          $display("FAIL timeout a=%0d b=%0d", a, b);
          errors = errors + 1;
          disable do_gcd;
        end
      end
      if (resp_msg !== expected) begin
        $display("FAIL gcd(%0d,%0d)=%0d expected %0d", a, b, resp_msg, expected);
        errors = errors + 1;
      end else begin
        $display("OK   gcd(%0d,%0d)=%0d", a, b, resp_msg);
      end
      @(posedge clk);
    end
  endtask

  initial begin
    $dumpfile("learn/sim/gcd/gcd_gate.vcd");
    $dumpvars(0, tb_gcd_gate.dut);
    repeat (8) @(posedge clk);
    reset = 0;
    repeat (4) @(posedge clk);

    do_gcd(15, 25, 5);
    do_gcd(21, 14, 7);
    do_gcd(7, 3, 1);
    do_gcd(48, 18, 6);
    do_gcd(0, 9, 9);

    if (errors == 0) $display("GATE_SIM_PASS");
    else $display("GATE_SIM_FAIL errors=%0d", errors);
    $finish;
  end
endmodule
