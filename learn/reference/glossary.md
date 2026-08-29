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

**DPL-0038** — Detailed placement: utilization > 100% (area celle > area core). Fallimento legale, non “timing un po’ negativo”. LAB 05 parte 4. Non è **RSZ-0062**.

---

## F

**False path** — Percorso che STA deve ignorare (non critico temporalmente).

**Floorplan** — Definizione die, core, rows, power grid, pin IO.

**Flow variant** — Sottocartella risultati ORFS (`base`, `learn`, …).

---

## G

**GUI** — interfaccia Qt di OpenROAD. Non è Preview HTTP. Atlante: `gui-atlas.md`.

**GUI-0013** — Controllo Display Control inesistente. In 26Q2 `gui::set_display_controls "Rows"` fallisce: non esiste un controllo chiamato `Rows`.

**gcell** — Cella della griglia di **global routing**: unità di capacità (quanti fili “ci stanno” in una regione). Heatmap congestion = domanda vs capacità per gcell. PNG `orfs_final_congestion.png`.

**Guide (GRT)** — corridoi 2D per net, non wire mask-ready. File `route.guide`.

**Global placement (GP)** — Posizionamento approssimato minimizzando wirelength + density.

**Global routing (GRT)** — Assegnazione guide di routing per regioni; non wire finali.

**Gate-level netlist** — Verilog con celle della libreria (post-synthesis).

---

## H

**Hold time** — Tempo minimo che dati devono restare stabili dopo clock edge.

**Heatmap (GUI)** — Visualizzazione colori di density, congestion, IR drop.

---

## I

**IFP-0028** — Messaggio Init Floorplan: origine/core **snappati** alla site grid. Non è un errore; allinea il rettangolo alle piastrelle LEF. Nel log `2_1_floorplan.log` vedi `(1.000, 1.000)` → `(1.140, 1.400)` o simile.

**IO delay** — Budget temporale tra pad/pin del mondo esterno e registri.

**IR drop** — Caduta di tensione sulla power grid (finish stage).

**ideal clock** — STA finge latency di rete = 0 (pre-CTS). Dopo CTS il clock è **propagato** (delay dei `CLKBUF*`).

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

## N

**NDR (Non-Default Rule)** — Regola di routing più larga/spazio rispetto al default tech. Su GCD post-CTS/route la net `clk` in Inspector mostra `CTS_NDR_0`: il clock non è più un filo “qualsiasi”.

**ngspice** — Simulatore SPICE open-source per System PDN in Studio (AC + TRAN). Vedi [spice-ngspice-primer.md](./spice-ngspice-primer.md).

---

## O

**ODB (OpenDB)** — Database binario OpenROAD; snapshot di ogni fase.

**OpenRCX** — Estrattore parassiti OpenROAD (`extract_parasitics` + `RCX_RULES`). Produce SPEF a finish. Senza RCX, ORFS ricade su `estimate_parasitics -global_routing`.

**OpenSTA** — Static Timing Analyzer (parte di OpenROAD e standalone).

---

## P

**PDK (Process Design Kit)** — Pacchetto tech: LEF, LIB, regole (Nangate45, sky130, …).

**PDN (Power Distribution Network)** — Mesh/straps VDD/VSS nel core. In Studio: gridcheck (L03) + mesh SPICE post-finish ([spice-chip-mesh.md](./spice-chip-mesh.md)).

**PDNSim** — OpenROAD `analyze_power_grid`: IR statico on-die; esporta `write_pg_spice`.

**Power chain** — Sequenza Studio: `activity_power` → `chip_pdn_ir` → `system_pdn` → export (`run_power_chain.sh`). Guida: [spice-power-chain.md](./spice-power-chain.md).

**period_min** — Periodo minimo (ns) per cui lo STA, con *quel* modello RC, non vede WNS negativo. fmax ≈ `1000 / period_min` MHz. A finish sul run d’oro è **0.50 ns** (~2011 MHz) vs SDC **0.46 ns** (~2174 MHz): target non chiuso.

**Placement** — Assegnazione posizione (x,y) a ogni cella.

**Parasitics (SPEF)** — R/C estratti dal layout per STA post-route.

---

## R

**Resizer (RSZ)** — Tool OpenROAD che inserisce buffer, upsize, clone per timing.

**RSZ-0062** — Warning: il resizer **non** ha riparato tutte le setup. Sul GCD `learn` compare al CTS (`Inserted 45`) e il flow **continua**. Non è overflow di area: quello è **DPL-0038**.

**RTL** — Register Transfer Level; Verilog comportamentale pre-synthesis.

**Row** — Fila di sites dove allineare celle standard.

---

## S

**SDC** — Synopsys Design Constraints (file `.sdc`).

**Setup time** — Tempo richiesto per dati stabili prima del clock edge.

**SPICE** — Simulazione circuitale. In Studio: (1) mesh resistiva chip da `write_pg_spice`; (2) ladder System PDN con **ngspice**.

**System PDN** — Catena VRM → board → package → die (ngspice). Distinta da chip PDN on-die. FlowLab fase PKG.

**Site** — Slot fisico minimo per una cella (es. `FreePDK45_38x28_...`).

**Skew** — Differenza di arrivo clock tra sink diversi.

**SPEF** — Standard Parasitic Exchange Format.

**STA** — Static Timing Analysis: verifica setup/hold senza simulazione.

**STA-2204** — Errore tipico se ORFS **master** (26Q3) gira su OpenROAD **26Q2** (`get_property default` in save_images). Il repo pinna il tag ORFS **26Q2**.

**Synthesis** — RTL → gate-level netlist mappato alla libreria.

---

## T

**Tapcell** — Celle per well tie/substrate connection.

**Timing closure** — Raggiungere WNS ≥ 0 e TNS ≈ 0 su tutti i corner.

**TNS (Total Negative Slack)** — Somma di tutti i setup violation.

**Top module** — Radice gerarchia Verilog (`gcd` nel nostro corso).

---

## E

**EMSim** — Framework accademico di emanazione EM ([jinyier/EMSim](https://github.com/jinyier/EMSim), TIFS 2023). Il passo *current analysis* (PT-PX → PWL → HSpice) è lo split A/B da copiare. Prerequisiti: VCS, Calibre xRC, PrimeTime PX, HSpice — non è drop-in OSS.

## V

**vyges-em-ir** — Engine Apache-2.0 ([vyges-tools/em-ir](https://github.com/vyges-tools/em-ir)): IR statico CG + transiente backward-Euler su un `.pdn`. Integrato sul GCD via `run_vyges_em_ir.sh`. Bootstrap e check simultaneous-switch — **non** il core della piattaforma.

**Dynamic IR (I(t))** — Engine del corso (`pdn_dynamic.py`): I(t) per pin + **Solver A** (BE + LU sparso, golden) + heatmap. Non è CCS, VCD pin-accurate, SA-AMG (Solver B) né Krylov/MOR (Solver C).

---

## W

**WNS (Worst Negative Slack)** — Peggiore violazione setup (la più critica).

**Wirelength** — Lunghezza totale interconnessioni (obiettivo placement/routing).

**write_pg_spice** — Export OpenROAD PDNSim: rete R + correnti I per pin cella → input `pdn_transient.py`, `spice_to_pdn.py` (vyges-em-ir) e `pdn_dynamic.py`.

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
| Finish | WNS/TNS post-SPEF? `period_min` vs SDC? GDS apre in KLayout? |
