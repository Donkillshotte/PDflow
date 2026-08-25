# LAB 05 — CTS (sessione da 90–120 minuti)

## Obiettivi misurabili

- Spiegare perché serve un clock tree
- Contare buffer clock pre/post CTS
- Debuggare DPL-0038 senza playbook aperto
- Usare Clock Tree Viewer

---

## Parte 1 — Teoria clock (20 min)

### Problema
Ogni flip-flop ha un pin `CK`. Il clock deve arrivare **quasi simultaneamente** a tutti i sink, altrimenti **skew** → hold/setup violations artificiali.

### Soluzione CTS
Inserisce buffer/inverter in albero bilanciato dal root `clk` ai sink.

### Script ORFS (`cts.tcl`) — blocchi chiave

1. `repair_clock_inverters` — prepara inverted clocks
2. `clock_tree_synthesis` — TritonCTS
3. `detailed_placement` — legalizza dopo inserimento buffer
4. `repair_timing` — fix setup/hold post-CTS

Leggi log mentre esegui: `logs/.../4_1_cts.log`

---

## Parte 2 — Run CTS baseline (15 min)

Prerequisito: `3_place.odb` esiste.

```bash
./scripts/learn_physical_design.sh --lesson 05
```

Se **passa** con util 35 + SDC 0.46 ns → annota skew da `4_cts_final.rpt`.

Se **fallisce** → vai a Parte 4 (debug).

---

## Parte 3 — Ispezione GUI (30 min)

### Conteggio buffer
```bash
# Pre-CTS
make ... gui_3_place.odb
# Filtra istanze: non dovresti vedere molti CLKBUF*

# Post-CTS  
make ... gui_4_cts.odb
# Filtra clock net + CLKBUF*
```

Annota: ~quanti buffer clock in più?

### Clock Tree Viewer
1. View → Clock Tree Viewer
2. Seleziona clock `core_clock`
3. Esplora livelli albero
4. Save screenshot (o descrivi profondità albero)

---

## Parte 4 — Debug intenzionale DPL-0038 (30 min)

**Obiettivo:** provocare e risolvere overflow.

### Provoca
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint_tight.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
export CORE_UTILIZATION=55
make ... clean_synth clean_floorplan clean_place clean_cts
make ... synth floorplan place cts
# → atteso: fallimento
```

Cerca nel log:
```
DPL-0038 Utilization greater than 100%
Instances area: ... Utilization: 100.x%
```

### Ispeziona errore
```bash
make ... gui_4_1_error.odb
```

### Risolvi (scegli una strategia)
**A)** `CORE_UTILIZATION=30`  
**B)** ripristina SDC 0.46 ns  
**C)** entrambi

Documenta in `learn/workbook/mio-quaderno.md` (template esercizio D1/D2).

---

## Parte 5 — Report analysis (15 min)

```bash
cat tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt
```

Cerca:
- Skew
- Latency
- Buffer count
- Sink count

---

## Parte 6 — Domande d'esame

1. Perché CTS fa detailed placement di nuovo?
2. Cosa fa `repair_clock_inverters`?
3. Se rimuovi tutti i buffer clock manualmente, cosa succede al timing?
4. Relazione tra RSZ pre-CTS e area disponibile per CTS?

---

## Criteri "lezione superata"

- [ ] CTS completato almeno una volta con successo
- [ ] Debug DPL-0038 documentato
- [ ] Clock tree visto in GUI
- [ ] 4 domande d'esame risposte per iscritto
