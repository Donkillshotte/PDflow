# DSE fisico-aware

Non è un loop cieco synth→P&R. Il controller cerca **un livello per volta**, tiene
una memoria di esperimenti e usa Dynamic IR come **oracolo F4**, non come penalità
scalare.

```text
RTL
 → e-graph datapath (cono IR, es. dpath)
 → F1 Yosys+ABC (alfabeto BOiLS, GP+SSK, append DRiLLS) + equiv
 → F1 synthesis: ORFS `abc_speed.script` (ABC_AREA=0, `-D 460`) — non `-fast`, non `abc_ops`
   chip = flatten-first (teacher area 409.108 µm²)
   cono dpath = ABC solo sui moduli del datapath; leftover = moduli noti − cono pagato
   cono ctrl = ABC su FSM+RegRst (primo classe, non leftover del dpath); `mapped_hier.v`
   write_verilog -noattr -noexpr  (celle liberty, non assign soup)
 → F2-fast netgraph (baricentro ancorato + HPWL + RUDY)
 → F2 OpenROAD GPL -skip_io (un colpo a budget, non finish)
 → F3 OpenSTA sul *candidato* (ideale; path gerarchici `dpath/sub/…` sul cono), **interleaved** dopo ogni F1
 → F2 routing: place_pins + GPL + global_route + `write_sdf` (non SPEF)
 → F3 OpenSTA + SDF GRT (stesso `mapped.v` del GRT — non OpenRCX)
 → F5-lite: `detailed_route` (2 iter, no CTS) + OpenRCX + OpenSTA `read_spef` (clock ideale)
 → F3 OpenSTA + SPEF OpenRCX (stesso SPEF F5-lite, senza un secondo DRT)
 → F5-CTS: `clock_tree_synthesis` + DRT + OpenRCX + OpenSTA `set_propagated_clock` sul netlist post-CTS (colpo a pagamento, non sostituisce F5-lite, non `make finish`)
 → F5-local: OpenRCX SPEF sul netlist cell/net — residuo F3→F5, non il SPEF F1, non `make finish`
 → active learning: residuo F3→F5-lite ordina host cell vs net; residuo F3→F5-local + incertezza sceglie il livello successivo (altro SPEF, o cell/net sul path SPEF) — non un vettore misto
 → F2 catalogo fisico: un punto AutoDMP (util/densità) misurato con GPL, non solo proxy RUDY
 → F2 regione: `create_blockage -max_density` sul bin IR (rXY / hotspot dbu) + GPL
 → F4 extract regione: `write_pg_spice` sotto lo stesso cap — mesh nuova, non gold
 → F2 ingest place / GRT del layout corrente
 → F3 ingest STA signoff
 → F4 extract candidato (`write_pg_spice` dopo place_pins+GPL+DP+pdngen) + `report_arrival`
 → F3 `report_arrival` sull’host attribuito (t50 per I(t), non lo STA dell’extract synth)
 → F4 restamp DirectLU / SA-AMG / RAS / Krylov-MOR (knobs PDN / I(t)×power dell’host attribuito / **static IR**) sullo extract nominato
 → F4 ingest gold (45.298 mV unrestampato)
 → attributo hotspot → regione → celle/net → modulo RTL (dpath/ctrl)
 → F3 cell-local: drive-up sulle celle del worst path (scope di modulo, non ABC)
 → F3 net-local: `BUF_X2` sugli hop del worst path (stesso modulo)
 → F3 port-net: `BUF_X2` sul net di porta al parent (hop ctrl↔dpath; non mescolato agli hop intra-modulo)
 → surrogato F0 (SSK-GP, residual F1→F2, GNN HPWL; F1→F4 solo se accoppiato)
 → Pareto per livello
 → prossimo candidato / extract
```

## Livelli (non un vettore unico)

| Livello | Cosa si cerca | Stato |
|---|---|---|
| **architecture** | extract e-graph equivalenti sul cono `dpath` (ROVER/ASPEN-shaped) | READY F1 + equiv |
| **logic** | sequenze ABC `{rewrite, refactor, resub, balance, …}` (BOiLS STD) | READY F1 · GP+**EHVI(area,WNS)** / EI · insert |
| **synthesis** | `ABC_AREA` ORFS (`abc_speed.script` + `-D 460`) | F0 catalogo + **F1 misurato** (non mescolato alle ops ABC) |
| **cell** | drive-up delle istanze sul worst path STA | READY F3 — scope di modulo, non `abc_ops` |
| **net** | `BUF` sugli hop attribuiti del worst path | READY F3 — scope di modulo **e** scope di porta (parent) sui crossing ctrl↔dpath; non un drive-up di cella |
| **physical** | util, densità, **regione IR**, netlist del candidato | F0 proxy + F2-fast + **GPL** + catalogo + **density cap sul bin IR** + ingest — non lancia finish |
| **routing** | GRT dopo place_pins + F5-lite DRT/OpenRCX + F5-CTS | READY F2 GRT + F5-lite SPEF (clock ideale) + F5-CTS SPEF (clock propagato) — non `make finish` |
| **pdn** | `c_decap`, pkg L, I(t)×power, mesh del candidato, solver MF | ingest gold + **extract `write_pg_spice`** + DirectLU/AMG/RAS/Krylov (non gold) |

Concatenare `rewrite` e `coreUtilization` in un unico box è **vietato** (`knobs_fp` include il livello).

## Fedeltà

