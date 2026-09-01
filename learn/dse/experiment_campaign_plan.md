# Piano: campagna esaustiva multi-design vs flow base

Solo piano. Nessun esperimento parte da questo commit.

Obiettivo: capire se la DSE ha **valore di prodotto** o resta un laboratorio.
Il verdetto GCD@0.46ns ("A resta") vale per un design da 500 celle a un solo
clock. Questa campagna lo mette alla prova su più design, più clock, con
criteri decisionali **pre-registrati** (scritti qui, prima di cuocere).

## 0. Vincoli non negoziabili (invariati)

- VM 15 GiB / 4 CPU, **un** job pesante alla volta, `prlimit --as=8GiB`.
- Mai Krylov/MOR su extract AES ~50–70k-R (`admit_solve` decide, non noi).
- Mai overwrite di `results/.../gcd/flowlab/` né restamp dell'oro 45.298.
- Mai riga `febe6804241c` toccata. Variant nuove per ogni cottura.
- Un `test_dse.py` alla volta; F4 live sempre ultimo.
- Ogni esperimento committato subito dopo (log durabile, sessioni brevi).

## 1. Ipotesi falsificabili (pre-registrate)

| ID | Ipotesi | Come si falsifica |
|---|---|---|
| H1 | I proxy (STA ideale, area mapped) **invertono l'ordine** vero anche su design più grandi, non solo su GCD | Se su ≥2 design il ranking proxy coincide col ranking finish, H1 è falsa e il funnel è sovradimensionato |
| H2 | Il gate place-DP predice il ranking finish (P2 ≈ oracolo economico) | Misurare su TUTTE le cotture: se precision/recall del gate < 80% su ≥15 punti, il gate va ricalibrato o buttato |
| H3 | B-type (netlist piccolo) **vince ad area** quando il clock si rilassa: esiste un clock al quale B chiude e A no, o B chiude con ≥25% area in meno | Se nel clock sweep B non chiude mai prima di A o non mantiene il vantaggio area, H3 è falsa e "più piccolo" non è mai un win |
| H4 | Il valore della DSE **cresce con la taglia** del design (più leva per ABC per-cono / knobs fisici) | Se il delta best-DSE vs base non migliora (in % WNS o area) passando da ~500 a ~10k–50k celle, H4 è falsa: la DSE non scala |
| H5 | Il residual place→finish (−50 ps ± σ) è trasferibile tra design | Se il residual osservato esce dall'intervallo ±2σ su >30% dei punti, il modello va ricalibrato per-design |
| H6 | Il forno è deterministico anche sui design grandi (A-injected bit-identical) | Se un A-injected differisce, TUTTI i delta di quel design sono sospetti finché non si trova la fonte di nondeterminismo |

## 2. Matrice design

Taglie da **misurare in P0** (qui stime). Tutti nangate45, config ORFS già nel repo.

| Design | Celle (stima) | Ruolo | Runtime finish stimato (4 CPU) | Note |
|---|---:|---|---:|---|
| `gcd` (tutorial) | ~500 | ancora + clock sweep | ~1 min | già caratterizzato |
| `spi` / `riscv32i` | ~1–3k | gradino piccolo | ~2–5 min | manca config nangate45: crearla in P0 (solo `learn/designs/`, mai in ORFS) |
| `dynamic_node` | ~10k | medio, netlist pickle | ~10–20 min | `SWAP_ARITH_OPERATORS=1` di default: disattivare per il base onesto? decidere in P0 |
| `ibex` | ~15–20k | medio, SystemVerilog (slang) | ~20–40 min | CPU vera, cone ctrl/dpath sensati |
| `aes` | ~15–20k | medio, FLOORPLAN_DEF fisso | ~15–30 min | geometria già bloccata dal config → ottimo per H6; **niente F4 Krylov** |
| `jpeg` | ~40–70k | grande | ~30–60 min | util 80: rischio congestione, tenere come stretch |
| `tinyRocket` / `swerv` | ~30k / ~100k | fuori budget v1 | ore | solo se P2 finisce sotto budget |

Design set v1: **gcd, riscv32i (o spi), dynamic_node, ibex, aes**. Jpeg stretch.

## 3. Assi sperimentali

Una sola cosa cambia per esperimento (stile bake-off). Assi:

1. **Clock sweep** (solo gcd + 1 design medio): SDC ∈ {0.40, 0.46, 0.55, 0.70, 0.90} ns su gcd; {T_base·0.9, T_base, T_base·1.25, T_base·1.6} sul design medio. Risponde a H3.
2. **Netlist variant** (tutti i design): `abc_area` (base A), `abc_speed`, e — dove la DSE ha già un winner equiv-PASS full-chip — il netlist DSE. Risponde a H1/H4.
3. **Geometria**: product (util del config) vs fissa (die del base A di quel design). Solo sui punti dove il netlist variant è competitivo a place. Già falsificata su GCD-B; ripetere solo se serve. |
4. **Robustezza knob** (solo gcd, economico): `PLACE_DENSITY_LB_ADDON` ±0.05 e `CORE_UTILIZATION` ±10 sul base, per misurare la sensibilità del −37 ps di A. Se A oscilla di ±50 ps coi knob, i delta B/C vanno riletti.

**Non-assi (esclusi):** seed sweep (ORFS qui è deterministico, H6 lo verifica), PDK diversi, macro placement, retiming Yosys.

## 4. Controlli per ogni design (obbligatori prima dei confronti)

