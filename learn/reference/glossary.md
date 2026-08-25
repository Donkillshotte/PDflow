# Glossario Physical Design — OpenROAD / ORFS

Riferimento alfabetico. Torna qui durante ogni lezione.

---

## A

**ABC** — Tool di synthesis/logic optimization usato da Yosys internamente.

**Area (core)** — Superficie rettangolare dove possono essere piazzate le celle standard.

**Artefatto** — File prodotto da una fase (`.odb`, `.def`, `.gds`, `.v`, `.sdc`, `.spef`).

---

## C

**Cell** — Istanza di una master cell della libreria (es. `AND2_X1`, `DFF_X1`).

**Clock domain** — Insieme di registri clockati dallo stesso clock.

**Congestion** — Troppa domanda di routing in una regione del chip.

**Constraints (SDC)** — Regole temporali: clock, I/O delay, false path, multicycle.

**Core utilization** — Percentuale del die occupata dal core logico (parametro floorplan).

**CTS (Clock Tree Synthesis)** — Costruzione albero di clock bilanciato verso tutti i FF.

---

## D

**DEF (Design Exchange Format)** — Descrizione testuale di placement + routing + componenti.

**Detailed placement (DP)** — Legalizzazione: ogni cella su un site valido, senza overlap.

**Detailed routing (DRT)** — Routing finale rispettando width/spacing/via rules.

**DRC (Design Rule Check)** — Verifica geometrica (spacing, width, enclosure).

**DFF / Flip-flop** — Elemento di memoria sincrono; endpoint tipico di timing path.

---

## F

**False path** — Percorso che STA deve ignorare (non critico temporalmente).

**Floorplan** — Definizione die, core, rows, power grid, pin IO.

**Flow variant** — Sottocartella risultati ORFS (`base`, `learn`, …).

---

## G

**GDSII** — Formato binario layout per mask shop / fab.

**Global placement (GP)** — Posizionamento approssimato minimizzando wirelength + density.

**Global routing (GRT)** — Assegnazione guide di routing per regioni; non wire finali.

**Gate-level netlist** — Verilog con celle della libreria (post-synthesis).

---

## H

**Hold time** — Tempo minimo che dati devono restare stabili dopo clock edge.

**Heatmap (GUI)** — Visualizzazione colori di density, congestion, IR drop.

---

## I

**IO delay** — Budget temporale tra pad/pin del mondo esterno e registri.

**IR drop** — Caduta di tensione sulla power grid (finish stage).

---

## L

**LEF (Library Exchange Format)** — Geometria fisica di tech + celle (layers, pins, sites).

**LIB (Liberty)** — Timing/power model delle celle (.lib).

**Legalization** — Spostare celle su sites validi senza violare row alignment.

---

## M

**Master cell** — Definizione di una cella in LEF (template).

**Multicycle path** — Percorso che può usare più cicli clock.

---

## O

**ODB (OpenDB)** — Database binario OpenROAD; snapshot di ogni fase.

**OpenSTA** — Static Timing Analyzer (parte di OpenROAD e standalone).

---

## P

**PDK (Process Design Kit)** — Pacchetto tech: LEF, LIB, regole (Nangate45, sky130, …).

**PDN (Power Distribution Network)** — Mesh/straps VDD/VSS nel core.

**Placement** — Assegnazione posizione (x,y) a ogni cella.

**Parasitics (SPEF)** — R/C estratti dal layout per STA post-route.

---

## R

**Resizer (RSZ)** — Tool OpenROAD che inserisce buffer, upsize, clone per timing.

**RTL** — Register Transfer Level; Verilog comportamentale pre-synthesis.

**Row** — Fila di sites dove allineare celle standard.

---

## S

**SDC** — Synopsys Design Constraints (file `.sdc`).

**Setup time** — Tempo richiesto per dati stabili prima del clock edge.

**Site** — Slot fisico minimo per una cella (es. `FreePDK45_38x28_...`).

**Skew** — Differenza di arrivo clock tra sink diversi.

**SPEF** — Standard Parasitic Exchange Format.

**STA** — Static Timing Analysis: verifica setup/hold senza simulazione.

**Synthesis** — RTL → gate-level netlist mappato alla libreria.

---

## T

**Tapcell** — Celle per well tie/substrate connection.

**Timing closure** — Raggiungere WNS ≥ 0 e TNS ≈ 0 su tutti i corner.

**TNS (Total Negative Slack)** — Somma di tutti i setup violation.

**Top module** — Radice gerarchia Verilog (`gcd` nel nostro corso).

---

## W

**WNS (Worst Negative Slack)** — Peggiore violazione setup (la più critica).

**Wirelength** — Lunghezza totale interconnessioni (obiettivo placement/routing).

---

## Acronimi del flusso ORFS

```
RTL → yosys → 1_synth.odb
     → floorplan → 2_floorplan.odb
     → place → 3_place.odb
     → cts → 4_cts.odb
     → route → 5_route.odb
     → finish → 6_final.gds
```

---

## Domande da farsi in ogni fase

| Fase | Domanda |
|---|---|
| Synth | Quante celle? Ci sono latch? |
| Floorplan | Core abbastanza grande per utilization target? |
| Place | Overflow zero? Quanti buffer ha aggiunto RSZ? |
| CTS | Skew accettabile? Area post-CTS < 100%? |
| Route | DRC clean? Congestion residua? |
| Finish | WNS/TNS post-SPEF? GDS apre in KLayout? |
