* System PDN AC — impedance Z(f) at die (Iac=1A → |Z|=|V(n_die)|)

V_VRM n_vrm_src 0 DC 1.1
R_VRM n_vrm_src n_vrm 0.015
L_VRM n_vrm n_vrm_l 2e-09
C_VRM n_vrm_l 0 4.7e-05
R_ESR_VRM n_vrm_l n_board_in 0.008

R_PLANE n_board_in n_board 0.005
L_PLANE n_board n_board_l 1e-09
C_BULK n_board_l 0 2.2e-05
R_ESR_BULK n_board_l n_board_mid 0.012
C_HF n_board_mid 0 1e-06
R_ESR_HF n_board_mid n_board_out 0.02
L_VIA n_board_out n_pkg_in 5e-10

R_PKG n_pkg_in n_pkg 0.04
L_PKG n_pkg n_pkg_l 3e-10
C_PKG n_pkg_l 0 2e-10
R_BUMP n_pkg_l n_die_pre 0.00035714285714285714
L_BUMP n_die_pre n_die 3.5714285714285716e-12

C_DIE n_die 0 5e-10

I_AC n_die 0 DC 0 AC 1

.control
set filetype=ascii
ac dec 20 1000.0 1000000000.0
let zmag = abs(v(n_die))
wrdata /workspace/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/system_pdn/ac zmag
quit
.endc
.end
