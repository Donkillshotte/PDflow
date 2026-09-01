# Next iteration write-up (Q0–Q4)

Plan: `learn/dse/next_iteration_plan.md` (sha in `eval_policy.json`).
Win criteria §5 and I1–I5 bars are **frozen**. Source of truth: `6_report.json`.

## Product verdict

Physical knobs beat the ORFS default on this set. The first frozen §5
wins of the whole campaign come from `PLACE_DENSITY_LB_ADDON` /
`CORE_UTILIZATION`, not from DSE netlists or `abc_speed`.

| Design | Clock | Winner | Why |
|---|---:|---|---|
| gcd | 0.46 ns | `camp_gcd_q1_d25u35` | slack ±1.2 ps vs base, area **−10.5%** (842 vs 940 µm²) |
| ibex | 2.20 ns | `camp_ibex_q1_d20u60` | WNS **+42 ps** vs base +22 ps (area ~unchanged) |

Also §5 wins on ibex: `d15u50` (+36 ps) and `d25u50` (+40 ps).

## I1–I5

| ID | Esito |
|---|---|
| I1 | **supportata** (4 win §5; gcd range 8.4 ps, ibex 26.2 ps) |
| I2 | **supportata** (13/13 Q* holdout dentro ±2σ per-design) |
| I3 | **supportata** (STOP precision 100% su 11 reject già pagati) |
| I4 | **non supportata** (Q4 a 0.55 ns chiude ma area ≈ base) |
| I5 | **supportata** (place Spearman 0.968 ≥ 0.6) |

## Q0

Zero-cost sul registry P0–P7. Place→finish Spearman 0.978 già prima di Q1.
Il gate place-DP è un segnale economico; F1 resta invertito su gcd (H1).

## Q1 knob grid

Offsets dai default di config (LB 0.20, gcd util 35, ibex util 50).

GCD 8 punti (centro già noto). Range WNS 8.4 ps. Unico win: LB=0.25 / util=35.

Ibex 4 punti. Tre battono il WNS del base; util 40 è l'unico peggioramento
(−6 ps). Range 26.2 ps.

## Q2 policy

`learn/dse/fidelity_policy.py`: STOP se `place + residuo_per_design` è
peggio del base di >2σ e fuori dalla banda ±5 ps. Collegata allo
scheduler Next Level. I3 è un replay sui DSE B/C già pagati in P0/P1:
11/11 STOP corretti. I Q1 knob (place ~+10–15 ps) restano EVALUATE,
correttamente: uno di loro è un win.

`Candidate.delta` esisteva già (`qor_delta` vs parent). Nessun DesignState.

## Q3 schema

Niente secondo stato. Consumato ciò che c'era:

- `SolveResult` + `CurrentScenario` (`REAL/PARTIAL/SYNTHETIC/ABSENT`)
- `Candidate.pred` / `Candidate.delta`
- `pareto_status()` → dominated/non-dominated × feasible/infeasible/uncertain

## Q4 area-regime

`camp_gcd_q4_d25u35_c055` al clock dove A chiude (0.55 ns): WNS +13.02 vs
base +13.36 (tie), area 698 vs 697. **I4 falsa** su questo punto: il
vantaggio area di Q1 a 0.46 ns non sopravvive quando entrambi chiudono
allo stesso util.

## Successo della fase

Entrambi i rami del criterio frozen:

1. Win §5 reali (gcd area, ibex WNS).
2. Policy STOP ≥80% (100% su 11) + I2/I5 misurate.

Oro 45.298 unrestampato. `febe6804241c` intatta. Nessun overwrite
`flowlab`. Nessun Krylov AES. Nessun proposer AI.

## QoR multi-asse (finish `6_report`, non solo slack)

§5 resta WNS / area-tie / first-to-close. Power e leakage sono assi extra
letti da `finish__power__*` — prima il registro non li copiava.

| Variant | §5 | ΔWNS | Δarea | Δpower | Δleak |
|---|---|---:|---:|---:|---:|
| gcd `d25u35` | win | −1.2 ps | **−10.5%** | **−12.7%** | **−14.1%** |
| ibex `d20u60` | win | +20 ps | −0.2% | −0.3% | ~0% |
| ibex `d25u50` | win | +17 ps | −0.1% | ~0% | ~0% |
| ibex `d15u50` | win | +14 ps | ~0% | ~0% | ~0% |

Su gcd il win area è anche un win power/leakage (stesso netlist, die
invariato, meno buffering). Su ibex il win è quasi solo slack: potenza
totale ~108 mW, invariata.

IR (worst VDD drop) e GRT wirelength sono assi extra letti da
`6_report` / `5_1_grt.json`. Non c'è overflow fraction in questi JSON
ORFS (`congestion_*_s` sono runtime). Tabella con **valori assoluti del
reference flow** + challenger + Δ: `learn/dse/qor_compare.md`.

| Variant | §5 | IR ref → cand | ΔIR | GRT WL ref → cand | ΔWL |
|---|---|---|---:|---|---:|
| gcd `d25u35` | win | 6.67 → 6.15 mV | **−7.7%** | 7589 → 6971 | **−8.1%** |
| ibex `d20u60` | win | 123.8 → 86.2 mV | **−30.3%** | 438851 → 420930 | **−4.1%** |

Su ibex il win slack è anche un calo IR/WL; power resta ~iso. §5 non
usa IR/WL. 12 reference slot, 29 challenger, tutti con IR e GRT WL.
