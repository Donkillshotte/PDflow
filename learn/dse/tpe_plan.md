# Piano: TPE sul die ufficiale (finish vero)

Solo piano. Nessun trial TPE parte da questo commit. Le scelte sotto
sono pre-registrate e non si ritoccano dopo i primi dati.

Contesto: il prodotto oggi è OFAT (una ricetta = un knob) + deepen
(coppie di win). I paper (AutoTuner, AutoDMP, MOTPE) cercano uno spazio
continuo con TPE/BO, ma spesso si fermano al place e ottimizzano HPWL o
un mix PPA, e muovono il die. Noi vogliamo **lo stesso cervello di
ricerca**, **il nostro forno** (CTS + route + finish + IR/leak) e **il
die fisso**.

Questo piano **non** riscrive I1–I5 né §5 P0–P7. Non è un surrogate
bayesiano del finish (vietato in `next_iteration_plan.md` §7 con pochi
punti). Ogni osservazione TPE è un finish vero, o uno STOP al place.

## 0. Vincoli non negoziabili

- Netlist Yosys ufficiale dello slot. RTL fisso. ABC area.
- Floorplan fisso: `DIE_AREA` / `CORE_AREA` dal DEF ufficiale. Niente
  `CORE_UTILIZATION`, `CORE_ASPECT_RATIO` nello spazio di ricerca.
- Win rule invariata (`win_rule.py`): slack ±5 ps, area/potenza/leakage/IR
  ±10%, `wrong_die` se il die si muove.
- Un job pesante alla volta. `prlimit` resta nel wrapper.
- Mai `FLOW_VARIANT` in {flowlab, learn, base}, mai krylov, mai restamp
  oro GCD 45.298 mV, mai riga `febe6804241c`.
- Registry unico: `learn/sim/dse/campaign_experiments.jsonl`.
- Niente `if design ==` nel tuner. I range sono offset sui default di
  `config.mk`.

## 1. Perché non AutoTuner / Ray / white-box

`tools/AutoTuner` è nel tree ORFS. Non lo usiamo come prodotto.

| AutoTuner | Questo piano |
|---|---|
| Ray + HyperOpt/Ax/Optuna sul JSON ORFS | Optuna TPE, processo singolo |
| Mix PPA (`coeff_perform/power/area`) | Vincoli + score della **win rule** |
| Spesso include util / die | Die inchiodato dal DEF |
| Flow intero o proxy, a scelta del JSON | Place → policy → CTS/route/finish |
| Non sa di leakage/IR/`wrong_die` | Li usa |
| Non riusa `1_2_yosys.v` ufficiale | Sempre, salvo synth (fuori v1) |

White-box (patch al C++ di OpenROAD) è laboratorio, non prodotto.
Un GNN/GP che predice il finish al posto di cuocerlo è laboratorio.

TPE e non NSGA-II in v1: la win rule è già un regione fattibile + un
ordinamento tra i win. NSGA-II ridà un Pareto che poi dovremmo
ri-tagliare con la stessa regola. TPE con vincoli è la mappa diretta.

## 2. Idea centrale: fattibilità, poi rango

La win rule **non** è uno scalare liscio. Forzarla in un mix tipo
`0.5·WNS+0.3·area` è come AutoTuner: insegue un'altra cosa.

Due strati, entrambi derivati da `win_rule` (stesse `SLACK_PS=5`,
`METRIC_FRAC=0.10`, stesso `_imp`):

**Vincoli** (Optuna: `c ≤ 0` è fattibile):

- Slack: `c_slack = -5 - ΔWNS_ps` → fattibile sse timing non peggio di 5 ps.
- Assi: per area, potenza, leakage, IR, `c = -10 - imp_%` → fattibile sse
  nessuno è ≥10% peggio. Asse `None` → vincolo 0 (non squalifica) e non
  conta come “meglio”.
- Die: `c_die = 0` se `not moves_floorplan`, altrimenti `1`.
- Finito: `c_done = 0` se `status=done` e c’è finish WNS, altrimenti `1`.

