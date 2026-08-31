# PLAN — Fase 2: scenario guida I(t), fronte gated onesto, coda IR dichiarativa

Stato: passo A ✅, E ✅, B ✅, C1 ✅, C2 ✅, C3 ✅, C4 ✅, C5 ✅. I passi si eseguono **in ordine**; ogni passo si chiude
solo con i test verdi indicati e con commit dedicato. Nessun passo introduce un
tipo `DesignState` parallelo: si irrigidisce ciò che esiste.

Fase 1 (schema → slice dichiarative) è **chiusa** su `ca47126`
(passi 0–6). Questo documento la sostituisce come piano eseguibile.
Riferimenti: `learn/dse/README.md`, `.cursor/SETUP_LOG.md`, PR #2.

---

## Diagnosi (stato dopo Fase 1, 2026-08-31)

Misurato sul tree `ca47126`, non a memoria.

| File | Righe | Ruolo |
|---|---:|---|
| `learn/dse/controller.py` | 4920 | Teacher F1 + 3 slice `run_stage` + **coda IR inlined** (~939–2782) |
| `learn/dse/acquire.py` | 3146 | **66** `should_pay_*`. Le stage migrate le chiamano ancora |
| `learn/dse/stages.py` | 1559 | Slice: logic / place-route / F4 head. `should_pay_generic` solo su 3a |
| `learn/scripts/test_dse.py` | 4925 | Un solo `main()`: metriche → planner → IR leftover → F4 live |
| `learn/dse/current_scenario.py` | 188 | Dataclass + `infer_scenario`. Non guida `plan_events` |
| `learn/scripts/dse_f4_worker.py` | 349 | `--scenario` stampato; I(t) da `--sta/--vcd/--saif` |
| `learn/dse/planner.py` | 790 | `next_candidate_ids` → `plan["next"]` e report. **Non sceglie parent** |
| `studio/.../DsePanel.tsx` | — | Legge `report.pareto` (ungated). Ignora `pareto_gated` / scenario |

**Cosa è già vero (non rifare).**

- `STAGES_LOGIC_TRANSFORM` / `STAGES_PLACE_ROUTE` / `STAGES_F4_HEAD` girano
  come tabelle. GRT sta fra STA e SDF **per dati**, non per commento.
- `STAGE_F5_PORT` e `STAGE_PHYSICAL_CATALOG` restano singoli perché
  residual/port/f2_region li spezzano.
- Refine depth ≥ 1 è già generico: `dispatch.run_next_refine` + `actions.py`
  + `frame.py`. Non è un blocco controller da “tabellizzare”.
- `f1_pareto_parents` = area-best + WNS-best **solo F1**. È corretto per
  F1→F2. Non è il buco del passo 5.
- GCD finish live: DirectLU **6.075 mV**, `current_scenario.source=sta_t50`,
  `n_r` worker **5816**. Gold **45.298** intatto. AES `febe6804241c` intatto.
- `leftover_cone_region_next` / `winning_ir_region_next` sono già inspector
  closed-loop (`kind ∈ {extract, pdn}`), non one-shot.

**Cosa è ancora falso (i buchi da chiudere).**

1. **Scenario è un francobollo.** `build_worker_cmd` passa `--scenario` JSON
   e, se c’è spice+STA, passa anche `--sta`. Il worker fa
   `plan_events(..., sta_arrivals=sta, vcd=vcd, saif=saif)` **ignorando**
   `source`. `ideal_triangle` + STA su disco ⇒ STA vince. CCS è già GAP.
2. **Pareto gated è contratto, non picker.** `plan["next"]` e
   `report["pareto_gated"]` esistono. Cell / net / extract / catalog
   pickano `f1_wns_winner` + `f1_area_winner` + `f1_ok`. Studio badge-a
   `report.pareto`. Un WNS F1 migliore può ancora *sembrare* il vincitore
   in UI anche se il fronte gated tiene F1 e F5.
3. **La coda IR è fotocopia.** Dopo `STAGES_F4_HEAD` il controller ripete
   `n_*` / `should_pay_*` / `step("acquire")` / `evaluate_*` / `step("evaluate")`
   per IR_STEER … EM_STRAPS. `via` / `why` / `fidelity` sono stringhe
   asserite in `test_dse.py`. Residual/port/f2_region stanno **fra** le
   slice, non in coda.
