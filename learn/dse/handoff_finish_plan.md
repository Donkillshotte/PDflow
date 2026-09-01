# Piano: cottura completa dei winner DSE vs finish standard

Obiettivo: dopo la ricerca DSE, **cucinare il piatto per intero** con le
ricette scelte e confrontarlo col finish ORFS di oggi. Stesso esame,
stesso forno. Non è un nuovo giro di DSE.

Lingua del piano: cosa facciamo, in che ordine, come decidiamo se ha
vinto. I dettagli di file stanno in fondo.

## Perché

Oggi confrontiamo assaggi (DSE) con un piatto servito (`make finish`).
Quella è la domanda sbagliata per “siamo meglio?”. La domanda giusta è:
**stesso flusso completo, solo il netlist cambia**.

## Cosa *non* è questo piano

- Non lanciare `make finish` da dentro il controller DSE a ogni prova.
- Non toccare il finish `flowlab` già su disco (oro 45.298, current-run 6.075).
- Non AES, non Krylov, non restampare l’oro.
- Non cucire in v1 le modifiche “solo su un pezzo” (ABC di cono): non è un
  file che ORFS ingoia da solo.
- Non dichiarare win su mesh di alimentazione diverse.

## Tre cotture, non venti

Una sola cosa cambia: **il netlist in ingresso**. Orologio, utilizzazione,
densità, strategia PDN: **identici** al baseline. Altrimenti stiamo
confrontando il piano del chip, non la ricetta DSE.

| Cottura | Chi | Netlist DSE (id) | Cosa testa |
|---|---|---|---|
| A — baseline | Finish `flowlab` già fatto | Yosys+ABC standard ORFS | Il piatto di oggi. Non si rilancia. |
| B — piccolo | Nuova variant ORFS | `54142494d890` `sub_twos_complement` (~407 µm² mapped, 257 celle) | La forma più piccola. |
| C — veloce | Nuova variant ORFS | `52e0ecacb19b` `orfs_abc_speed` (~619 µm² mapped, 408 celle) | La logica più veloce sulla carta. |

Condensatori sull’alimentazione: **non** sono una quarta cottura di
place/route. Sul baseline è già misurato (6.075 → 4.156 mV, stesso grafo).
Dopo B e C, se i finish nuovi nascono, si può ripetere **solo** quella
misura sui nuovi extract. Fase 2, non bloccante.

## Come si decide se ha vinto

Prima delle cotture, i criteri (stesso file `6_report.json`):

1. **In orario** — WNS e TNS finish. “Meglio” = meno ritardo, o stessi
   tempi con **meno pezzi di riparazione**.
2. **Quanto è grande** — area stdcell finish e conteggio istanze. “Meglio”
   = più piccolo a tempi non peggiori.
3. **Alimentazione** — calo di tensione sullo **stesso tipo** di extract
   (DirectLU, non un’altra rete). Fase 2.
4. **Costo** — quanti buffer di riparazione ha inserito ORFS.

Esito possibile, tutti onesti:

- **Win di prodotto:** B o C batte A su tempi *o* su area a tempi pari.
- **Pareggio:** ORFS reinserisce gli stessi buffer, i tre piatti si
  assomigliano. La ricerca era utile, il piatto no.
- **Regressione:** B o C peggiora i tempi o l’area. Si tiene A.

GCD è piccolo: i delta possono essere minimi. Un pareggio **non** è un
fallimento del piano, è una risposta.

## Fasi

### 0 — Freeze del baseline

Copiare da parte (non nel tree `flowlab/` vivo) i numeri A:
WNS, TNS, area, conteggio repair, potenza, util, IR DirectLU.

Non rilanciare A. Non sovrascrivere `results/.../gcd/flowlab/`.

### 1 — Scegliere i file, non i slogan

Verificare su disco che i due `.v` DSE esistano, siano `module gcd`,
passino un equiv rapido vs RTL (B) / vs flatten (C se ha senso).

Se un file manca (netlist è gitignorato): **rigenerare solo quel F1**,
non una campagna.

### 2 — Forno isolato

Nuove `FLOW_VARIANT` ORFS, es. `flowlab_dse_small` e `flowlab_dse_fast`.
Log/results separati da `flowlab`.

Trucco: saltare Yosys. Il netlist DSE **è già** gate-level. Si piazza
come `1_2_yosys.v` (o equivalente ORFS) e si parte da floorplan.
Stesso `constraint.sdc`, stesso `CORE_UTILIZATION` del baseline
(finish vivo ≈ 55%, non il 35% delle prove DSE GPL).

Un job pesante alla volta. Tetto memoria come il resto della VM.

### 3 — Cottura B, poi C

Seriali. Per ognuna: `make finish` → stesso `6_report.json`.

Se una cottura crasha (legalize, antenna, DRT): si registra il fallimento.
Non si “aggiusta la ricetta” in silenzio: quello sarebbe di nuovo DSE.

### 4 — Tabella unica

Stesse colonne per A, B, C:

- WNS / TNS setup
- area stdcell e n. istanze
- n. buffer di riparazione e clock buffer
- potenza / leakage
- util
- (fase 2) IR DirectLU sullo extract di *quel* finish

Niente mapped 407 vs finish 940. Niente F5-lite vs finish.

### 5 — Decisione e stop

Scrivere tre righe: ha vinto B, C, nessuno, o A resta il piatto.
Solo allora si discute se vale la pena cucire i coni ABC o mettere
il handoff nel controller.

## Fuori da v1 (esplicito)

| Richiesta | Perché dopo |
|---|---|
| ABC solo sul percorso dati (`boils_balance`) | Va ricucito nel chip; non è un drop-in. |
| Cell size-up / net buffer DSE | ORFS repair lo rifà; confonderebbe il segnale. |
| Catalog IR 1.705 / leftover 3.94 | Altra rete. |
| AES | Fuori tetto VM; non è questo confronto. |
| `make finish` nel loop DSE | Costa e rimescola le categorie. |

## Ordine di lavoro (quando si implementa)

1. Script/variant isolata + test secco: “questo `.v` entra in floorplan”. **fatto**
2. Finish B. **fatto** (`flowlab_dse_small`, WNS −338 ps)
3. Finish C. **fatto** (`flowlab_dse_fast`, WNS −187 ps)
4. Tabella e verdetto nel write-up accanto a `flow_vs_orfs_gcd.md`. **fatto**
   (`handoff_finish_bakeoff.md`: A resta)
5. Fase 2 IR solo se B/C sono nati. **saltata** (die diversi; PSM ≠ DirectLU)

Niente codice nel controller: il verdetto GCD non giustifica il loop.

