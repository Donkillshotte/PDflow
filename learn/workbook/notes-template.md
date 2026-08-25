# Template quaderno personale

Copia questo file in `mio-quaderno.md` e compila durante il corso.

---

## Sessione ____

Data:
Lezione:
Durata:

### Obiettivo sessione


### Comandi eseguiti


### Osservazioni GUI


### Valori chiave (incolla da log/report)

| Metrica | Valore |
|---|---|
| Core area | |
| Utilization | |
| WNS | |
| TNS | |
| Cell count | |

### Problemi / errori


### Cosa ho capito oggi


### Domande per dopo


---

## Tabella sweep SDC (esercizio A2)

| SDC file | clk_period | WNS post-place | Buffer count | Note |
|---|---|---|---|---|
| relaxed | 2.0 | | | |
| default | 0.46 | | | |
| tight | 0.25 | | | |

---

## Tabella sweep utilization (esercizio B1)

| CORE_UTILIZATION | Core area (µm²) | CTS OK? | Note |
|---|---|---|---|
| 25 | | | |
| 35 | | | riferimento golden: 1712.5 |
| 50 | | | |

---

## Confronto con golden-metrics.md (ogni lezione)

| Stadio | Metrica | Mio valore | Golden | Scarto % |
|---|---|---|---|---|
| Synth | celle | | 496 | |
| Floorplan | core µm² | | 1712.5 | |
| Place | WNS / period_min | | +0.01 / 0.45 | |
| CTS | WNS / Inserted | | −0.04 / 45 | |
| Route | DRC linee | | 0 | |
| Finish | period_min / fmax | | 0.50 ns / ~2011 MHz | |

Ho chiuso il target SDC 0.46 ns (~2.17 GHz)? ______
(sul run d’oro: no, fmax ~2.01 GHz)
