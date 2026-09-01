# Piano: iterazione successiva — generatore prima, policy poi, schema per ultimo

Solo piano. Nessun esperimento parte da questo commit. I criteri decisionali
sono pre-registrati qui, prima di cuocere, e non si ritoccano dopo i dati.

Contesto: la campagna P0–P7 (`experiment_campaign_plan.md`, verdetti in
`eval_campaign.md` e `campaign_writeup.md`) ha stabilito che **il base ORFS
vince** su gcd/spi/dynamic_node/ibex/aes ai clock provati. H1 supportata (i
proxy invertono il ranking), H6 supportata (forno deterministico 5/5),
H2 incompleta, H3/H4/H5 non supportate. Il funnel ha rifiutato correttamente
i candidati perdenti: il valutatore funziona, è **il generatore** che non ha
mai prodotto un candidato promuovibile.

Questo piano consolida il feedback strategico ricevuto (fidelity policy,
Candidate come stato unico, EvaluationResult, Pareto come primitiva,
CurrentScenario adapter) con una correzione d'ordine: prima si allarga lo
spazio di ricerca con le leve fisiche già disponibili e si misura la policy
sul dato esistente; il refactoring dei contratti entra solo dove viene
consumato.

## 0. Vincoli non negoziabili (invariati)

- VM 15 GiB / 4 CPU, **un** job pesante alla volta, `prlimit --as=8GiB`.
- Mai Krylov/MOR su extract AES ~50–70k-R (`admit_solve` decide, non noi).
- Mai overwrite di `results/.../gcd/flowlab/` né restamp dell'oro 45.298.
- Mai riga `febe6804241c` toccata. Variant nuove per ogni cottura
  (`camp_*` resta lo schema; le righe già registrate sono locked).
- DirectLU resta il `numerical_reference` PDN. Non si sostituisce.
- Un `test_dse.py` alla volta; F4 live sempre ultimo.
- Ogni esperimento committato subito dopo (log durabile, sessioni brevi).
- I criteri §5 della campagna restano frozen e identici: win = WNS migliore,
  oppure WNS pari (±5 ps) e area stdcell ≥10% minore, oppure primo a
  chiudere. Il proxy non entra mai nel verdetto.

## 1. Principio guida (adottato dal feedback, con l'ordine corretto)

Spendere compute solo quando una evaluation può realisticamente cambiare la
decisione, e imparare dai casi in cui una fidelity economica ha previsto male
quella costosa. La domanda del controller non è «qual è lo stage successivo?»
ma «quale evaluation riduce di più l'incertezza o aumenta la probabilità di
battere la baseline, per unità di costo?».

Correzione d'ordine rispetto al feedback: una fidelity policy perfetta
applicata a candidati che perdono tutti produce solo STOP più economici.
Quindi: **Q1 knob fisici (generatore) → Q2 policy (valutatore) → Q3 schema
(contratti)**. Niente nuovi proposer AI (LLM/RL/GNN/e-graphs) in questa
iterazione.

## 2. Ipotesi falsificabili (pre-registrate)

| ID | Ipotesi | Come si falsifica |
|---|---|---|
| I1 | Le manopole fisiche (`PLACE_DENSITY_LB_ADDON`, `CORE_UTILIZATION`) hanno più leva degli script ABC: esiste una config che batte il base §5 su ≥1 design, oppure la sensibilità misurata supera ±25 ps su gcd | Se lo sweep Q1 non produce nessun win §5 **e** il range WNS osservato sui knob è < 25 ps su gcd e < 50 ps su ibex, I1 è falsa: la ricetta base è robusta anche sul fisico |
| I2 | Il residuo place→finish è stabile **per-design**: calibrato su ≥3 finish dello stesso design, predice il finish WNS delle cotture successive entro ±2σ su ≥80% dei punti nuovi | Se <80% dei punti nuovi cade in ±2σ per-design, I2 è falsa e il place-DP non è un surrogato affidabile nemmeno localmente |
| I3 | La policy sa dire STOP: ≥80% dei candidati che la policy rifiuta di portare a finish perdono davvero (verificato pagando control finish) | Se <80% dei rifiutati verificati perde, la policy butta candidati buoni e va ricalibrata prima di qualunque estensione |
| I4 | Nel regime «area a clock chiuso» esiste un win §5: a un clock dove il base chiude, un candidato chiude con area stdcell ≥10% minore | Se nessun candidato Q1/Q2 chiude con ≥10% area in meno dove il base chiude, I4 è falsa su questo set. `camp_gcd_clk090_b` (−24.1%) **non** è retroattivamente un win: contava contro la barra H3 al 25%, e i criteri non si riscrivono a posteriori |
| I5 | La correlazione proxy→finish è misurabile e utile: il ranking place-DP correla col ranking finish (Spearman ≥ 0.6 sui punti etichettati), mentre il ranking F1 no | Se anche il place-DP ha correlazione < 0.6, il gate attuale è rumore e la policy Q2 non può appoggiarsi a nessun segnale economico |

## 3. Metriche e criteri decisionali (frozen)

Fonte unica per il verdetto QoR: `6_report.json` della variant. Come in
campagna.

- **Win di prodotto**: §5 invariato (sopra).
- **Policy (I3)**: precision degli STOP ≥80% sui rifiutati verificati;
  budget di verifica ≤2 control finish per design, etichettati
  `control_negative`. I control finish non contano come win/loss di
  prodotto: pagano solo la misura.
- **Residuo (I2)**: per-design, media±σ su finish etichettati; predizione
  = place WNS + residuo medio del design; barra ±2σ su ≥80% dei nuovi punti.