Uno STOP al place **non** è un lose di IR. È `c_done=1` e, se la policy
ha predetto slack morto, anche `c_slack>0`. TPE impara “questa zona è
tardi”, non “questa zona ha IR orribile”. Un fail DPL/route è `c_done=1`
senza sporcare gli assi QoR.

**Score da minimizzare**, solo tra i fattibili (win o tie):

```
better = max(0, area_imp, power_imp, leak_imp, ir_imp)   # % meglio
if better >= 10 or ΔWNS_ps > 5:   # sarebbe win
    score = -1 - 0.01*better - 0.001*max(0, ΔWNS_ps)
else:
    score = 0   # tie
```

Così: ogni lose/wrong_die/incompleto è infattibile; ogni tie è 0; un win
è negativo; un win più largo (IR −40% vs −10%) è più negativo. Non si
premiamo un asse al 9% se un altro è a −11% (vincolo). Non si cambia
`verdict()`.

Il coordinatore e `eval_policy` continuano a usare `verdict == "win"`.
Lo score esiste **solo** per far camminare TPE.

## 3. Spazio v1 (stesso die, stessa netlist)

Una dimensione = un meccanismo del catalogo, reso continuo o discreto
intorno al default di config. Due pad (global/detail) restano **un**
asse: il catalogo li muove insieme.

| Dimensione Optuna | Tipo | Range | Se = default di config |
|---|---|---|---|
| `PLACE_DENSITY_LB_ADDON` | continuo | default ±0.10, clamp `[0, 0.99]` | ometti la env (resta config) |
| `cell_pad` | intero | `{0,1,2}` | ometti entrambi i `CELL_PAD_*` |
| `TNS_END_PERCENT` | intero | `[0, 100]` | ometti |
| `SETUP_SLACK_MARGIN` | continuo | `[0, 0.08]` ns | ometti se 0 |
| `HOLD_SLACK_MARGIN` | continuo | `[0, 0.05]` ns | ometti se 0 |
| `CTS_BUF_DISTANCE` | continuo | `[80, 200]` µm | ometti se uguale al default di config |
| `GPL_TIMING_DRIVEN` | categorico | `{0,1}` | ometti se 1 (default ORFS) |

**Sempre iniettati, mai campionati:** `DIE_AREA`, `CORE_AREA` da
`official_box(design)`; `ABC_AREA=1`, `ABC_SPEED=0`; netlist
`1_2_yosys.v` ufficiale.

**Mai nello spazio:** `CORE_UTILIZATION`, `CORE_ASPECT_RATIO`,
`SYNTH_HIERARCHICAL`, `ABC_SPEED`, rewrite Verilog, seed di placer,
white-box.

Perché omettere i default: `run_design_finish.sh` applica un knob solo
se la env è non vuota. Passare `HOLD_SLACK_MARGIN=0` **non** è “non
toccare”: è un valore. TPE deve distinguere “lascia config” da “forza 0”
solo dove 0 è un vero knob (TNS=0 = skip repair, che è nel catalogo).

`cell_pad=0` significa entrambi i pad a 0, esplicito: è una prova,
non “lascia config”, se il default non è 0.

## 4. Valutatore = cook, non un secondo forno

Oggi `cook_recipe.py` sa solo `--recipes`. Il path place → `decide()` →
finish → `record_experiment.py` è quello giusto. Non duplicarlo.

Estrarre `learn/dse/cook.py` (`cook_one(...)`) usato da:

- `cook_recipe.py --recipes …` (invariato per cover/improve)
- `cook_recipe.py --knobs '{...}'` XOR `--recipes` (TPE)
- `run_tpe.py`

Pin die, refuse floorplan recipes, ABC area, netlist ufficiale, policy
STOP, registro: una funzione sola.

**Nome variant:** `camp_{design}_tpe_{fp}` dove `fp` è 12 hex dello
sha256 del vettore **canonico** (chiavi ordinate, float arrotondati a
6 decimali, senza `DIE_AREA`/`CORE_AREA`/`ABC_*`). Motivo: ORFS scrive
sotto `FLOW_VARIANT`; `ExperimentLog.has(variant, phase)` salta i
doppioni; due fasi con lo stesso variant si pestano i log. L’hash è
globale, non per-fase.

