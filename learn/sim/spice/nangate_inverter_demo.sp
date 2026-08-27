* CMOS inverter demo — transistor-level (didactic, NOT Nangate45 foundry)
* Shows how liberty power maps to device currents at logic level.
* Run: ngspice -b nangate_inverter_demo.sp
*
* Compare with: OpenROAD report_power (aggregated) vs this single-gate SPICE.

.param Vdd=1.1
.param Wn=0.36u Ln=0.09u Wp=0.81u Lp=0.09u

VDD vdd 0 DC {Vdd}
VIN in 0 PULSE(0 {Vdd} 1n 0.1n 0.1n 4n 8n)

* Level-1 style (educational — replace with BSIM for tapeout)
M1 out in vdd vdd PMOS W={Wp} L={Lp}
M2 out in 0 0 NMOS W={Wn} L={Ln}

Cload out 0 10f

.model NMOS NMOS (VTO=0.4 KP=200u)
.model PMOS PMOS (VTO=-0.4 KP=100u)

.control
tran 0.01n 20n
plot v(in) v(out) i(VDD)
print avg(i(VDD))
quit
.endc
.end
