* Demo System PDN TRAN — VRM / board / package / die
* Studio GCD · learn/sim/spice/system_pdn_tran_demo.sp
*
* Run: ngspice -b -o tran_demo.log system_pdn_tran_demo.sp
* Docs: learn/reference/spice-ngspice-primer.md

V_VRM n_vrm_src 0 DC 1.1
R_VRM n_vrm_src n_vrm 0.015
L_VRM n_vrm n_vrm_l 2e-09
C_VRM n_vrm_l 0 47e-06
R_ESR_VRM n_vrm_l n_board_in 0.008

R_PLANE n_board_in n_board 0.005
L_PLANE n_board n_board_l 1e-09
C_BULK n_board_l 0 22e-06
R_ESR_BULK n_board_l n_board_mid 0.012
C_HF n_board_mid 0 1e-06
R_ESR_HF n_board_mid n_board_out 0.02
L_VIA n_board_out n_pkg_in 0.5e-09

R_PKG n_pkg_in n_pkg 0.04
L_PKG n_pkg n_pkg_l 0.3e-09
C_PKG n_pkg_l 0 200e-12
R_BUMP n_pkg_l n_die_pre 0.000357
L_BUMP n_die_pre n_die 3.57e-12

C_DIE n_die 0 500e-12
* I_avg=2mA idle=30% peak=4x
I_DIE n_die 0 PULSE(0.0006 0.008 20n 2n 2n 80n 1.0)

.control
set filetype=ascii
tran 0.1n 200n
print v(n_die)
wrdata tran_demo_out v(n_vrm_l) v(n_board_out) v(n_pkg_l) v(n_die)
quit
.endc
.end