4. **Due numeri IR.** Report/UI dicono ancora “A gold” accanto al finish
   corrente. I test distinguono 6.075 vs 45.298; Studio
   (`DynamicIrHeatmap.tsx`, `suite.ts`) no.
5. **`test_dse.py` è un monolite.** Lo split “durante il passo 3” non è
   successo. Si spacchetta **dopo** i lotti C, un modulo per commit,
   tenendo un solo entrypoint.

**Cosa resta fuori (non è una mancanza di Fase 2).**

AES come secondo GCD (coni, e-graph, F5-CTS, Krylov, DSE controller pieno),
ibex slang, CUDA, CCS su Nangate45, closed-loop synth↔PD libero, DesignState,
LLM/GNN come centro del controller, ristampare il gold.

---

## Vincoli permanenti (valgono per ogni passo)

- VM cloud ~15 GiB / 4 CPU / swap 0. Un solo job pesante; `prlimit --as=8GiB`.
- **Mai** Krylov/MOR su mesh AES ~50–70k R. `admit_solve` deve rifiutare.
- **Mai** sovrascrivere `memory_aes.jsonl` riga `febe6804241c`
  (`n_r=73139`, static **6.954 mV**).
- **Mai** ristampare il gold GCD 45.298 mV
  (`learn/sim/reports/dynamic_ir_flowlab.json`).
- Finish FlowLab corrente = **6.075 mV** su `n_r=5816`: è `current_run`,
  non `reference_run`. I test non li confondono. `n_r_from_spice` (~5821)
  ≠ `n_r` worker: non pinare 5816 sulla riga spice.
- AES SDC 0.82 ns, `top=aes_cipher_top`; F5 AES rifiuta path `/gcd/`.
- Test solo sintetici o GCD-scale. `pkill -f` vietato (kill per PID).
- DirectLU = reference numerico. B/C/D = accelerator + errore vs A.
- **Non** `mem.touch` su hit F4 in cache (rompe
  “live memory is not restamped, got 113”).
- **Non** cancellare `should_pay_*` che stage o test chiamano ancora.
  `test_dse.py` asserisce frammenti `why` (`"not bumps"`, `"not gold"`).
- **Non** sostituire `f1_pareto_parents` per F2-fast. F1-only è corretto.
- **Non** usare un F5 come host del *primo* `cell_size_up`:
  `evaluate_cell_size` vuole `mapped_v` di un netlist F1.
- Un solo `test_dse.py` alla volta (~5 min). La suite veloce non lancia F4.

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

Passi A / B / E (niente mesh nuova): schema + designs + head di `test_dse`
bastano in locale; `test_dse` live resta il gate prima del commit se si
tocca worker / `solve_f4` / report IR.

---

## Passo A — Lo scenario guida I(t) (piccolo, alto onestà)

**Problema.** `CurrentScenario` è serializzato su argv e su
`SolveResult.activity_via`, ma `plan_events` in
`learn/scripts/dse_f4_worker.py` (circa 165–181) carica STA/VCD/SAIF dai
flag file. `build_worker_cmd` (`learn/dse/f4_oracle.py` 175–201) aggiunge
`--sta` se il path esiste, anche quando `source=ideal_triangle`.

**Non cambiare.** Infer default GCD finish (`kind=="finish"`, `design_id=="gcd"`,
STA su disco, nessuno `source` esplicito) resta `sta_t50`. È il path 6.075.
`liberty_ccs` resta GAP. Waveform assente resta ABSENT, mai inventata.
`pdn_activity.plan_events` non cambia firma: il worker decide *cosa* passarle.

**Modifiche.**

1. `dse_f4_worker.py` dopo il parse di `--scenario`:
   - `ideal_triangle` → non caricare STA/VCD/SAIF anche se i file ci sono;
     `plan_events(..., sta_arrivals=None, vcd=None, saif=None)`.
   - `sta_t50` + `activity_status=ABSENT` → non applicare STA; status GAP/ABSENT
     già coperto da infer.
   - `sta_t50` + REAL → caricare solo `--sta` (come oggi per 6.075).
   - `vcd`/`saif` + ABSENT → non passare file (già vero in `build_worker_cmd`).
   - `vcd`/`saif` + REAL → waveform; non promuovere STA a source.
   - `liberty_ccs` → invariato (exit 0 + GAP).
