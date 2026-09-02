# Risultati (onesti)

Registro: `learn/sim/dse/campaign_experiments.jsonl`.
Verdetto = `win_rule`, non lo score TPE.

Percentuali = variazione della metrica vs base dello slot.
Negativo su area / potenza / leakage / IR = più piccolo (meglio).

## Per slot

| Slot | Base | OFAT | TPE | Min/finish |
|---|---|---|---|---|
| gcd | −37 ps | 3 win (Place più denso, Padding +1, …) | 8 cook, **0 win nuovi** | ~0.9 |
| spi | +612 ps | 0 win (10 tie) | non ammissibile | ~0.6 |
| ibex | +22 ps | 4 win | 8 cook, **6 win nuovi** | ~7 |
| aes | −8.9 ps | 3 win | 8 cook, **5 win nuovi** | ~8 |
| dynamic_node | +3354 ps | 1 win (Buffer di clock più fitti) | non ancora | ~4.5 |

## Cosa ha funzionato

- **Ibex:** combo OFAT (Place sparso + pad, Place denso + pad) e mix IR
  fino a −38%, slack dentro 5 ps. Area / potenza / leakage ~0 o sotto +10%.
- **Aes:** chiude il timing (base era aperto). Area / potenza / leakage
  salgono un po’ (fino a +7%), tutti sotto il 10%. SHA `6_report` = disco.
- **Enqueue stesso-slot:** i 2 win immediati aes erano combo deepen
  (Place più sparso + Margine di setup; Setup + Buffer di clock più fitti).

## Cosa non ha funzionato

- **Gcd:** il continuo TPE non ha battuto OFAT. Miss vicino: IR −19% con
  slack −7.4 ps (vincolo, non proposta cieca).
- **Padding celle +2:** 5 fail (3 gcd, 2 ibex). Il place può chiudere;
  il finish no. Ora è un muro.
- **Place sparso + CTS 80 su aes:** lose, slack −30 ps.
- **Senza timing-driven su aes:** STOP al place (WNS −0.78 / −0.47 ns).
- **Sintesi gerarchica:** 0 win su 5 design. Muro.

## Transfer (dopo i live)

`learn/dse/tune_transfer.py`: pad=2 e synth_hier non si ricuociono;
fino a 3 meccanismi win-su-≥2-design in coda TPE.
«Place più sparso + margine di setup» è ricetta di catalogo.

Criterio di successo del transfer (congelato in `arch_review.md`):
sul prossimo slot live, zero pad=2, un enqueue cross-design nei primi 3,
primo win entro 3 cotture — o verdetto onesto che lo slot non ha win.
