# PLAN — consolidamento DSE (schema → controller dichiarativo)

Stato: passo 0 ✅, passo 1 ✅, passo 2 ✅, passo 3a ✅, passo 3b ✅, passo 4 ✅. I passi si eseguono **in ordine**; ogni passo si chiude
solo con i test verdi indicati e con commit dedicato. Nessun passo introduce un
tipo `DesignState` parallelo: si irrigidisce ciò che esiste.

Riferimenti: `learn/dse/README.md` (invarianti), `.cursor/SETUP_LOG.md` (log durabile),
feedback architetturale discusso in PR #2.

---

## Vincoli permanenti (valgono per ogni passo)

- VM cloud ~15 GiB / 4 CPU / swap 0. Un solo job pesante; `prlimit --as=8GiB`.
- **Mai** Krylov/MOR su mesh AES ~50–70k R. `admit_solve` deve rifiutare, non lo script.
- **Mai** sovrascrivere `memory_aes.jsonl` riga `febe6804241c` (73k-R / 6.954 mV).
- **Mai** ristampare il gold GCD 45.298 mV (`dynamic_ir_flowlab.json`).
- Il finish FlowLab corrente droopa **6.075 mV** su `n_r=5816`: è `current_run`,
  non il `reference_run` 45.298. I test non devono confonderli.
- AES SDC 0.82 ns, `top=aes_cipher_top`; F5 AES rifiuta path `/gcd/`.
- Test solo su dati sintetici o GCD-scale. `pkill -f` vietato (kill per PID).
- DirectLU = reference numerico. B/C/D = accelerator con errore vs A.

Test di regressione da tenere verdi a ogni passo:

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_candidate_schema.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_heavy_analysis.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_designs.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse.py        # ~5 min con F4
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_frame.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dispatch.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_actions.py
```

---

## Passo 0 — Contratto base ✅ (fatto, commit `3bd9479`)

- `Candidate.delta` = QoR figlio − parent sugli assi osservati da entrambi
  (`qor_delta` in `metrics.py`; riempito da `DesignMemory.add`).
- Ruoli espliciti su `Candidate`: `knobs`=azione, `artifacts`=osservazione,
  `attr`=interpretazione, `pred`=predizione.
- `SolveResult` (`learn/dse/solve_result.py`): role reference/accelerator,
  `abs_err_vs_reference_mv`, `activity_status` REAL/PARTIAL/SYNTHETIC/ABSENT,
  `backend_requested`/`backend_actual`/`fallback_reason`, `mesh_fp`.
- `admit_solve` (`learn/dse/resources.py`): gate unico RSS/mesh/CUDA sopra
  `heavy_analysis.pick_bounded_solver`.
- `solve_f4` stampa `payload["solve"]` (SolveResult serializzato) su ogni esito.
- Test: `test_candidate_schema.py` → `SCHEMA_CONTRACT_OK`.

---

## Passo 1 — Riconciliare i due «delta» (piccolo) ✅

**Problema.** `Candidate.delta` è vs **parent**; `controller._attach_delta`
scrive `attr["delta"]` vs **liberty_default** (baseline). Stesso nome,
semantica diversa.

**Modifiche.**
- `learn/dse/controller.py::_attach_delta`: la chiave diventa
  `attr["delta_vs_baseline"]`; il payload usa `qor_delta(cand.qor, base.qor)`
  più `{"vs": base.id, "note": ...}`. Mantenere la retro-lettura: chi legge
  accetta sia `delta` (righe storiche) sia `delta_vs_baseline`.
- Grep di tutti i lettori di `attr.get("delta")` (Studio incluso:
  `studio/` API suite) e aggiornarli alla doppia chiave.

**Accettazione.**
- `test_dse.py` verde senza modifiche ai valori attesi (solo chiave).
- Una riga nuova in `test_candidate_schema.py`: baseline-delta usa `qor_delta`
  e non tocca `Candidate.delta`.

---

## Passo 2 — Il controller consuma il contratto (piccolo, alto valore) ✅

**Problema.** Zero occorrenze di `admit_solve` / `SolveResult` / `.delta` in
`controller.py`. Il gate esiste ma le decisioni non lo leggono.

**Modifiche.**
1. Ogni pagamento F4 nel controller (candidate/host/region/champ/solver-residual)
   passa da `admit_solve(n_r, n_nodes=..., solver=...)` **prima** di lanciare;
   `reason` del gate finisce nel `why` dello `step(...)` di log.
   `n_r` viene dall'extract già registrato (`artifacts["n_r"]`); quando manca,
   il gate ammette DirectLU e il log lo dice (`re-admit with n_r`).
2. I confronti fra solver (blocchi `f4_amg_champ` / `f4_ras_champ` /
   `f4_krylov_champ` e i ~10 punti di `fidelity.py` che ricalcolano
   `residual_mv` a mano) leggono `artifacts["solve"]["abs_err_vs_reference_mv"]`
   quando presente; il ricalcolo manuale resta solo come fallback per righe
   storiche senza `solve`.
3. `attribute`/`inspect` propagano `activity_status` dal SolveResult all'`attr`
   del candidato F4 (chiave `attr["activity_status"]`).

**Accettazione.**
- `test_dse.py`: i blocchi F4 verdi; nuovo assert che un F4 pagato dal
  controller ha `artifacts["solve"]["role"]` coerente col solver.
- `test_candidate_schema.py`: AES Krylov ancora REFUSED via gate.
- Nessun nuovo solve AES nel test (solo GCD / cached).

---

## Passo 3 — Stage table nel controller (redesign, a strangolamento)

**Problema.** `run_controller` = ~4600 righe, ~50 blocchi fotocopiati
(`should_pay_X` → `if plan and pay and t_end` → `evaluate_X`).
`acquire.py` = 66 `should_pay_*` quasi identiche.

**Pattern di arrivo** (già provato in `dispatch.run_next_refine`):

```python
STAGES: list[Stage] = [
    Stage(level="f2_fast", should_pay=..., evaluate=..., max_shots=4, cost_key="F2_FAST"),
    ...
]
for stage in STAGES:
    run_stage(stage, mem, plan, budget, step)