2. `build_worker_cmd`:
   - `source=ideal_triangle` → `--no-sta`, niente `--sta`, niente activity flags.
   - `source=sta_t50` e STA file → `--sta` (GCD 6.075 invariato).
   - `source=sta_t50` e STA mancante → `--no-sta`, scenario ABSENT.
3. Nessun nuovo campo su `CurrentScenario`. Il fingerprint già include `source`.

**Accettazione.**

- `test_candidate_schema.py`: cmd GCD default contiene `--scenario` + `sta_t50`
  e `--sta` (o path STA). Cmd esplicito `ideal_triangle` ha `--no-sta` e
  **non** ha `--sta`, anche se lo STA GCD è su disco.
- `test_designs.py`: AES waveform-free resta senza `--vcd`/`--saif`.
- `test_dse.py` live A: DirectLU **6.075** ± 0.05, `source=sta_t50`,
  `activity_via.scenario.source=sta_t50`, ≠ 45.298.
- Triangolo esplicito sulla stessa mesh: `activity_status=SYNTHETIC`.
  **Non** pinare il droop a 6.075 (può differire). Un unit test di argv
  basta; non lanciare un secondo F4 live nel passo A se il primo è già
  `sta_t50`.
- Gold unrestampato. Nessun AES Krylov.

---

## Passo B — Fronte gated come preferenza, non come F1→F2 (piccolo)

**Problema.** Il passo 5 ha scritto il contratto (`dominates_with_fidelity`,
`pareto_front_gated`, `next_candidate_ids`) e lo stampa. I parent reali
restano F1 winners. Studio (`DsePanel.tsx` ~191–192, ~630) badge-a
`report.pareto`.

**Non fare.**

- Non sostituire `f1_pareto_parents` / `f1_area_winner` / `f1_wns_winner`
  per F2-fast, cell *first shot*, net *first shot*, F4 extract host.
  Quegli host devono essere netlist mappati F1 (`mapped_pick` + `mapped_v`).
- Non far pickare residual/port/IR dallo gated front: lo host è il
  residual (`steer_from_*`), non un WNS.
- Non cambiare `pareto_front` (report storici).
- I check `test_dse.py` “area winner is liberty_default” / “WNS winner is
  the delay-improved sequence” restano verdi senza toccare i valori.

**Modifiche.**

1. `learn/dse/planner.py` (o `metrics.py`): helper
   `prefer_gated(mem, level, cands, *, pred=None) -> list`.
   Filtra/ordina `cands` tenendo chi sta sul fronte gated di quel livello;
   se il fronte è vuoto, restituisce `cands` invariato. Non inventa host.
2. Un consumer reale, non un helper morto:
   - Studio `DsePanel.tsx`: badge e conteggio usano `pareto_gated` se
     presente, fallback a `pareto`. Tipo TS: aggiungere `pareto_gated?`.
   - Opzionale e solo se un lotto C introduce una lista mista allo stesso
     livello (es. più extract F4 già misurati): `prefer_gated` su *quella*
     lista. Non anticipare.
3. Unit in `test_dse.py` (blocco metriche in testa, già c’è il gated):
   F1 WNS migliore + F5 WNS peggiore restano entrambi sul gated front;
   un picker “solo WNS” terrebbe solo F1 — documentare che `prefer_gated`
   non fa quella riduzione.

**Accettazione.**

- `test_dse.py` verde senza cambiare valori attesi dei winner F1.
- `test_candidate_schema.py` / `test_frame.py` verdi.
- Studio: il tipo accetta `pareto_gated`; nessun cambio di layout obbligatorio
  oltre a leggere la chiave giusta. Verifica a mano sulla pagina DSE solo
  se il passo tocca CSS/markup visibile.

---

## Passo E — Due numeri IR etichettati (piccolo, dopo A)

**Problema.** I test sanno che 6.075 ≠ 45.298. Studio e copy dicono ancora
“Solver A golden” sul finish corrente (`DynamicIrHeatmap.tsx` ~295, ~594;
`suite.ts` “Solver A gold”).