1. **Base**: un `make finish` con la ricetta ORFS del config → freeze JSON (WNS/TNS/area/repair/die + sha `6_report`). Variant `<design>_base`.
2. **A-injected**: ricuocere l'`1_2_yosys.v` del base in variant `<design>_ainj`. Deve essere bit-identical (H6). Se no: stop su quel design.
3. **Equiv**: ogni netlist non-base deve passare Yosys equiv vs RTL (o dichiarare `unsupported` ed essere escluso dal funnel — mai "fidati").
4. **Funnel dry-run**: prima di pagare un finish DSE, il gate P2 deve dire promote. I finish "gate dice no" si pagano SOLO nel sottoinsieme di validazione H2 (max 1 per design), etichettati `control_negative`.

## 5. Metriche e criteri decisionali (pre-registrati)

Fonte unica per il verdetto: `6_report.json` della stessa variant. Proxy mai nel verdetto.

- **Win di prodotto** (per design, per clock): WNS migliore, oppure WNS pari (±5 ps) e area stdcell ≥10% minore, oppure primo a chiudere (WNS≥0) al clock dato.
- **Win di search** (non di prodotto): il funnel DSE trova in ≤N finish pagati un punto che il base non ha — dichiararlo separatamente, mai sommarlo al win di prodotto.
- **H2 (gate P2)**: per ogni finish pagato, registrare (place_wns, finish_wns). Precision = frazione dei promossi che finiscono meglio del peggior promosso base; recall = frazione dei win reali che il gate avrebbe promosso. Bersaglio ≥80/80 su ≥15 punti.
- **H5 (residual)**: distribuzione finish−place per design; report media±σ per design e globale.
- **Pareggio è una risposta.** Nessun reframing a posteriori: se A-equivalenti vincono ovunque, il verdetto è "la DSE su questi design non è un prodotto" e si scrive così.

## 6. Fasi e budget

Sequenziali, un job alla volta. Ogni fase committa i suoi freeze/JSON prima della successiva.

| Fase | Contenuto | # finish | Wall stimato |
|---|---|---:|---:|
| **P0 pilot** | 1 finish base per design (5 design) + A-injected (5) + misura celle/runtime reali + config riscv32i/spi | 10 | ~2–4 h |
| **P1 clock sweep GCD** | 5 clock × 3 netlist (A-yosys, B, C) − già fatti i 0.46 | 12 | ~30 min |
| **P2 multi-design base vs abc_speed** | 4 design × {base già in P0, abc_speed} | 4 | ~2–3 h |
| **P3 DSE proxy campaign per design** | `run_dse.py --campaign` a livello F1–F3 su ibex/dynamic_node/aes (budget 10–15 min l'uno, NO finish nel loop) | 0 | ~1 h |
| **P4 funnel-selected finishes** | Next Level `--launch-finish`: max 2 finish per design scelti dal gate P2 + 1 `control_negative` per H2 | ≤9 | ~2–4 h |
| **P5 clock sweep design medio** | 4 clock × 2 netlist sul migliore emerso in P4 (o abc_speed se nessuno) | 8 | ~2–4 h |
| **P6 PDN same-extract** | DirectLU su extract dei winner SE `admit_solve` ammette (mai Krylov AES); altrimenti solo statico | 0 | ~1 h |
| **P7 analisi** | estendere `eval_vs_base_flow` a matrice multi-design; H1–H6 verdette; write-up | 0 | ~1 h |

Totale: **~40–45 finish**, ~10–18 h di wall sequenziale. Si spezza su più sessioni: ogni esperimento scrive freeze+commit, la sessione può morire senza perdere nulla (SETUP_LOG + JSON per riprendere).

## 7. Infrastruttura da costruire (piccola, prima di P0)

1. `scripts/run_design_finish.sh` — generalizza `run_dse_handoff_finish.sh`: `DESIGN`, `FLOW_VARIANT`, `SDC_NS` (genera SDC in tmp, mai in ORFS), `SYNTH_NETLIST_FILES` opzionale, `DIE_AREA/CORE_AREA` opzionali. Rifiuta variant base/`flowlab`/`learn` in scrittura.
2. `learn/dse/experiments.py` — registro JSONL degli esperimenti: id, design, clock, netlist, variant, sha, esito, runtime. Append-only.
3. `learn/scripts/eval_campaign.py` — estende `eval_vs_base_flow` alla matrice: per-design, per-clock, H1–H6 con i criteri della sezione 5.
4. Test sintetici per 1–3 in `test_dse_next.py` (parse, refusal, registro) — prima di ogni cottura.

## 8. Regole di stop

- Un esperimento >2× il runtime stimato → kill (per PID), segnare `timeout`, non ripetere nella stessa sessione.
- A-injected non identico su un design → si congela quel design (solo report, niente confronti).
- Disco <50 GB liberi → pulire `results/` delle variant DSE già freezate (mai le base).
- RAM: se un design supera il cap 8 GiB in place/route → escluso, scritto nel registro con la ragione.
- jpeg/tinyRocket/swerv: partono solo se P0–P4 chiudono sotto budget.

## 9. Cosa NON faremo

- Nessun finish dentro il loop del controller legacy.
- Nessun Krylov/MOR su AES; F4 dinamico solo dove `admit_solve` ammette.
- Nessun retiming/architettura non verificata nel funnel (binary GCD resta fuori finché non esiste equiv transazionale).
- Nessuna media tra design: i verdetti sono per-design; l'aggregato è solo il conteggio H1–H6.
- Nessun tuning dei criteri della sezione 5 dopo aver visto i dati.
