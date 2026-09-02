# Revisione architettura dopo TPE v1 (gcd, ibex, aes)

Solo analisi e piano. Le scelte in §4–§6 sono pre-registrate e non si
ritoccano dopo i dati.

Stato: §4.1–§4.3 implementati (`tune_transfer.py`, ricetta
`place_sparse_setup`). §4.4 (ordine slot cost-aware) resta fuori.

Vincoli fermi che questa revisione NON tocca: die fisso, finish veri,
un job pesante, win rule invariata (`win_rule.py`), niente proposer
nuovi (LLM/RL/GNN/e-graph) e niente surrogato bayesiano del finish
(`next_iteration_plan.md` §7). Il gate lineare per-design (I2) resta
l'unico modello ammesso, ed è già la policy.

## 1. Cosa dicono i numeri (registro a questa data)

Cotture di prodotto (`role=knob`) contro il base P0 dello slot:

| Slot | Base | OFAT/deepen | TPE | Min/finish |
|---|---|---|---|---|
| gcd | −37 ps | 17 cook, 3 win | 8 cook, **0 win** (2 tie, 3 lose, 3 fail) | 0.9 |
| spi | +612 ps | 14 cook, 0 win (10 tie) | non ammissibile | 0.6 |
| ibex | +22 ps | 10 cook, 4 win | 8 cook, **6 win** (2 fail) | 7.1 |
| aes | −8.9 ps | 8 cook, 3 win | 8 cook, **5 win** (1 lose, 2 STOP) | 7.6 |
| dynamic_node | +3354 ps | 11 cook, 1 win | non ancora lanciato | 4.5 |

Nota onesta: le 8 righe TPE aes hanno `runtime_s=0` perché restampate
dai log su disco dopo il fix `FLOORPLAN_DEF`; il costo vero è ~50 min.

Fatti che contano:

1. **Il muro pad=2 è stato pagato 5 volte** (3 gcd, 2 ibex), 4 delle
   quali dopo la prima prova fallita. Nessun finish con pad 2 è mai
   arrivato in fondo, su nessun design.
2. **I meccanismi trasferiscono parzialmente.** Su ≥2 design:
   `sparse+setup` vince su aes+ibex e non perde da nessuna parte;
   `setup` vince su aes+ibex (perde su gcd); `cts_fitti` vince su
   aes+dynamic_node; `pad1` vince su gcd+ibex (perde su aes+dn).
   `synth_hier` non ha mai vinto su 5 design. `aspect/core_*` è sempre
   `wrong_die`.
3. **GPL_TIMING_DRIVEN=0 dipende dal design**: su ibex 2 win (IR −38%),
   su aes 2 STOP al place, su spi lose. Non è un muro: è un asse da
   campionare, e TPE lo ha fatto.
4. **TPE vince dove lo slot è aperto** (ibex: IR da combinare; aes:
   timing da chiudere) e non vince dove il base è già stretto (gcd).
   Non è il sampler: su gcd i miss migliori erano vincoli (IR −19% con
   slack −7.4 ps), non proposte cieche.
5. **I 2 win immediati su aes (trial 1–2) erano combo enqueue** dal
   deepen dello slot. L'informazione OFAT trasferita in TPE paga al
   primo colpo.
6. **Il gate policy ha funzionato dove può funzionare**: 2 STOP giusti
   su aes (place WNS −0.78/−0.47 ns). Ma i fail pad=2 su gcd passavano
   il gate del place (WNS positivo) e morivano al finish: il gate WNS
   non vede i muri di dettaglio/route.
7. **dynamic_node è ammissibile al tune con coda vuota**: 1 solo win
   (`cts_closer_bufs`), zero combo deepen da enqueue-are. TPE partirebbe
   quasi freddo proprio dove il transfer avrebbe più da dire.

## 2. Punti deboli dell'architettura attuale

1. **Il warm-start è cieco fuori dallo slot** (`slot_rows` filtra per
   design). Muri e meccanismi vincenti non passano da un design
   all'altro: ibex ha ripagato il muro pad=2 che gcd aveva già pagato.
2. **Nessuna promozione**: un win TPE resta un hash
   (`camp_aes_tpe_2fcef4b2e86a`), non diventa una ricetta di catalogo
   con titolo umano che il cover del prossimo design prova per prima.
3. **L'ordine degli slot è cheap-first puro**: non guarda quanto è
   aperto lo slot né il costo reale del finish (0.6–7.6 min). gcd era
   economico ma senza headroom; 8 trial spesi lì valevano ~7 min, ma la
   stessa informazione (0 win) era leggibile dopo 3–4.
4. **Il gate vede solo il WNS del place**: i crash a valle (DPL/route
   con pad=2) non sono predetti né memorizzati come muro.
