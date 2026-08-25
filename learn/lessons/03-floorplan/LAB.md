# LAB 03 — Floorplan (sessione da 90–120 minuti)

## Obiettivi misurabili

- Disegnare die/core/rows su carta partendo dal log
- Spiegare i 4 metodi di init floorplan in ORFS
- Identificare PDN VDD/VSS in GUI
- Predire effetto di utilization sul core area

---

## Parte 1 — Teoria visuale (15 min)

```
┌──────────────────────── DIE ────────────────────────┐
│  margin                                             │
│    ┌────────────── CORE ──────────────┐             │
│    │ row row row row row row row row  │             │
│    │  ▢  ▢  ▢  ▢  ▢  ▢  ▢  ▢  cells  │             │
│    │ row row row row row row row row  │             │
│    └──────────────────────────────────┘             │
│  margin                                             │
└─────────────────────────────────────────────────────┘
     ↑ metal4/7 stripes VDD/VSS (PDN)
```

Leggi: `learn/reference/walkthrough-floorplan.tcl.md` (30 min consigliati).

---

## Parte 2 — Esecuzione floorplan (20 min)

```bash
./scripts/learn_physical_design.sh --lesson 03
```

Oppure manuale:
```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn floorplan
```

Verifica output:
```bash
ls -lh results/nangate45/gcd/learn/2_*.odb
```

Attesi: `2_1_floorplan.odb`, `2_2_floorplan_macro.odb`, `2_3_floorplan_tapcell.odb`, `2_4_floorplan_pdn.odb`, `2_floorplan.odb`

---

## Parte 3 — Analisi log (25 min)

```bash
rg -n 'Core area|Die area|utilization|initialize_floorplan' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/2_1_floorplan.log
```

Compila tabella nel quaderno:

| Metrica | Valore | Unità |
|---|---|---|
| Core area | | µm² |
| Effective utilization | | ratio |
| Site name | | text |

**Esercizio B1 workbook:** ripeti con `CORE_UTILIZATION=25` e `50`.

```bash
CORE_UTILIZATION=25 make ... clean_floorplan floorplan
# annota core area
CORE_UTILIZATION=50 make ... clean_floorplan floorplan
```

Domanda: core area scala linearmente con 1/utilization? (approssimativamente sì)

---

## Parte 4 — PDN Tcl (20 min)

Apri: `flow/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl`

Identifica:
1. `set_voltage_domain` — quale net power/ground?
2. `add_pdn_stripe` — quali layer?
3. `add_pdn_connect` — quali via stack?

Disegna a mano: M1 followpin → M4 → M7

---

## Parte 5 — GUI session (30 min)

Atlante obbligatorio: `learn/reference/gui-atlas.md` §5.2–5.4 (PNG `win_floorplan.png`, `win_pdn.png`, `03_pdn_labeled.png`).

### Sessione A — Core init
```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_2_1_floorplan.odb
```

Checklist:
- [ ] Fit (`F`) — due rettangoli concentrici (die / core)
- [ ] Canvas quasi vuoto: **normale** (nessuna logica piazzata)
- [ ] **Non** usare `gui::set_display_controls "Rows" visible true` → `GUI-0013` in questa build; cerca Rows nel tree se c’è, altrimenti passa al PDN
- [ ] Aspect ratio visivo ~1.0

### Sessione B — PDN
```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_2_4_floorplan_pdn.odb
```

Checklist (colori Nangate45 in *questa* GUI):
- [ ] Linee blu fitte = rail M1 followpin
- [ ] Strap verdi verticali + rosa orizzontali
- [ ] Display Control: spegni metal2/metal3 per “pulire” il segnale (non c’è ancora)
- [ ] Tcl: `gui::set_display_controls "Nets/Power" visible true`
- [ ] Tapcell: `gui_2_3_floorplan_tapcell.odb` o PNG `win_tapcell.png`

**Scavenger hunt B3:** annota nel quaderno i colori strap vs rail; confronta con `03_pdn_labeled.png`.

---

## Parte 6 — Confronto pre/post floorplan (10 min)

| File | Celle posizionate? | Routing? | PDN? |
|---|---|---|---|
| 1_synth.odb | no (0,0 stack) | no | no |
| 2_1_floorplan.odb | no | no | no |
| 2_4_floorplan_pdn.odb | no | no | sì |

Floorplan **non piazza celle logiche** — prepara solo il "terreno".

---

## Criteri "lezione superata"

- [ ] Tabella utilization vs core area (3 righe)
- [ ] PDN spiegato a voce in 60 secondi
- [ ] Screenshot o descrizione GUI PDN
- [ ] Letto walkthrough-floorplan.tcl.md completo

Prossimo LAB: 04-placement (global vs detailed)