**Modifiche.**

- Report F4 / DSE: campi espliciti `current_run_mv` (finish vivo) e
  `reference_run_mv` (45.298, solo lettura del gold JSON, mai restamp).
  Se il gold file manca, `reference_run_mv=null` — non inventare.
- Copy Studio: “A = DirectLU current_run” vs “reference_run 45.298
  (historical gold, unrestamped)”. Non rinominare `solver_kind=direct`.
- `test_candidate_schema.py` o head `test_dse`: le chiavi esistono e
  `current_run_mv` non è 45.298 sul path finish GCD.

**Non fare.** Ristampare gold, cambiare soglie signoff, toccare
`febe6804241c`, fondere i due JSON `dynamic_ir_flowlab.json` e
`dynamic_ir_flowlab_direct.json`.

**Accettazione.** Gold file byte-uguale. Live A resta 6.075. UI non
presenta 6.075 come gold.

---

## Passo C — Strangler della coda (stessa regola di 3a–3e)

Ordine dei lotti **sacro** (dipendenze di `via` / residual / extract_id).
Un lotto = un commit. `why` / `step` / `via` / `fidelity` identici al
blocco inlined. `test_dse.py` verde **senza** cambiare valori attesi.
Misurare `wc -l learn/dse/controller.py` prima/dopo. Domain `should_pay_*`
restano in `acquire.py`; le stage le chiamano.

Pattern già provato: `Stage` + `run_*` + `_pay_and_maybe_eval`.
Loop closed-loop (`leftover_*_next`): **non** un `Stage` one-shot —
helper `run_inspect_loop` che chiama l’inspector, paga extract o PDN,
ripete fino a `None` / wall / cap già nei test (4 iter leftover-cone-region).

F4 restano `needs_admit=True` e passano da `ctx["admit_paid_f4"]` +
wrapper `evaluate_f4_*` del controller (stamp SolveResult, no restamp
JSONL live).

Teacher F1 (BOiLS while + ctrl-cone, ~751–890) **resta inlined**. Non è
fotocopia IR; è acquisition SSK-GP/EHVI.

### C1 — residual_steer + port_steer + f2_region

Siedono **fra** `STAGES_PLACE_ROUTE` e `STAGES_F4_HEAD` (controller ~939–1070).

| Blocco | `should_pay_*` | `fidelity` acquire | evaluate |
|---|---|---|---|
| residual_steer | `should_pay_residual_steer` | `RESIDUAL_STEER` | `evaluate_f5_local` / `evaluate_cell_size` / `evaluate_net_buffer` su `steer["level"]` |
| port_steer | `should_pay_port_steer` | `PORT_STEER` | `evaluate_net_buffer(..., source="net_buffer_spef")` |
| f2_region | `should_pay_f2_region` | `F2_REGION` | `evaluate_f2_gpl` + `extra_knobs` region; parent = `_mapped_pick(F1 winners)` |

Dopo C1 si può unire `STAGE_F5_PORT` / `STAGE_PHYSICAL_CATALOG` nelle slice
vicine **solo se** l’ordine runtime resta identico (port dopo residual,
catalog prima di f2_region, f2_region prima di F4_HEAD). Se unire le slice
rompe il commento/ordine, lasciare i due stage singoli.

**Accettazione.** Check planner “schedules residual-steered / port / f2_region”
invariati. Nessun valore QoR nuovo. Linee controller ↓.

### C2 — ir_steer + host_ir_steer + f4_scale_win

`while planned_*` (~1074–1232). Cap loop già in `should_pay_ir_steer`
(“IR-steer loop caps at region family + unused catalog”).

| Blocco | pay | via child |
|---|---|---|
| ir_steer | `should_pay_ir_steer` + `steer_from_ir_residual` | `active_f4_ir` |
| host_ir_steer | `should_pay_host_ir_steer` + `steer_from_host_ir_residual` | `active_f4_host_ir` |
| f4_scale_win | `should_pay_f4_scale_win` | `f4_iscale_win`; host `iscale_parent` + `winning_host_pdn` |

Loop = `run_inspect_loop` o `Stage` con `max_shots` allineato al cap
esistente. Non alzare il cap.

