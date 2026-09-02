# Personal notebook template

Copy this file to `my-notebook.md` and fill in during the course.

---

## Session ____

Date:
Lesson:
Duration:

### Session objective


### Commands run


### GUI observations


### Key values (paste from log/report)

| Metric | Value |
|---|---|
| Core area | |
| Utilization | |
| WNS | |
| TNS | |
| Cell count | |

### Problems / errors


### What I understood today


### Questions for later


---

## SDC sweep table (exercise A2)

| SDC file | clk_period | WNS post-place | Buffer count | Notes |
|---|---|---|---|---|
| relaxed | 2.0 | | | |
| default | 0.46 | | | |
| tight | 0.25 | | | |

---

## Utilization sweep table (exercise B1)

| CORE_UTILIZATION | Core area (µm²) | CTS OK? | Notes |
|---|---|---|---|
| 25 | | | |
| 35 | | | golden reference: 1712.5 |
| 50 | | | |

---

## Comparison with golden-metrics.md (every lesson)

| Stage | Metric | My value | Golden | Delta % |
|---|---|---|---|---|
| Synth | cells | | 496 | |
| Floorplan | core µm² | | 1712.5 | |
| Place | WNS / period_min | | +0.01 / 0.45 | |
| CTS | WNS / Inserted | | −0.04 / 45 | |
| Route | DRC lines | | 0 | |
| Finish | period_min / fmax | | 0.50 ns / ~2011 MHz | |

Did I close the SDC target 0.46 ns (~2.17 GHz)? ______
(on the golden run: no, fmax ~2.01 GHz)
