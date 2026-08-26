# Guida GUI OpenROAD — pannelli, menu, Tcl

**Atlante con screenshot reali (obbligatorio):** [gui-atlas.md](./gui-atlas.md)  
PNG in [gui-shots/](./gui-shots/) catturati da OpenROAD Qt 26Q2 sul GCD `learn`.

OpenROAD Qt. Layout finestra dopo `gui_*.odb` (stessi rettangoli etichettati A–G nell’atlante):

```
┌──────────────┬────────────────────────────┬─────────────────┐
│ Display      │                            │ Inspector /     │
│ Control      │      Layout canvas         │ Charts          │
│ (layer tree) │                            │                 │
├──────────────┴────────────────────────────┴─────────────────┤
│ Scripting console (Tcl)                                     │
└─────────────────────────────────────────────────────────────┘
```

**Come aprire:** pulsante **Desktop** su cursor.com/agents (non Preview chat).

**Anche da Studio:** Ctrl+K → «OpenROAD · …», oppure **Apri GUI** sui `.odb`.
Per il **Web Viewer** (browser, senza Qt): Strumenti → **Apri Web Viewer**
(`openroad -web`, vedi [tool-hooks.md](./tool-hooks.md)).

---

## Avvio

```bash
cd /workspace/tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_3_place.odb
```

Titolo atteso: `OpenROAD - nangate45/gcd/learn - 3_place`

Se non vedi la finestra: Alt+Tab, o icona **OpenROAD GCD** sul desktop XFCE.

---

## Pannello Display Control (sinistra)

Albero visibilità. Click sul **occhio** o checkbox:

| Nodo | Quando usarlo |
|---|---|
| Layers / metal1 … metal10 | Routing (lezione 06–07) |
| Layers / via1 … | Via stack |
| Nets / Signal | Interconnessioni logiche |
| Nets / Clock | Solo clock (CTS) |
| Nets / Power, Ground | PDN |
| Instances / StdCells | Celle logiche |
| Instances / Physical / Fill | Fill (finish) |
| Rows | Floorplan (lezione 03) |
| Blockages | Ostacoli placement |
| Heat Maps / Placement Density | Lezione 04 |
| Heat Maps / Routing Congestion | Lezione 06 |
| Heat Maps / IR Drop | Lezione 07 |

**Esercizio standard:** tutto OFF, poi accendi solo Rows → solo Clock → solo metal4.

---

## Canvas (centro)

| Azione | Come |
|---|---|
| Fit all | tasto **F** o View → Fit |
| Zoom | rotella mouse |
| Pan | tasto medio / spazio+drag |
| Seleziona istanza | click |
| Seleziona net | click su wire o Find |
| Misura | Tools → Ruler (se presente) |

**Find:** Edit → Find / `select -name "clk*" -type Inst` nella console.

---

## Inspector (destra)

Dopo click su una cella:
- Master name (`DFF_X1`)
- Coordinate
- Pin list

Dopo click su un layer via: proprietà geometria.

---

## Charts — Endpoint Slack

Dopo load con `GUI_TIMING=1` (default `open.tcl`):
1. Pannello Charts a destra
2. Dropdown **Endpoint Slack**
3. Click su una barra negativa → path evidenziato nel canvas

View → **Show Worst Path** se il menu Timing è visibile.

---

## Clock Tree Viewer (lezione 05)

1. View → **Clock Tree Viewer** (o widget Clock)
2. Lista clock: `core_clock`
3. Click clock → albero
4. `gui::select_clockviewer_clock` dalla console se il menu è nascosto

---

## Console Tcl (basso)

Comandi utili da copiare:

```tcl
report_checks -max_paths 3
report_clock_skew
gui::fit
select -name "CLKBUF*" -type Inst
gui::clear_selections
```

**Non** chiudere OpenROAD con `exit` se stai ancora ispezionando: usa `gui::hide` solo se serve.

---

## Sequenza didattica (una sessione GUI di 45 min)

Segui la tabella cronometrata in [gui-atlas.md](./gui-atlas.md) §6. In sintesi:

1. `gui_1_synth.odb` — canvas nero (PNG `win_synth.png`)
2. `gui_2_1_floorplan.odb` — die/core (`win_floorplan.png`)
3. `gui_2_4_floorplan_pdn.odb` — power (`03_pdn_labeled.png`)
4. `gui_3_3_place_gp.odb` vs `gui_3_5_place_dp.odb`
5. `gui_4_cts.odb` — `select -name "clk" -type Net`
6. `gui_5_1_grt.odb` vs `gui_5_2_route.odb` (isola metal2 / metal3)
7. `gui_final` — Inspector `CTS_NDR_0`

Per ciascuno: 5 minuti, confronto con il PNG dell’atlante, una riga nel quaderno.

---

## KLayout (GDS, lezione 07)

```bash
klayout results/nangate45/gcd/learn/6_final.gds
```

- F: fit
- Pannello Layers: accendi metal
- Se vuoto: File → Load layer properties del PDK se disponibile

---

## Troubleshooting GUI

| Sintomo | Fix |
|---|---|
| Finestra nera | Display Control: Layers ON |
| Nessun timing chart | GUI_TIMING=0; rilancia senza skip liberty |
| Crash save_images | ignora; GDS è indipendente |
| Preview Cursor "non disponibile" | usa Desktop, non Preview |