- **Diagnostiche da riportare sempre** (mai nel verdetto): correlazione
  proxy→F5, FP/FN rate del gate, time-to-best, numero di evaluation costose,
  compute speso per decisione.
- **Obiettivo della fase**: massimizzare `miglior QoR F5 feasible / compute
  speso` vs base ORFS. Pareggio resta una risposta.

## 4. Fasi e budget

Sequenziali, un job alla volta, freeze+commit dopo ogni esperimento.
Registro: `learn/sim/dse/campaign_experiments.jsonl`, fasi `Q0..Q4`.

| Fase | Contenuto | # finish | Wall stimato |
|---|---|---:|---:|
| **Q0 misura a costo zero** | Query sul JSONL esistente (45 righe): correlazione F1→finish e place→finish, FP/FN del gate, residuo per-design con σ. Script `learn/scripts/eval_policy.py` + test sintetici. Verdetto I5 preliminare | 0 | ~1 h |
| **Q1 knob fisici** | gcd: griglia 3×3 `PLACE_DENSITY_LB_ADDON` {−0.05, 0, +0.05} × `CORE_UTILIZATION` {25, 35, 45}, centro già noto → 8 finish. ibex: 4 punti (`LB_ADDON` ±0.05 a util config; util ±10 a LB 0). Netlist = base yosys del design (H6 garantisce riproducibilità) | 12 | ~1.5 h |
| **Q2 fidelity policy v1** | Next Level: scelta azione con costo, gain atteso, residuo per-design da Q0/Q1 e STOP espliciti. Campo `delta` (vs parent/baseline) nel Candidate — solo campo, niente DesignState. Verifica I3 con ≤2 control finish/design sui rifiutati | ≤4 | ~1 h |
| **Q3 schema incrementale** | Solo dove consumato: `pred` (valore+incertezza) quando un modello la produce; contratto `EvaluationResult`/`SolveResult` (status, fidelity, provenance, runtime, RSS, backend_requested/actual, fallback_reason, residual) al prossimo ritocco PDN; tag provenienza `REAL/PARTIAL/SYNTHETIC/ABSENT` su CurrentScenario; stati Pareto espliciti (dominated/non-dominated/feasible/infeasible/uncertain) nel report | 0 | ~2 h |
| **Q4 win regime area (condizionale)** | Solo se Q1/Q2 producono un candidato vicino alla frontiera: ≤2 finish mirati al win I4. Altrimenti skip onesto registrato | ≤2 | ~30 min |

Totale: ≤18 finish, ~6 h wall. gcd ~1 min/finish, ibex ~7.5 min/finish.

## 5. Infrastruttura minima (prima di Q1)

1. `scripts/run_design_finish.sh`: passthrough `PLACE_DENSITY_LB_ADDON`
   (oggi passa già `CORE_UTILIZATION`, `DIE_AREA/CORE_AREA`, `ABC_SPEED`,
   `SYNTH_NETLIST_FILES`). Refusal locked invariati.
2. `learn/scripts/eval_policy.py`: correlazioni, FP/FN, residui per-design,
   verdetti I1–I5 con le barre della sezione 3. Output `eval_policy.md/json`.
3. Registro riusato (`experiments.py`), fasi `Q*`, nessun secondo registro.
4. Test sintetici in `test_dse_next.py` per 1–2 prima di ogni cottura.

## 6. Regole di stop

- Un esperimento >2× il runtime stimato → kill per PID, `timeout`, non si
  ripete nella stessa sessione.
- Config knob che fallisce il flow (es. DPL-0038, PDN-0185) → registrata
  `failed` con l'errore, non riprovata con gli stessi valori.
- Disco <50 GB → pulizia `results/` delle variant Q* già freezate (mai base,
  mai flowlab).
- RAM >8 GiB in place/route → punto escluso, registrato con la ragione.
- Se Q0 falsifica I5 (nemmeno il place-DP correla), Q2 si ferma alla misura:
  niente policy costruita su segnale rumoroso.

## 7. Cosa NON faremo in questa iterazione

- Nessun proposer nuovo: niente LLM, RL, GNN, e-graphs/equality saturation,
  architecture-level search. Esistono come prototipi: restano fermi finché
  la policy non sa scegliere fidelity, solver e budget.
- Nessun multi-fidelity surrogate bayesiano: con ~36+18 finish etichettati
  sarebbe sottodeterminato. Prima il residuo per-design (I2), che è un
  modello a due parametri.
- Nessun `DesignState` parallelo: Candidate evolve (delta → pred), non si
  duplica.
- Nessuna compressione prematura in uno score unico: la frontiera Pareto
  riporta gli assi separati (area, WNS, power, congestion, IR, EM, costo).
- Nessun retune dei criteri §5 o delle barre della sezione 3 dopo i dati.
- Jpeg / tinyRocket / swerv: solo se Q0–Q2 chiudono sotto budget **e**
  esiste un candidato che giustifica il costo.

## 8. Criterio di successo della fase (frozen)

Il deliverable è **uno dei due**, dichiarato senza reframing:

1. Almeno un win §5 reale al finish contro il base ORFS (da Q1 o Q4), oppure
2. La dimostrazione quantitativa che il controller riconosce i candidati
   senza speranza: I3 ≥80% di precision sugli STOP verificati, più I2/I5
   misurate e riportate.

Se entrambi falliscono, il verdetto è «né win né policy affidabile» e si
scrive così. Pareggio è una risposta; anche «la ricetta base è robusta pure
sui knob fisici» (I1 falsa) è un risultato pubblicabile, non un fallimento
da nascondere.