**Accettazione.** Blocco `test_dse` su `steer_from_ir_residual` /
`should_pay_ir_steer` (decap_200f → pkg_l_100p, n_steer cap) invariato.

### C3 — famiglia ir_cell (depth 0, non refine)

~1234–1474. Ordine: size → extract → PDN → region → region PDN.

| level planner | pay | via / source |
|---|---|---|
| `ir_cell` | `should_pay_ir_cell` | `cell_size_ir` / `active_f4_ir_cell` |
| `ir_cell_extract` | `should_pay_ir_cell_extract` | `f4_ir_cell_extract` |
| `ir_cell_pdn` | `should_pay_ir_cell_pdn` + `steer_from_ir_cell_residual` | `active_f4_ir_cell_pdn` |
| `ir_cell_region` | `should_pay_ir_cell_region` | region density cap |
| `ir_cell_region_pdn` | `should_pay_ir_cell_region_pdn` | restamp PDN |

Host: `iscale_parent` / `ir_cell_host` (attribution, non Pareto).

### C4 — winning_ir catalog + iscale_champ + famiglia ir_cell_champ

~1476–1927.

| level | note |
|---|---|
| `winning_ir_pdn` | `should_pay_winning_ir_catalog` / steer unused Dynamic IR |
| `f4_scale_champ` | `should_pay_f4_scale_champ` |
| `ir_cell_champ` | size-up sul champ |
| `ir_cell_champ_extract` / `_pdn` | mesh + restamp |
| `ir_cell_champ_cone` / `_extract` / `_pdn` | cone dpath/ctrl; leftover modules già in `acquire` |

`via` champ (`active_f4_ir_cell_champ_*`) sono stringhe pinate nei test.
Copiarle.

### C5 — loop inspector leftover-cone-region e winning_ir_region

~1929–2150. Già `leftover_cone_region_next` / `winning_ir_region_next`.

Estrarre `run_inspect_loop(ctx, next_fn, handlers)` nel controller o in
`stages.py`. Il `for _ in range(4)` leftover-cone-region e il loop
winning-IR-region restano cap/why identici, incluso il primo acquire
negato `"no leftover-cone-region extract or |Δ| PDN"`.

**Non** convertire questi loop in un solo `Stage(max_shots=1)`.

### C6 — winning_ir_region_cell depth 0 (size / extract / PDN)

~2175–2316. Depth ≥ 1 è già `run_next_refine` **subito dopo** (~2333).
Non fondere depth 0 nel dispatch in questo lotto: `frame.py` tratta
suffix vuoto come depth 0, ma il controller attuale paga depth 0
inlined e poi entra nel while refine. Cambiare quel confine è un
refactor a parte, fuori C6.

Pay: `should_pay_winning_ir_region_cell` / `_extract` / `_pdn`.

### C7 — champ AMG/RAS/Krylov + static IR/mesh/straps + EM (ultimo)

~2361–2782. Steer-special, ultimi perché leggono champ/static già scritti.

| acquire fidelity | pay | solver / catalog |
|---|---|---|
| `F4_AMG_CHAMP` | `should_pay_f4_amg_champ` | `evaluate_f4_pdn(..., solver="amg")` |
| `F4_RAS_CHAMP` | `should_pay_f4_ras_champ` | `solver="ras"` |
| `F4_KRYLOV_CHAMP` | `should_pay_f4_krylov_champ` | `solver="krylov"` + residual vs Direct champ |
| `F4_STATIC_IR` | `should_pay_static_ir_steer` | `steer_from_static_ir_residual` |
| `F4_STATIC_MESH` | `should_pay_static_mesh` | bump catalog |
| `F4_STATIC_STRAPS` | `should_pay_static_straps` | pitch catalog (`"not bumps"` / `"not gold"`) |
| `F4_EM_STRAPS` | `should_pay_em_straps` | width catalog |

Krylov **solo** sul champ GCD già ammesso. `admit_paid_f4` resta.
Niente AES.

Dopo C7 il controller `run_controller` dovrebbe essere: ingest/teacher F1
→ slice logic → slice place-route → C1 stages → slice F4 head → C2–C7
stages/loop → `run_next_refine` while → report. La coda fotocopiata
sparisce; F1 teacher no.