| F | Ruolo | Stato |
|---|---|---|
| F0 | SSK-GP area ± std; congestion RUDY-class; skip F1 se l’ottimista è già peggiore | READY — **non** è IR |
| F1 | Yosys synth + ABC (script *file*) + `equiv_*` + `write_verilog -noexpr` | READY · chip flatten-first **o** cone-local ABC **o** ORFS `abc_speed` (synthesis) |
| F2 | place / GRT / finish ORFS **ingest** · F2-fast netgraph · GPL `-skip_io` · GRT+SDF | READY (GPL/GRT budgetati) |
| F3 | OpenSTA ideale (hier sul cono) + OpenSTA+SDF GRT + OpenSTA+SPEF OpenRCX + ingest | READY — SPEF F5-lite è clock ideale; F5-CTS usa `set_propagated_clock` |
| F4 | Dynamic IR/EM (libdpn A/B/C/D) + static IR sullo stesso extract | ingest gold + **extract candidato** + arrivals + restamp DirectLU/AMG/RAS/Krylov — **non** sostituisce il gold 45.298 |
| F5 | DRT + OpenRCX SPEF + OpenSTA `read_spef` | READY F5-lite (clock ideale) **e** F5-CTS (clock propagato) **e** F5-local sul netlist cell/net — il controller **non** lancia `make finish` |

F2-fast HPWL è in **unità griglia**; GPL HPWL è in **µm**. Non stanno sullo stesso asse Pareto.
La congestion F2-fast è `rudy_excess/(1+rudy_excess)` ∈ [0,1) — non è l’overflow GRT.

## E-graph / extract

Sul datapath GCD saturiamo uguaglianze:

- `a-b` ≡ `a+(~b+1)`
- `(x==0)` ≡ `~(|x)`
- unsigned `a<b` ≡ borrow di `{0,a}-{0,b}`

L’extract greedy (costo strutturale) preferisce l’operatore nativo; gli extract
forzati vengono misurati a F1 e subito a F3 (feedback EDA, idea ASPEN). Softmax su −cost/T è
ispirato a SmoothE, senza loop GPU. Se l’hotspot IR è su `dpath`, si riscrive
**solo quel cono** — niente restart del chip. Un extract peggiore sul WNS
(es. `lt_borrow` a −0.59 ns vs baseline −0.52) viene **deprioritizzato**, non
ripetuto come se l’area fosse l’unico asse.

Dopo il teacher chip (`liberty_default` flatten-first, 409.108 µm²) i proposal
BOiLS con focus IR `dpath` ricevono `scope=logic_cone` + `cone=dpath` +
`cone_module` (`knobs_fp` li distingue dal flatten-first). ABC gira sui moduli
del datapath (`GcdUnitDpathRTL`, `sub`, `a_reg`/`b_reg`, …); leftover = inverse
del cono pagato. Se lo STA elenca hop `ctrl/`, un colpo **logic_ctrl** mappa
`GcdUnitCtrlRTL`+`RegRst` (non è leftover del dpath e non riparte dal chip).
Lo STA sul `mapped_hier.v` vede `dpath/b_reg/…` e `ctrl/_07_` senza inherit.
Il netlist flattenato va a P&R/GRT/F4.

## Attributi (chip → block → region → cone → cell → net)

Il path OpenSTA del GCD (`dpath.a_reg…`) e l’hotspot ITerm (`x_dbu`, `y_dbu`)
diventano `scope=logic_cone`, `modules=[dpath]`, `region=r31`. Si registra
`transform + context → ΔQoR`, non solo `design → QoR`.

## Ottimizzatori (uno per problema)

Il **planner** legge `combo_frac`, il modulo, la regione e il WNS F3: IR combo su
`dpath` nomina gli extract (`lt_borrow` → `sub` → `eqz`) e non riparte dal chip.
Dopo ogni F1 lo STA ricalcola l’ordine: extract misurati peggiori sul slack
vanno in fondo. Congestione GRT alta o focus di regione sposta il budget sul
livello physical. I knobs ABC e `coreUtilization` restano fingerprint distinti.

- **BOiLS** — kernel SSK + GP + **EHVI(area, WNS)**; EHVI(area, IR) è secondario quando ≥2 extract F4 — mai un box unico con util/pkg L
- **DRiLLS** — UCB sul prossimo op ABC dato (ultimo op, focus IR); reward area+WNS
- **e-graph** — saturation + extract, non RTL casuale
- **GNN** — 2 layer mean-aggregate + ridge su HPWL F2-fast; incertezza alta se n&lt;4
- **AutoDMP-shaped** — catalogo util/densità: F0 è solo un prior; **un punto è GPL**
- **OpenROAD GPL** — colpo `-skip_io` sul vincitore F1 + colpo catalogo (non F5)
- **LLM** — proposer opzionale (`DSE_LLM_URL`); fallback simbolico; **non** è l’ottimizzatore

## Layer sostituibili

`learn/dse/layers.py` registra extraction / power / activity / current / DSE /
surrogate / solver / physical_fast / physical_gpl / routing / timing.
Extraction è `write_pg_spice` sul candidato legalizzato **oppure** ingest del finish.
Activity è OpenSTA `report_arrival` sul candidato (t50), non una mappa RTL→ITerm inventata.
Solver è `make_solver(direct|amg|bicg|ras)` — AMG è residuo MF, non il gold.
Il gold GCD 45.298 mV non si ristampa. EM J è `em_thermal_snapshot` su V_worst.

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