`role=knob`. `extra.tuner="tpe"`, `extra.knobs=…`, `extra.tpe_trial=n`.
`recipe_ids` vuoto (non inventare un id catalogo). Le label umane
derivano dai knob, come già fa `label_for` in fallback.

Fase registro: `T1`. Non riusare J1/C1/L1.

## 5. Warm-start: il cover non si butta

TPE a freddo con 8 trial è peggio delle combo deepen. Il log **stesso
die** è il prior.

Regole per importare una riga in Optuna (`create_trial` completato, zero
ricotture):

- stesso `design` e clock dello slot
- `status=done` e finish WNS presente
- `verdict != "wrong_die"`
- netlist ufficiale (`fresh_synth` assente/false)
- `extra.knobs` proiettabile sullo spazio v1 (chiavi mancanti = default
  config)
- fingerprint non già in studio

Le univariate che hanno vinto (place denso, padding, setup, CTS fitti,
place sparso, …) diventano trial completati con il loro score. I lose
stesso die diventano trial infattibili: TPE impara i muri.

Le combo deepen **non ancora cotte** (place denso+padding su gcd, ecc.)
si `enqueue` come primi ask, non come coda parallela. Poi TPE campiona.

## 6. Integrarlo nel coordinatore (il punto delicato)

Oggi `coordinate()` precompute **tutte** le combo deepen e
`max-cooks` ne cuoce 4 di fila. Va bene per una griglia. **Non va bene
per TPE:** ogni finish deve aggiornare il modello prima del trial
successivo.

Quindi:

1. **Cover** — invariato. Una ricetta, nomi leggibili, buchi di catalogo.
2. **Improve** — invariato. Solo slot con 0 win (spi chiuso, knob nuovi).
3. **Tune** — sostituisce deepen nel **default**. `--deepen` resta override.
4. **Stop** — catalogo coperto, improve esaurito, e (budget TPE finito
   **oppure** slot non ammissibile al tune).

Ammisibile al tune: esiste il base, die pinnabile (`official_box`), e
**non** (very-closed ∧ 0 product win ∧ improve esaurito). spi @ 1 ns
resta stop. Non si bruciano trial TPE su un die già chiuso di 600 ps
dove OFAT non ha mosso nulla.

Un invocazione di `run_recipe_loop.py` in modo tune:

- decide `tune` + `design` (cheap-first tra gli ammissibili)
- **non** elenca 20 vettori
- chiama `run_tpe.py --design … --max-cooks N` che fa il loop
  ask → cook_one → tell, uno alla volta

`run_recipe_loop --dry-run` stampa `decision=tune`, lo slot, il numero di
trial già in studio, il prossimo fingerprint se enqueue, niente ricette
floorplan.

Deepen non si cancella: è laboratorio/override. Le combo già in coda
mentale diventano enqueue TPE, così non perdiamo l’idea “denso+pad”
e non le cuciniamo cieche in blocco.

## 7. Budget e stop TPE

- Un design per volta, cheap-first (gcd prima).
- v1 live: **gcd, ≤8 finish nuovi** (oltre il warm-start). Poi si legge
  se TPE ha trovato un win che OFAT/deepen non avevano. Solo allora
  ibex/aes.
- Stop locale: `max_trials` **oppure** 3 finish fattibili di fila senza
  nuovo `verdict=win` e senza migliorare lo score del miglior win.
- Fail/timeout: registrati, trial infattibile, non ripetuti con lo
  stesso fingerprint.
- Disco: le variant `camp_*_tpe_*` si possono pulire dopo freeze del
  jsonl; mai `flowlab`, mai `camp_*_base`.

## 8. Dipendenze e test

- Optuna **solo** in `run_tpe.py` / `learn/requirements-tune.txt`.
  Spazio e score **non** importano Optuna: `test_dse_next.py` resta
  veloce e senza pip extra.