**Accettazione per ogni lotto C.** Suite veloce + `test_dse.py` ALL PASSED.
Droop live 6.075 / `sta_t50`. Gold unrestampato. SETUP_LOG con Δ linee
controller. Un commit.

---

## Passo D — Spacchettare `test_dse.py` (dopo C, un modulo per commit)

**Problema.** 4925 righe, un `main()`. Fase 1 aveva detto “stage per stage
durante il 3”: non fatto. Farlo **adesso** in un colpo rompe il gate da 5 min.

**Regola.** Un file estratto per commit. Stesso `check()`. `test_dse.py`
resta l’entrypoint che importa e chiama i pezzi, così CI/docs restano

`PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse.py`.

Tagli naturali (ordine):

1. `test_dse_metrics.py` — dominates / gated / HV / EHVI (testa attuale ~50–220).
2. `test_dse_memory.py` — JSONL / BOiLS / e-graph / cataloghi.
3. `test_dse_planner.py` — attribution, `plan_search`, f1 winners.
4. `test_dse_steer.py` — residual / F5 / IR leftover / champ / static (bulk).
5. Live F4 A/B/D/C **resta** in `test_dse.py` (o `test_dse_live_f4.py`
   importato per ultimo). Un solo processo, un solo job pesante.

**Non fare.** Due `test_dse` paralleli, pin di `n_r` spice=5816, split del
blocco live in quattro process.

**Accettazione.** Stesso numero di `ok` / stessi messaggi. `test_dse.py`
ALL PASSED ~5 min. Nessun valore atteso nuovo.

---

## Esplicitamente NON in piano

- Tipo `DesignState` parallelo a `Candidate`.
- LLM / GNN / e-graph / RL come centro del controller.
- Closed-loop synthesis↔PD libero (resta: parameter-DSE, poi structural;
  refine chain è già la ricerca IR).
- Restamp gold 45.298; F5-CTS AES; Krylov AES; full AES DSE; ibex slang; CUDA.
- Flatten delle knob across livelli.
- Cancellare i 66 `should_pay_*` “perché c’è generic”.
- Usare il gated front per promuovere F1 a F2 o per il first cell size-up.
- Fondere depth-0 winning_ir_region_cell in `run_next_refine` dentro C6.
- Flatten del teacher F1 BOiLS.

---

## Ordine dei commit

```
1  scenario guida I(t)                         (passo A)
2  etichette current_run vs reference_run      (passo E)
3  prefer_gated + Studio legge pareto_gated    (passo B)
4  C1 residual / port / f2_region
5  C2 ir_steer / host_ir / iscale_win
6  C3 famiglia ir_cell
7  C4 winning_ir + champ family
8  C5 inspect loops leftover / winning_ir_region
9  C6 winning_ir_region_cell depth 0
10 C7 champ solvers + static/EM
11 (opt) test_dse_metrics.py estratto          (passo D.1)
```

Ogni commit: test verdi del lotto, riga in `.cursor/SETUP_LOG.md`,
push, aggiornamento PR #2. Un `test_dse` alla volta.

---

## Come si misura il successo di Fase 2

- Worker: `source` decide STA/VCD/SAIF; triangolo esplicito non “ruba” STA.
- GCD live A resta **6.075 mV** + `sta_t50`. Gold 45.298 e AES
  `febe6804241c` intatti.
- Studio non badge-a un fronte ungated come se fosse gated; non chiama
  6.075 “gold”.
- `run_controller` dopo C7 non ha più i blocchi fotocopia IR_STEER…EM;
  F1 teacher e `run_next_refine` restano i due loop non-tabella, per
  ragioni diverse (acquisition vs refine generico).
- `test_dse.py` può diventare un runner; il live F4 resta un job.

Fase 1 archivio (git, non rieseguire): 0 `3bd9479` · 1 `4c4bcc7` ·
2 `9e1bab4` · 3a `74e1173` · 4 `aed3a6d` · 3b `c5f1d4a` · 3c `d4d2548`
· 3d `b2b96c9` · 3e `d94df2f` · 5 `9785bca` · 6 `14b6e47` / `ca47126`.
