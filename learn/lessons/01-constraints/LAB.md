# LAB 01 — Constraints e SDC (sessione da 90–120 minuti)

## Obiettivi misurabili

Al termine devi saper:
- Spiegare ogni riga del tuo `constraint.sdc` a voce alta
- Predire l'effetto di ±50% sul clock period prima di lanciare il flow
- Trovare WNS/TNS in un report senza aiuto

---

## Parte 1 — Lettura guidata SDC (20 min)

Apri: `learn/designs/nangate45/gcd-tutorial/constraint.sdc`

### Riga per riga

```tcl
current_design gcd
```
→ Dice a OpenSTA quale top module analizzare. Deve coincidere con `DESIGN_NAME` in config.mk.

```tcl
set clk_period 0.46
```
→ **Periodo** in nanosecondi, non frequenza. Frequenza = 1/0.46 ≈ 2.17 GHz.

```tcl
create_clock -name $clk_name -period $clk_period $clk_port
```
→ Crea clock virtuale su porta `clk`. Tutti i FF di quel dominio ereditano il periodo.

```tcl
set_input_delay [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs
```
→ Modello: segnali input arrivano con ritardo rispetto al clock edge. 20% del periodo = budget IO.

**Scrivi nel quaderno:** input_delay = ______ ns

---

## Parte 2 — Esperimento file (30 min)

### Run 1 — Baseline
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc learn/workbook/backup-sdc-default.sdc
./scripts/learn_physical_design.sh --lesson 01
# oppure solo:
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
```

Annota da `reports/.../learn/3_resizer.rpt`:
- WNS worst setup
- Numero buffer (cerca "Inserted")

### Run 2 — Relaxed
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint_relaxed.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 \
     clean_synth clean_floorplan clean_place
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
```

**Domanda:** WNS migliorato? Area celle diminuita?

### Run 3 — Tight (opzionale, può fallire dopo)
```bash
cp learn/designs/nangate45/gcd-tutorial/constraint_tight.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

Se CTS fallisce più avanti → **successo didattico**. Apri debug-playbook.

---

## Parte 3 — config.mk (20 min)

Apri `learn/designs/nangate45/gcd-tutorial/config.mk`

| Variabile | Valore corso | Cosa succede se raddoppi |
|---|---|---|
| CORE_UTILIZATION | 35 | core più piccolo → rischio overflow |
| FLOW_VARIANT | learn | risultati separati da base |
| PLACE_DENSITY_LB_ADDON | 0.20 | margine density placement |

**Esercizio:** aggiungi commento `# lezione01: mio valore util=40` e prova `CORE_UTILIZATION=40` da CLI:

```bash
CORE_UTILIZATION=40 ./scripts/run_gcd_flow.sh floorplan
```

Confronta core area nel log con util 35.

---

## Parte 4 — GUI timing (20 min)

Prerequisito: Desktop Cursor aperto.

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_place.odb
```

Checklist GUI:
1. [ ] Pannello Charts → Endpoint Slack visibile
2. [ ] Clic su endpoint con slack negativo
3. [ ] View → Worst Path (path evidenziato)
4. [ ] Identifica una `DFF_X1` sul path

**Scrivi:** nome del pin di partenza e arrivo del worst path.

---

## Parte 5 — OpenSTA standalone (15 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
sta -no_init <<'EOF'
read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_verilog results/nangate45/gcd/learn/1_2_yosys.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
report_checks -fields {slew cap input_pins fanout} -max_paths 5
EOF
```

Confronta slack con report post-place. Perché differiscono? (hint: parassiti, placement)

---

## Parte 6 — Riflessione scritta (10 min)

Rispondi in `learn/workbook/mio-quaderno.md`:

1. Cos'è il tradeoff clock period vs area?
2. Perché input_delay usa percentuale del periodo?
3. Quando useresti `set_false_path`? (cerca esempio online o in altri design ORFS)

---

## Criteri "lezione superata"

- [ ] Tabella sweep SDC compilata (workbook A2)
- [ ] Worst path identificato in GUI
- [ ] Spiegato `create_clock` a qualcuno (o a voce alta registrata)
- [ ] Ripristinato constraint.sdc default

Ripristino:
```bash
cp learn/workbook/backup-sdc-default.sdc learn/designs/nangate45/gcd-tutorial/constraint.sdc
```
