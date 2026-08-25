# Workbook — esercizi con consegna e soluzioni

Quaderno di lavoro del corso. **Non guardare le soluzioni** finché non hai provato.

---

## Come usare questo workbook

1. Crea `learn/workbook/mio-quaderno.md` (copia `notes-template.md`)
2. Per ogni esercizio: scrivi ipotesi → esegui → annota risultati
3. Confronta con `solutions/` solo dopo

Tempo consigliato totale workbook: **3–4 ore** aggiuntive alle lezioni.

---

## Capitolo A — Constraints (Lezione 01)

### A1 — Calcolo manuale I/O delay
**Consegna:** con `clk_period=0.46` e `clk_io_pct=0.2`, calcola input e output delay.

<details>
<summary>Soluzione A1</summary>

`0.46 × 0.2 = 0.092 ns` per input e output delay.

</details>

### A2 — Sweep clock period
**Consegna:** esegui tre run (solo fino a `place`) con:
- `constraint_relaxed.sdc` (2.0 ns)
- default (0.46 ns)
- `constraint_tight.sdc` (0.25 ns)

Compila tabella: | SDC | celle post-place | WNS da 3_resizer.rpt | buffer RSZ |

<details>
<summary>Soluzione A2 (metodo)</summary>

```bash
for sdc in constraint_relaxed.sdc constraint.sdc constraint_tight.sdc; do
  cp learn/designs/nangate45/gcd-tutorial/$sdc learn/designs/nangate45/gcd-tutorial/constraint.sdc
  ./scripts/learn_physical_design.sh --auto --lesson 04  # solo place
  rg 'WNS|Buffer|Resize' tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt | head
done
```

Osservazione attesa: clock più stretto → più buffer/upsize → più celle.

</details>

### A3 — Domanda riflessiva
**Consegna:** in 5 righe, spiega perché SDC e floorplan utilization sono accoppiati.

<details>
<summary>Soluzione A3 (outline)</summary>

Clock stretto → resizer aggiunge buffer → area celle cresce → stesso core → utilization effettiva sale → CTS/legalize fallisce se >100%.

</details>

---

## Capitolo B — Floorplan (Lezione 03)

### B1 — Misura core area
**Consegna:** da `2_1_floorplan.log`, estrai Core area per util 30 e 50.

<details>
<summary>Soluzione B1</summary>

```bash
rg 'Core area' tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/2_1_floorplan.log
```

Util più alta → core area più piccola (a parità di cell count post-synth).

</details>

### B2 — Disegno a mano
**Consegna:** disegna su carta die, core, rows, VDD strap. Fotografa o descrivi in notes.

### B3 — GUI scavenger hunt
**Consegna:** in `gui_2_4_floorplan_pdn.odb`, trova e annota:
- [ ] Net VDD
- [ ] Net VSS  
- [ ] Row site name
- [ ] Un tapcell

---

## Capitolo C — Placement (Lezione 04)

### C1 — Global vs Detailed
**Consegna:** confronta `gui-shots/win_place_gp.png` e `win_place_dp.png` (o le due GUI). Elenca 2 differenze visive. Fit su entrambi.

### C2 — Conta buffer resizer
**Consegna:** da `3_resizer.rpt`, quanti buffer/inverter inseriti?

<details>
<summary>Soluzione C2</summary>

Cerca righe `Inserted N buffers` nel log `3_4_place_resized.log` o summary in report.

</details>

---

## Capitolo D — CTS (Lezione 05)

### D1 — Debug intenzionale
**Consegna:** provoca fallimento CTS con util 55 + clock 0.25. Documenta errore DPL-0038.

### D2 — Fix
**Consegna:** stesso scenario, fix con util 30. CTS passa?

---

## Capitolo E — Routing & Finish (Lezioni 06–07)

### E1 — DRC
**Consegna:** `wc -l 5_route_drc.rpt` — zero linee = clean?

### E2 — GDS
**Consegna:** apri GDS in KLayout, conta top cells e layer.

### E3 — Progetto finale
**Consegna:** documento `mio-progetto-finale.md` con:
- Parametri scelti (SDC, util)
- WNS/TNS/area finali
- Screenshot GUI o descrizione
- Cosa faresti diversamente

---

## Griglia valutazione autonoma

| Competenza | Indicatore |
|---|---|
| Novizio | Completa lezioni con `--auto` senza leggere log |
| Intermedio | Completa workbook A1–C2 con tabella dati |
| Avanzato | Debugga CTS fallito senza playbook |
| Espertino | Modifica un `.tcl` ORFS e spiega effetto |
