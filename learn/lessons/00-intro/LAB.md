# LAB 00 — Primo contatto (60–90 minuti)

Non è un “hello world”. Alla fine di questo LAB sai **dove** vive ogni file e **perché** Preview Cursor non mostra OpenROAD.

## Obiettivi misurabili

- [ ] `--check` tutto verde
- [ ] Sai indicare, a voce, le 6 macro-fasi RTL→GDS
- [ ] Hai creato `learn/workbook/mio-quaderno.md`
- [ ] Sai aprire Desktop (non Preview) e spiegare la differenza
- [ ] Hai trovato `gcd.v`, `constraint.sdc`, `floorplan.tcl` senza usare questo file come mappa

Tempo: **60 min** se già hai i tool; **90 min** se è la prima volta sul repo.

---

## Parte 1 — Ambiente (10 min)

```bash
./scripts/learn_physical_design.sh --check
openroad -version
yosys -V | head -1
sta -version
klayout -v | head -1
```

Scrivi nel quaderno: versione OpenROAD (attesa `26Q2-…`). Se manca un tool, **smetti** e usa `learn/reference/debug-playbook.md` sezione toolchain — non “provare a caso”.

Wrapper:

```bash
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --status
```

`--list` deve mostrare `00-intro` … `07-finish`. Se manca una lezione, il corso è incompleto: non sei tu.

---

## Parte 2 — Scavenger hunt cartelle (20 min)

Apri un file manager o `ls`. **Senza** copiare-incollare i path da qui, trova:

| # | Cosa | Path che hai trovato |
|---|---|---|
| 1 | RTL GCD | |
| 2 | `config.mk` del **tutorial** (non `designs/nangate45/gcd/config.mk` upstream) | |
| 3 | `constraint.sdc` del tutorial | |
| 4 | `flow/scripts/cts.tcl` | |
| 5 | PDK LEF (nangate45) | |
| 6 | Cartella dove **finirà** `6_final.gds` per la variante `learn` | |

Soluzione (guardala **dopo**):

```
1  tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v
2  learn/designs/nangate45/gcd-tutorial/config.mk
    (ORFS lo vede come flow/designs/nangate45/gcd-tutorial/ via symlink)
3  learn/designs/nangate45/gcd-tutorial/constraint.sdc
4  tools/OpenROAD-flow-scripts/flow/scripts/cts.tcl
5  tools/OpenROAD-flow-scripts/flow/platforms/nangate45/
6  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/
```

**Trappola:** `designs/nangate45/gcd/` è il design **upstream** ORFS (`FLOW_VARIANT=base` se lanci male). Il corso usa **`gcd-tutorial`** + **`FLOW_VARIANT=learn`**.

---

## Parte 3 — Contratti di fase (10 min)

Copia nel quaderno e completa a memoria:

```
Verilog+SDC → ______ → netlist gate-level
            → ______ → die/core/PDN
            → ______ → (x,y) celle
            → ______ → albero clock
            → ______ → wire DRC
            → ______ → GDS+SPEF
```

Risposte: synth, floorplan, place, CTS, route, finish.

Apri `learn/reference/file-formats.md` e per **ODB, SDC, SPEF, GDS** scrivi in una riga: tool + a cosa serve.

---

## Parte 4 — Glossario attivo (10 min)

Apri `learn/reference/glossary.md`. Senza scorrere tutto, definisci **con parole tue**:

1. Core utilization  
2. Skew  
3. WNS  
4. DRC  
5. FLOW_VARIANT  

Poi confronta col glossario. Se hai copiato le frasi, rifai.

---

## Parte 5 — Smoke synth (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 00
```

Oppure:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn synth
ls -lh results/nangate45/gcd/learn/1_synth.odb
```

Se `1_synth.odb` manca: log `logs/nangate45/gcd/learn/1_2_yosys.log`. Playbook sezione synth.

Apri `reports/nangate45/gcd/learn/synth_stat.txt` (o cerca `Printing statistics` nel log Yosys). Annota: numero di celle, area.

---

## Parte 6 — GUI: Desktop vs Preview (10 min)

1. Nella chat Cursor, **non** usare Preview per OpenROAD.
2. Apri **Desktop** sulla pagina agente.
3. Confronta con `learn/reference/gui-atlas.md` sezione 1 (anatomia). Non serve lanciare la GUI in questa lezione se il desktop non è pronto; in quel caso descrivi dal PNG `win_anatomy_labeled.png` i rettangoli A–G.

Domanda da scrivere: perché un iframe HTTP non può mostrare una finestra Qt/VNC?

---

## Parte 7 — Quaderno (5 min)

```bash
cp learn/workbook/notes-template.md learn/workbook/mio-quaderno.md
```

Compila la prima sessione: data, durata, 3 osservazioni.

---

## Criteri di superamento

- [ ] Tabella scavenger hunt compilata
- [ ] Sei fasi in ordine, a memoria
- [ ] `1_synth.odb` esiste in `.../gcd/learn/`
- [ ] Quaderno creato
- [ ] Sai spiegare Preview vs Desktop

**Non** lanciare `--all` in auto: bruci il corso.
