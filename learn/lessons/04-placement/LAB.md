# LAB 04 — Placement (90–120 minuti)

Qui il design **occupies space**. Bring open: atlas GUI §5.5–5.6 e `walkthrough-global_place.tcl.md`.

## Measurable objectives

- [ ] Distinguere GP e DP su screenshot o GUI (non in vague words)
- [ ] Extracted WNS/TNS/buffer da `3_resizer.rpt`
- [ ] Found almeno un prefisso resizer (`rebuffer*`, `fanout*`, …)
- [ ] Connected tight clock → more buffer → more area → CTS risk

---

## Part 1 — Theory operativa (15 min)

Reread `lessons/04-placement/README.md` tabelle sub-stages.

In one sentence ciascuna:

1. Cosa optimizes **global placement**?
2. Cosa forbids **detailed placement**?
3. Why ORFS fa GP, **poi** resizer, **poi** DP (e non DP before del resizer)?

Hint: i buffer del resizer devono essere legalized.

---

## Part 2 — Walkthrough Tcl (20 min)

Apri `flow/scripts/global_place.tcl` e il walkthrough.

Segna:

| Riga / blocco | What it does | If you remove it… |
|---|---|---|
| `buffer_ports` | | slew sui pin I/O |
| `GPL_TIMING_DRIVEN` | | GP ignora slack |
| `-density` | | overflow / holes |
| `estimate_parasitics -placement` | | STA blind to wires |

Poi `flow/scripts/detail_place.tcl`: `detailed_placement`, `improve_placement`, `optimize_mirroring`, `check_placement`.

**Question:** because esiste `3_5_place_dp-failed.odb`?

---

## Part 3 — Run place (15 min)

```bash
./scripts/learn_physical_design.sh --deep --lesson 04
```

O:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 place
ls results/nangate45/gcd/learn/3_3_place_gp.odb \
   results/nangate45/gcd/learn/3_4_place_resized.odb \
   results/nangate45/gcd/learn/3_5_place_dp.odb
```

---

## Part 4 — Report (25 min)

Leggi **in full** (are corti on the GCD):

```bash
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_global_place.rpt
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt
```

Estrai nel notebook:

| Metric | Valore | Files |
|---|---|---|
| Overflow GP | | 3_global_place / log 3_3 |
| WNS | | 3_resizer |
| TNS | | 3_resizer |
| Buffer inserted | | log `3_4_place_resized` (`Inserted`) |
| Resize / upsize | | same log |

```bash
rg -n 'Inserted|Resize|WNS|TNS|overflow' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/3_4_place_resized.log \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  | head -40
```

Workbook **C2**: stesso numero nel notebook.

---

## Part 5 — GUI comparison GP vs DP (30 min)

Desktop. Two loads (o due terminali):

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_3_place_gp.odb
# another shell, stesso cwd:
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_5_place_dp.odb
```

Use `learn/reference/gui-atlas.md`:

- GP: `win_place_gp.png` / `04_place_gp_labeled.png` — blob, possible visual overlap
- DP: `win_place_dp.png` / `05_place_dp.png` — row alignment

Checklist:

- [ ] Fit (`F`) su entrambi
- [ ] I/O triangles on edge (GP after IOP)
- [ ] Visible PDN straps
- [ ] Heatmap Placement Density se c’is in View (red = full)

Find: `rebuffer`, `clkbuf` (pre-CTS i clkbuf are pochi).

Se you have not Desktop: note le differenze **on repor PNGs** — is accepted, ma try the GUI at least once nel course.

---

## Part 6 — Bridge to CTS (10 min)

Scrivi la catena (lesson 01+03+04):

```
SDC stretto → WNS negativo → RSZ buffer → area ↑ → stesso core (util 35%)
  → al CTS detailed_placement may hit DPL-0038
```

Predici: con `constraint_tight.sdc` i buffer in `3_4` rise or fall?

---

## Pass criteria

- [ ] Table metrics resizer
- [ ] Una differenza GP/DP documented (screenshot o riferimento atlas)
- [ ] Prefisso resizer spiegato
