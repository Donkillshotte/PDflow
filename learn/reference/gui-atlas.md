# Atlante GUI OpenROAD — guida pixel-level (Qt 26Q2)

Queste non sono icone inventate: ogni PNG in `gui-shots/` è una **cattura reale** della GUI Qt di OpenROAD (`26Q2-1164-g08f67ee5ec`) sul design tutorial `nangate45/gcd` variante `learn`, oppure un `save_image` del canvas dallo stesso ODB.

**Come aprire la GUI:** pulsante **Desktop** su [cursor.com/agents](https://cursor.com/agents) (non Preview chat). Poi:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_final
```

Titolo atteso: `OpenROAD - gcd` (o `OpenROAD - nangate45/gcd/learn - 6_final`).

Riferimento menu/pannelli in prosa: [gui-openroad.md](./gui-openroad.md). Questo atlante è la **mappa visiva**.

**FlowLab / lezioni (browser):** su `/flusso` e nello step **Risultati** del wizard, il canvas centrale mostra gli stessi layout via ORFS PNG + **OpenROAD Web Viewer** embedded (`POST /api/viewer`). Non serve aprire Qt per una prima ispezione — usa Desktop per analisi pixel-level come in questo atlante.

---

## 1. Anatomia della finestra (impara questi 7 rettangoli)

Finestra di riferimento: **1680×1000** pixel (massimizza la tua a una dimensione simile).

![Anatomia etichettata](./gui-shots/win_anatomy_labeled.png)

| Zona | Dove cliccare (1680×1000) | Cosa fa |
|---|---|---|
| **A Menu** | `y ≈ 8–24`, `File` a `x≈30`, `View` a `x≈80`, `Tools` a `x≈150` | File→Load ODB, View→fit/heatmap, Tools→ruler |
| **B Toolbar** | `y ≈ 32–52`: **Fit** `x≈40`, **Find** `x≈95`, **Inspect** `x≈155`, **Timing** `x≈230` | Scorciatoie; Fit ≡ tasto `F` ≡ `gui::fit` |
| **C Display Control** | colonna sinistra `x=0–268`, `y=56–760` | Occhio = visibile; cursore = selezionabile |
| **D Canvas** | `x=268–1390`, `y=56–760` | Layout; rotella zoom, tasto medio pan, click seleziona |
| **E Inspector** | colonna destra `x=1390–1680` | Proprietà dell'oggetto selezionato |
| **F Console** | `y≈760–972` | Log + campo **TCL commands** in basso |
| **G Status** | ultima riga `Idle` | Se non è Idle, aspetta prima di cliccare |

**Esercizio 90 secondi:** apri `gui_final`, identifica A–G **senza** rileggere la tabella. Poi confronta con lo screenshot.

![Finestra intera su 6_final.odb](./gui-shots/win_anatomy.png)

---

## 2. Display Control — colori layer Nangate45

Ritaglio del pannello sinistro sulla stessa sessione:

![Display Control](./gui-shots/win_display_control_crop.png)

Nella build 26Q2 i **swatch** (quadratini colore) coincidono con il canvas:

| Layer | Colore in GUI | Cosa rappresenta di solito su GCD |
|---|---|---|
| `metal1` | blu | rail VDD/VSS sulle **rows** (followpin) + pin locali |
| `metal2` | rosso | routing segnale orizzontale/verticale |
| `metal3` | verde | routing segnale (direzione opposta a M2) |
| `metal4` | giallo/verde chiaro | strap PDN verticali (griglia M1–M4–M7) |
| `metal5` | magenta/rosa | strap PDN orizzontali |
| `via1`… | viola/vari | tagli tra metal adiacenti |

Due checkbox per riga:

1. **Occhio** — visibile nel canvas
2. **Puntatore** — cliccabile/selezionabile

### Click path: spegni tutto, riaccendi solo M2+M3

1. In **C**, scorri la lista `Layers`.
2. Togli l'occhio a `metal1`, `metal4`–`metal10` e alle via che non ti servono.
3. Lascia `metal2` (rosso) e `metal3` (verde) accesi.
4. Toolbar **Fit** (o `F`).

Equivalente Tcl (incolla nel campo **TCL commands**, Invio dopo ogni riga):

```tcl
gui::set_display_controls "Layers/*" visible true
gui::set_display_controls "Layers/metal1" visible false
gui::set_display_controls "Layers/metal4" visible false
gui::set_display_controls "Layers/metal5" visible false
gui::fit
```

Risultato atteso (wire rossi + verdi, PDN rosa/verde spento):

![Solo metal2 e metal3](./gui-shots/win_layers_m2m3.png)

Nella console in basso vedi esattamente i `gui::set_display_controls` eseguiti: è il modo giusto di **documentare** una vista nel quaderno.

### Nets vs Layers

- **Layers** = geometria (tutto il metal, power incluso).
- **Nets/Signal** e **Nets/Clock** = quali *net* evidenziare/filtrare.

Nascondere `Nets/Signal` **non** cancella i fili se i layer restano accesi: i wire *sono* geometria di layer. Per isolare il clock: seleziona la net (sezione 4) oppure spegni i layer e usa Highlight.

Tentativo filtro clock (layer ancora ON → il canvas resta pieno; la console conferma i comandi):

![Filtro Nets/Clock con layer ancora visibili](./gui-shots/win_clock_filter.png)

**Lezione:** se vuoi “solo clock”, combina `select -name "clk" -type Net` (highlight giallo) *oppure* spegni i metal di segnale.

---

## 3. Console Tcl — dove scrivere, cosa funziona

Il campo è la riga bianca in **F**, etichetta **TCL commands**, circa `x=80–900`, `y ≈ H−50` (su 1000px: `y≈950`).

Click nella riga → digita → **Invio**. Lo storico compare sopra.

Comandi verificati su questa GUI:

| Comando | Effetto visivo |
|---|---|
| `gui::fit` | il die riempie **D** |
| `select -name "clk" -type Net` | net clock evidenziata; Inspector si popola |
| `select -name "clkbuf*" -type Inst` | buffer CTS |
| `gui::clear_selections` | toglie highlight |
| `gui::set_display_controls "Layers/metal2" visible false` | spegne M2 |

**Non** usare (errore visto in sessione):

```tcl
report_checks -path_delay max -max_paths 3
```

OpenSTA in questa build risponde `sta_error 563 ... is not a known keyword`. Usa invece:

```tcl
report_checks -max_paths 3
```

Screenshot dell'errore (così lo riconosci):

![Comando STA sbagliato in console](./gui-shots/win_report_checks.png)

---

## 4. Inspector — ispezionare la net `clk`

Dopo `select -name "clk" -type Net` il pannello **E** mostra proprietà reali del GCD post-route:

![Inspector sulla net clk](./gui-shots/win_inspector_tab.png)

Cosa **devi** saper leggere (valori tipici sul GCD `learn`):

| Campo Inspector | Valore atteso | Perché conta |
|---|---|---|
| Type | `Net` | non hai cliccato una cella |
| Name | `clk` | porta clock del modulo |
| Signal type | `CLOCK` | CTS ha classificato la net |
| Wire type | `ROUTED` | il detailed route è passato |
| Non-default rule | `CTS_NDR_0` | clock con regola più larga/spazio |
| ITerm | `clkbuf_0_clk/A` | primo buffer dell'albero |
| BTerm | `clk` | pin sul bordo del blocco |
| BBox | ~`(4.5, 0) … (19.8, 23.5)` µm | estensione fisica del clock |

Se Inspector è vuoto: non c'è selezione, oppure sei sul tab **Help Browser**. Click tab **Inspector** in basso a destra del pannello E (sopra la console).

Toolbar **Inspect** dopo una selezione forza il tab Inspector.

---

## 5. Galleria per fase (stessa GUI, ODB diversi)

Ogni riga: **finestra Qt** + (dove esiste) **canvas `save_image`**. Apri i `gui_*` nello stesso ordine.

### 5.1 Synthesis — `1_synth.odb`

Canvas **nero**. Die 0×0: le celle esistono nel DB ma **non hanno coordinate**. `save_image` headless spesso non scrive il PNG. È normale, non è un crash.

![GUI su 1_synth.odb: canvas vuoto](./gui-shots/win_synth.png)

Comando:

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_1_synth.odb
```

Esercizio: **Find** → cerca `DFF_X1` → Inspect. Master name visibile, posizione (0,0) o assente.

### 5.2 Floorplan — `2_1_floorplan.odb`

Due rettangoli concentrici: **die** (esterno) e **core** (interno). Niente celle, niente PDN.

![GUI floorplan: solo die/core](./gui-shots/win_floorplan.png)

Nota: `gui::set_display_controls "Rows" visible true` fallisce con **`[ERROR GUI-0013]`** — in questa GUI non esiste un controllo chiamato esattamente `Rows`. Cerca nel tree Display Control un nodo simile (spesso sotto gruppi fisici) oppure guarda le righe blu **dopo** il PDN.

### 5.3 Tapcell — `2_3_floorplan_tapcell.odb`

Prime geometrie di celle fisiche (well tap) sulle rows.

![Tapcell](./gui-shots/win_tapcell.png)

### 5.4 PDN — `2_4_floorplan_pdn.odb`

Prima vista “da chip”: rail M1 + strap.

![GUI PDN](./gui-shots/win_pdn.png)

Canvas ad alta risoluzione (stesso ODB, solo layout):

![PDN annotato](./gui-shots/03_pdn_labeled.png)

Checklist visiva:

- [ ] bordo die
- [ ] linee blu fitte = followpin M1
- [ ] 3 strap verdi verticali
- [ ] 3 strap rosa orizzontali
- [ ] **zero** rettangoli di logica (ancora)

Tcl:

```tcl
gui::set_display_controls "Nets/Signal" visible false
gui::set_display_controls "Nets/Power" visible true
gui::set_display_controls "Nets/Ground" visible true
gui::fit
```

### 5.5 Global placement — `3_3_place_gp.odb`

Celle sparse (blob), pin I/O a triangolo sul bordo, PDN ancora sotto.

![GUI global place](./gui-shots/win_place_gp.png)

![Canvas GP annotato](./gui-shots/04_place_gp_labeled.png)

I triangoli **ciano** (alto/basso) e **rossi** (sinistra/destra) sono i **BTerm**.

### 5.6 Detailed placement — `3_5_place_dp.odb`

Stesso contenuto “legalizzato” sulle rows: i rettangoli allineati alle piastrelle, overlap sparito.

![GUI detailed place](./gui-shots/win_place_dp.png)

Apri **nello stesso desktop** GP e DP (due finestre, o File→Load in sequenza) e annota *una* differenza nel quaderno. Canvas DP:

![Canvas DP](./gui-shots/05_place_dp.png)

### 5.7 CTS — `4_cts.odb`

Più celle (`CLKBUF*`). Filtra clock come in sezione 2. Canvas:

![Canvas CTS](./gui-shots/06_cts.png)

![GUI CTS](./gui-shots/win_cts.png)

```tcl
select -name "clkbuf*" -type Inst
```

View → **Clock Tree Viewer** se il menu è visibile; altrimenti resta sulla net `clk` evidenziata.

### 5.8 Global route — `5_1_grt.odb`

Guide (corridoi), non ancora wire mask-ready.

![GUI GRT](./gui-shots/win_grt.png)

![Canvas GRT](./gui-shots/07_grt.png)

### 5.9 Detailed route — `5_2_route.odb`

Spaghetti colorati = geometria DRT. Confronto con GRT: qui i fili sono fini e sui colori M2/M3.

![GUI route](./gui-shots/win_route.png)

![Canvas route annotato](./gui-shots/08_route_labeled.png)

Esercizio: spegni tutti i layer tranne `metal2`, Fit, conta a occhio la direzione dominante dei fili. Poi solo `metal3`.

### 5.10 Finish — `6_final.odb`

Fill + SPEF già estratti. Stessa “fotografia” densa del route, più dummy fill.

![GUI final](./gui-shots/win_final.png)

![Canvas final](./gui-shots/09_final.png)

KLayout (GDS, non Qt OpenROAD):

```bash
klayout results/nangate45/gcd/learn/6_final.gds
```

Tasto **F** = fit. Pannello Layers a destra: accendi/spegni metal come in Display Control.

---

## 6. Sessione guidata di 45 minuti (obbligatoria prima della lezione 04)

Cronometra. Per ogni step: 1 screenshot mentale + 1 riga nel quaderno.

| Min | ODB | Azione pixel | Scrivi nel quaderno |
|---|---|---|---|
| 0–5 | `1_synth` | constata canvas nero | “no die” |
| 5–10 | `2_1_floorplan` | identifica i due rettangoli | die vs core |
| 10–18 | `2_4_pdn` | spegni metal2–3, resta M1+strap | colori rail/strap |
| 18–26 | `3_3` vs `3_5` | Fit su entrambi | GP blob vs DP allineato |
| 26–32 | `4_cts` | `select clk` + Inspector | Signal type CLOCK |
| 32–40 | `5_1` vs `5_2` | solo M2 poi solo M3 su route | guida vs wire |
| 40–45 | `6_final` | Find `FILLCELL` se presente | fill ≠ logica |

---

## 7. Scorciatoie da memorizzare

| Tasto / click | Azione |
|---|---|
| `F` / toolbar **Fit** | inquadra il die |
| rotella | zoom sul puntatore |
| tasto medio / Space+drag | pan |
| click su cella o filo | selezione → Inspector |
| campo TCL in basso | comandi `gui::` e `select` |
| occhio in Display Control | hide/show layer |

---

## 8. Heatmap e Clock Tree Viewer (immagini ORFS `save_images`)

Oltre alla finestra Qt, ORFS 26Q2 in `make finish` scrive PNG in `reports/nangate45/gcd/learn/*.webp.png`. Copie didattiche in `gui-shots/orfs_*.png`.

### Clock tree (`orfs_cts_clock_tree.png`)

È il **Clock Tree Viewer**: asse Y = tempo (ns), triangoli = buffer, quadratini = sink FF.

Sul GCD `learn`: root → un buffer → fanout ~4 → foglie intorno a **0.07 ns**. Foglie allineate = skew piccolo (report setup skew ~0).

Usa questo PNG se View → Clock Tree Viewer non si apre dal menu.

### Worst path (`orfs_final_worst_path.png`)

Overlay sul die: **launch** ciano, **signal** rosso, **inst** viola. È View → Show Worst Path / Timing, già calcolato a signoff.

### Congestion (`orfs_final_congestion.png`)

Griglia gcell: verde = aria, rosso = pieno. Centro caldo, bordi freddi: stesso blob del placement.

### IR drop (`orfs_final_ir_drop.png`)

Scala **mV** (sul GCD ~0–5 mV). Se fosse centinaia di mV, la PDN della lezione 03 non basta.

Queste quattro immagini chiudono la sessione 45 min: dopo `gui_final`, confronta i PNG ORFS con ciò che vedi nel canvas.

---

## 9. Catturare di nuovo gli screenshot (maintainer)

```bash
# Canvas save_image (headless): 03–09. Synth/floorplan possono fallire (die 0 / GUI-0078).
./learn/scripts/capture_gui_shots.sh

# Finestra Qt reale (serve DISPLAY=:1 e un desktop):
python3 ./learn/scripts/capture_qt_gallery.py
python3 ./learn/scripts/annotate_gui_shots.py
# Heatmap/clock: copiare reports/nangate45/gcd/learn/*.webp.png → gui-shots/orfs_*.png
```

Non cancellare i PNG con glob `*_pdn.png`: cancellerebbe anche `03_pdn.png`.
