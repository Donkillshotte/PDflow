# DSE fisico-aware

Non è un loop cieco synth→P&R. Il controller cerca **un livello per volta**, tiene
una memoria di esperimenti e usa Dynamic IR come **oracolo F4**, non come penalità
scalare.

```text
RTL
 → e-graph datapath (cono IR, es. dpath)
 → F1 Yosys+ABC (alfabeto BOiLS, GP+SSK, append DRiLLS) + equiv
   write_verilog -noattr -noexpr  (celle liberty, non assign soup)
 → F2-fast netgraph (baricentro ancorato + HPWL + RUDY)
 → F2 OpenROAD GPL -skip_io (un colpo a budget, non finish)
 → F2 ingest place / GRT del layout corrente
 → F3 STA ingest
 → F4 Dynamic IR / EM ingest (gold 45.298 mV unrestampato)
 → attributo hotspot → regione → celle → modulo RTL (dpath/ctrl)
 → surrogato F0 (SSK-GP, residual F1→F2, GNN HPWL; F1→F4 solo se accoppiato)
 → Pareto per livello
 → prossimo candidato / extract
```

## Livelli (non un vettore unico)

| Livello | Cosa si cerca | Stato |
|---|---|---|
| **architecture** | extract e-graph equivalenti sul cono `dpath` (ROVER/ASPEN-shaped) | READY F1 + equiv |
| **logic** | sequenze ABC `{rewrite, refactor, resub, balance, …}` (BOiLS STD) | READY F1 · GP+EI · insert |
| **synthesis** | `ABC_AREA` ORFS | catalogo F0 (non mescolato alle ops ABC) |
| **physical** | util, densità, netlist del candidato | F0 proxy + F2-fast + **GPL** + ingest F2/F4 — non lancia finish |
| **pdn** | `c_decap`, pkg L | **ingest** F4 |

Concatenare `rewrite` e `coreUtilization` in un unico box è **vietato** (`knobs_fp` include il livello).

## Fedeltà

| F | Ruolo | Stato |
|---|---|---|
| F0 | SSK-GP area ± std; congestion RUDY-class; skip F1 se l’ottimista è già peggiore | READY — **non** è IR |
| F1 | Yosys synth + ABC (script *file*) + `equiv_*` + `write_verilog -noexpr` | READY |
| F2 | place / GRT / finish ORFS **ingest** · F2-fast netgraph · GPL `-skip_io` | READY (GPL budgetato) |
| F3 | OpenSTA | ingest `sta_signoff_*.json` |
| F4 | Dynamic IR/EM (libdpn A/B/C/D) | ingest — **non** sostituisce il gold |
| F5 | P&R signoff | GAP: il controller non lancia finish |

F2-fast HPWL è in **unità griglia**; GPL HPWL è in **µm**. Non stanno sullo stesso asse Pareto.
La congestion F2-fast è `rudy_excess/(1+rudy_excess)` ∈ [0,1) — non è l’overflow GRT.

## E-graph / extract

Sul datapath GCD saturiamo uguaglianze:

- `a-b` ≡ `a+(~b+1)`
- `(x==0)` ≡ `~(|x)`
- unsigned `a<b` ≡ borrow di `{0,a}-{0,b}`

L’extract greedy (costo strutturale) preferisce l’operatore nativo; gli extract
forzati vengono misurati a F1 (feedback EDA, idea ASPEN). Softmax su −cost/T è
ispirato a SmoothE, senza loop GPU. Se l’hotspot IR è su `dpath`, si riscrive
**solo quel cono** — niente restart del chip.

## Attributi (chip → block → region → cone)

Il path OpenSTA del GCD (`dpath.a_reg…`) e l’hotspot ITerm (`x_dbu`, `y_dbu`)
diventano `scope=logic_cone`, `modules=[dpath]`, `region=r31`. Si registra
`transform + context → ΔQoR`, non solo `design → QoR`.

## Ottimizzatori (uno per problema)

Il **planner** legge `combo_frac`, il modulo e la regione: IR combo su `dpath`
ordina gli extract (`lt_borrow` → `sub` → `eqz`) e non riparte dal chip.
Congestione GRT alta o focus di regione sposta il budget sul livello physical.

- **BOiLS** — kernel SSK + GP + EI + trust-region (swap/delete/**insert**)
- **DRiLLS** — UCB sul prossimo op ABC dato (ultimo op, focus IR)
- **e-graph** — saturation + extract, non RTL casuale
- **GNN** — 2 layer mean-aggregate + ridge su HPWL F2-fast; incertezza alta se n&lt;4
- **AutoDMP-shaped** — catalogo util/densità a F0
- **OpenROAD GPL** — un colpo `-skip_io` sul vincitore F1 (non route, non F5)
- **LLM** — proposer opzionale (`DSE_LLM_URL`); fallback simbolico; **non** è l’ottimizzatore

## Layer sostituibili

`learn/dse/layers.py` registra extraction / power / activity / current / DSE /
surrogate / solver / physical_fast / physical_gpl. Il solver PI resta **ingest**:
il gold GCD 45.298 mV non si ristampa.

## Comandi

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_dse.sh
# DSE_F1_MAX=6 DSE_BUDGET_S=90 DSE_FRESH=1
python3 learn/scripts/test_dse.py
```

Report: `learn/sim/reports/dse_flowlab.json` · memoria: `learn/sim/dse/memory_flowlab.jsonl`.

Studio: azione `dse` · `/strumenti?tab=run&action=dse` · pannello su `/pkg` e FlowLab signoff.

Riferimenti (non fork): BOiLS DATE’22 / HEBO ActionSimple, DRiLLS, AutoDMP ISPD’23,
ROVER/ASPEN/SmoothE come forma (ROVER/ASPEN non sono OSS), MAVIREC, EMSim split A/B,
Raptor/MATEX/ESPSim nel solver PI già presente.