- Se Optuna manca, `run_tpe.py` esce 2 con il comando di install.
- Test senza ORFS:
  - lo spazio non contiene chiavi floorplan
  - `pin(design, sampled)` aggiunge box e toglie util/aspect
  - `score(win) < score(tie)`; lose/wrong_die hanno un vincolo `> 0`
  - STOP non inventa IR
  - fingerprint stabile; collide → skip
  - warm-start salta `wrong_die` e `fresh_synth`
  - omettere env al default
  - coordinatore: dopo cover+improve, default `tune` non `deepen`;
    nessuno `if design ==`
- Un test Optuna (skip se manca): fake evaluator deterministico, TPE
  propone un secondo punto dopo un lose finto in un angolo dello spazio.

Niente cottura live nei test.

## 9. File previsti (implementazione futura)

| File | Ruolo |
|---|---|
| `learn/dse/tune_space.py` | dimensioni, clamp, omit-default, fingerprint, pin die |
| `learn/dse/tune_score.py` | vincoli + score da `win_rule` / `_imp` |
| `learn/dse/cook.py` | `cook_one` condiviso |
| `learn/scripts/cook_recipe.py` | CLI `--recipes` / `--knobs` |
| `learn/scripts/run_tpe.py` | Optuna ask/tell, warm-start, enqueue |
| `learn/scripts/run_recipe_loop.py` | decisione `tune`, flag `--deepen` |
| `learn/requirements-tune.txt` | `optuna` pinnato |
| `learn/scripts/test_dse_next.py` | assert spazio/score/pin/coordinatore |

Niente Ray, niente JSON AutoTuner, niente secondo jsonl.

## 10. Cosa può andare storto (e la risposta già scelta)

- **Pochi finish → TPE ≈ random.** Per questo il warm-start è obbligatorio
  e il primo live è gcd, non aes.
- **Score che insegue un asse e brucia slack.** I lose sono vincoli, non
  penalità morbide.
- **STOP contato come lose IR.** Vietato; vedi §2.
- **Cucinare 4 trial TPE precomputati.** Vietato; ask/tell seriale.
- **Passare `HOLD=0` e cambiare il default.** Omit, §3.
- **Variant `camp_gcd_tpe_17` che collide col phase.** Hash del vettore,
  §4.
- **Tune su spi.** Slot non ammissibile, §6.
- **Die che si muove comunque (hier, util residua).** Pin box +
  `wrong_die`; se succede è un bug del pin, si ferma il tuner.
- **Volere NSGA/GNN/white-box al primo no-win.** Fuori v1. Si misura
  prima se TPE batte OFAT sullo stesso forno.

## 11. Criterio di successo della fase (frozen)

TPE è un successo di **metodo** se, a parità di forno e die:

1. Lo spazio e lo score sono testati senza ORFS e non possono campionare
   il floorplan.
2. Un giro gcd (≤8 finish nuovi) è registrato nel jsonl con
   `extra.tuner=tpe`.
3. Il verdetto prodotto resta `win_rule` (non lo score TPE).
4. Si può dire onestamente se TPE ha trovato un win **nuovo** rispetto
   alle ricette univariate già cotte, oppure no.

Se (4) è no, non si “aggiunge un GNN”. Si dichiara che, su gcd, il
continuo non ha battuto OFAT con quel budget.

## 12. Tagli di implementazione (non tempi)

1. `tune_space` + `tune_score` + test finti. Zero cotture.
2. Estrarre `cook_one`; `cook_recipe --knobs` rifiuta floorplan e pinna
   il die. Test CLI refuse / fingerprint skip, ancora senza TPE.
3. `run_tpe.py` + warm-start + ask/tell con fake eval, poi gcd live ≤8.
4. `coordinate()`: default `tune` al posto di `deepen`; `--deepen`
   resta. Dry-run. Aggiornare `product.md` ciclo (già puntato da qui).

Il passo 1–2 non richiede Optuna installato in CI se i test di score
restano in `test_dse_next.py`.