5. **Il tuner non distingue** "fallito per muro noto" da "fallito per
   caso": un fingerprint fallito è solo un trial infattibile locale.

## 3. Tecniche valutate contro i vincoli fermi

| Tecnica | Scope | Perché |
|---|---|---|
| Transfer tra design (muri + prior d'ordine) | **SÌ, primo** | Evidenza diretta: pad=2 ripagato, matrice meccanismi, aes trial 1–2. Zero dipendenze nuove. |
| Promozione win → catalogo | **SÌ** | Il prodotto sono ricette. `sparse+setup` è già un candidato ≥2 design senza lose. |
| Ordine slot cost-aware | **SÌ, piccolo** | Win atteso per minuto: dynamic_node (4.5 min, slot aperto) prima di ritorni su gcd. |
| Multi-fidelity bayesiano (BOHB/Hyperband) | NO ora | Vietato da §7 con questi numeri. Il gate lineare I2 è già il multi-fidelity povero e ha funzionato (2 STOP giusti). |
| Cambiare sampler (MOTPE/NSGA-II/CMA-ES) | NO | Il sampler non è stato il collo di bottiglia in nessuno slot. gcd è fallito per headroom e muri, non per proposta. |
| Surrogato del finish (GP/GNN) | NO | Congelato §7: sottodeterminato (max ~34 finish per design). Ridiscutere solo sopra ~40 finish per-design. |
| LLM/RL proposer, white-box OpenROAD | NO | Laboratorio, congelato. |
| Nuovi assi nello spazio (routability, densità target) | Dopo | Prima si consuma l'informazione già pagata; v2 dello spazio solo dopo aver misurato il transfer. |

## 4. Proposta (ordine di priorità, pre-registrato)

1. **Memoria dei muri** (`tune_transfer.py`, nuovo, senza Optuna).
   Dal registro globale: un meccanismo con ≥2 fail/never-win su ≥2
   design (oggi: `cell_pad=2`, `synth_hier`) diventa muro. Il tuner lo
   importa come trial infattibile e non lo ripropone; `enqueue` lo
   salta. Test senza ORFS: su un replay del live ibex, i trial 5–6
   (pad=2) non si cucinano.
2. **Prior d'ordine cross-design.** Al warm-start, i vettori win di
   altri design (stesso spazio, meccanismo win su ≥2 design) si
   enqueue-ano dopo le combo deepen dello slot, max 3. Non si importano
   gli score assoluti di altri design come trial completati: basi
   diverse, distribuzioni diverse. Si trasferisce solo l'ordine di
   prova.
3. **Promozione a ricetta.** Un meccanismo win su ≥2 design senza lose
   diventa ricetta di catalogo con titolo umano. Primo candidato:
   `sparse+setup` → «Place più sparso + margine di setup». Il cover del
   prossimo slot lo prova come le altre ricette.
4. **Ordine slot cost-aware nel tune.** Tra gli ammissibili, priorità a
   (apertura slot) / (mediana min/finish) invece del cheap-first puro.
   Apertura = base non very-closed, oppure IR/leakage con margine ≥10%
   mai raggiunto. Con i numeri di oggi sceglie dynamic_node.

Cosa resta com'è: spazio v1 (7 assi), score e vincoli da `win_rule`,
`cook_one`, fase T1, fingerprint, budget ≤8 finish per slot, stop su
plateau, spi non ammissibile.

## 5. Cosa NON si fa (e quando ridiscuterlo)

- Niente surrogato del finish sotto ~40 finish per-design.
- Niente sampler nuovo: TPE resta finché non è lui il collo di
  bottiglia dimostrato (uno slot aperto, senza muri, dove TPE non trova
  win che una griglia trova).
- Niente nuovi assi v1. Ampliare lo spazio è v2, dopo il transfer.
- Il Verilog non si riscrive; il floorplan non si muove.

## 6. Criterio di successo (frozen)

Il transfer è un successo di metodo se, sul prossimo slot live
(dynamic_node, ≤8 finish):

1. Zero cotture su muri già noti (pad=2, synth_hier).
2. Almeno un enqueue cross-design tra i primi 3 trial.
3. Primo win (se lo slot ne ha uno) entro 3 cotture, come fece aes
   con le combo enqueue — oppure verdetto onesto che lo slot non ha
   win nello spazio v1.
4. «Place più sparso + margine di setup» esiste nel catalogo con test
   di label, e il cover la propone su un design che non l'ha provata.

Se (3) è no, non si cambia sampler e non si aggiunge un modello: si
dichiara che il transfer d'ordine non basta su quello slot e si misura
il successivo prima di toccare l'architettura.