```

**Regola di migrazione (strangler).** Mai riscrivere tutto: si migra un lotto,
si tengono identici i messaggi `why`/`step` (i test li asseriscono), si
committa, si passa al lotto dopo.

- **3a** ✅ — Infrastruttura: `learn/dse/stages.py` con `Stage` (dataclass) e
  `run_stage` generico; helper `should_pay_generic(budget_left, n_have, max_shots,
  min_s, parents_ok)` che copre il caso comune delle 66 funzioni.
  Migrare **4 stage semplici**: `f2_fast`, `f2_gpl`, `f3_sta`, `f3_sdf`.
- **3b** ✅ — Migrare il ramo routing/F5: `routing (GRT)`, `f5_drt`, `f3_spef`,
  `f5_cts`, `f5_local`, `f5_port`. GRT resta fra STA e SDF; residual_steer resta
  inlined fra local e port.
- **3c** — Migrare cell/net/synthesis/physical-catalog.
- **3d** — Migrare la coda PDN/F4 (candidate/host/region/champ/catalog/static/EM).
  Qui ogni stage F4 dichiara `needs_admit=True` e `run_stage` chiama
  `admit_solve` (chiude il cerchio col passo 2).
- **3e** — Pulizia: le `should_pay_*` rimpiazzate da `should_pay_generic`
  vengono eliminate da `acquire.py`; restano solo i predicati genuinamente
  speciali. `run_controller` diventa: setup → plan → loop stage table →
  refine chain (`dispatch`) → summary.

**Accettazione per ogni lotto.**
- `test_dse.py` verde **senza cambiare i valori attesi** (i `why` possono
  cambiare solo se il test viene aggiornato nello stesso commit, con diff
  esplicito nel messaggio).
- Il numero di righe di `run_controller` scende in modo misurabile a ogni
  lotto (annotarlo nel commit).
- Ogni lotto = un commit; niente lotti sovrapposti.

---

## Passo 4 — Cost model dai dati (dopo 3a, indipendente da 3b–3e) ✅ (commit `aed3a6d`)

**Problema.** `COST_HINT` in `fidelity.py` è statico
(`{"F0": 0.05, "F1": 2.0, "F2": 30.0, ...}`) mentre ogni candidato registra
`cost_s` reale.

**Modifiche.**
- `learn/dse/costs.py`: `estimated_cost_s(mem, fidelity, design_id)` = p75 dei
  `cost_s` delle righe ok di quella fedeltà su quel design; fallback a
  `COST_HINT` quando i campioni sono < 3.
- `run_stage` (passo 3a) e i check `time.time() + COST > t_end` usano la stima.
- `COST_HINT` resta come fallback dichiarato, non viene eliminato.

**Accettazione.**
- Unit test sintetico: memoria con `cost_s` noti → p75 corretto; < 3 campioni
  → fallback.
- `test_dse.py` verde (budget 45 s invariato).

---

## Passo 5 — Selezione con incertezza (dopo 3e)

**Problema.** Il fronte Pareto per livello esiste (`pareto_front`), ma un WNS
F1 e un WNS F5-SPEF competono alla pari.

**Modifiche.**
- `metrics.py`: `FIDELITY_RANK = {"F0": 0, "F1": 1, ..., "F5": 5}` e
  `dominates_with_fidelity(a, b)`: su un asse *timing/power* un punto a
  fedeltà più bassa non può dominare un punto a fedeltà più alta; può solo
  co-esistere (stato `uncertain`).
- `pareto_front` invariato; nuova `pareto_front_gated` usata dal planner per
  la scelta del prossimo candidato. Il fronte “storico” nei report non cambia.
- `pred` (surrogato) partecipa solo come tie-break, mai come dominanza.

**Accettazione.**
- Unit test: F1 WNS migliore non domina F5 WNS peggiore; F5 domina F1 a parità
  di assi; assi non-timing (area F1) restano confrontabili come oggi.
- `test_dse.py` verde.

---

## Passo 6 — CurrentScenario (dopo il passo 3; prerequisito CCS)

**Problema.** Il TRAN parla di «triangolo»; la sorgente I(t) deve diventare
un'astrazione (il solver non sa da dove viene la corrente).

**Modifiche.**
- `learn/dse/current_scenario.py`: dataclass con
  `source ∈ {ideal_triangle, sta_t50, vcd, saif, liberty_ccs}`,
  `activity_status`, `scale`, `period_ns`, fingerprint.
- `build_worker_cmd` / `dse_f4_worker.py` accettano lo scenario serializzato;
  il triangolo resta il default e il comportamento attuale non cambia.
- `SolveResult.activity_via` punta allo scenario.

**Accettazione.**
- Stesso droop GCD 6.075 mV con scenario `sta_t50` esplicito (equivalenza col
  default attuale).
- Waveform mancante ⇒ scenario ABSENT, mai inventato.

**Fuori scope del passo:** implementare CCS su Nangate45 (NLDM: resta GAP).

---

## Esplicitamente NON in piano

- Tipo `DesignState` parallelo a `Candidate`.
- LLM/GNN/e-graph/RL come centro del controller (restano adapter).
- Closed-loop synthesis↔PD libero: prima parameter-DSE, poi structural.
- Restamp del gold 45.298; F5-CTS AES; Krylov AES su questa VM.
- Spacchettare `test_dse.py` in un colpo solo (si spacchetta stage per stage
  durante il passo 3).

## Ordine dei commit

```
1  delta_vs_baseline (passo 1)
2  controller consuma admit_solve/SolveResult (passo 2)
3  stages.py + lotto 3a (f2_fast, f2_gpl, f3_sta, f3_sdf)
4  lotto 3b (routing/F5)
5  costs.py p75 (passo 4)
6  lotto 3c (cell/net/synthesis/catalog)
7  lotto 3d (PDN/F4 con needs_admit)
8  lotto 3e (pulizia acquire.py)
9  pareto_front_gated (passo 5)
10 current_scenario.py (passo 6)
```

Ogni commit: test verdi elencati sopra, riga in `.cursor/SETUP_LOG.md`,
push e aggiornamento PR #2.
