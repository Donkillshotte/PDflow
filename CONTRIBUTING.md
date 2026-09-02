# Contribuire

Indice: [`docs/README.md`](docs/README.md). Legge prodotto: [`learn/dse/product.md`](learn/dse/product.md).
Regole agente: [`AGENTS.md`](AGENTS.md).

## Prima di toccare codice

1. Capire la superficie: prodotto, laboratorio, o corso. Non mescolarle.
2. Un job pesante. VM ~15 GiB / 4 CPU.
3. Test sintetici o gcd-scale. Live F4 per ultimo.

## Branch e commit

Prefisso `cursor/`, suffisso assegnato dall’agente. Non lavorare su `main`.
Un commit per cambiamento logico. Non force-push. Non mergiare da soli.

Non committare leftover:

- `learn/sim/dse/memory_flowlab_nl.jsonl` (+ `.index.json`)
- `learn/sim/dse/memory_camp_spi_dse.index.json`
- `learn/sim/reports/dse_camp_spi_dse.json`
- `learn/sim/dse/tpe_*.db` (già ignorato)

## Test minimi

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/test_dse_next.py    # prodotto + mappa docs
./scripts/test_cloud_bootstrap.sh         # se si tocca install
./scripts/test_course.sh                  # se si tocca il corso
```

Lab: `python3 learn/scripts/test_dse.py` da solo, mai nello stesso processo
della suite prodotto.

## Vietato

- `if design ==` in tuner / spazio / score / coordinatore / transfer
- `FLOW_VARIANT` in `{flowlab, learn, base}` dal wrapper prodotto
- Krylov / MOR su AES (~50–70k-R)
- Restampare l’oro GCD Dynamic IR **45.298 mV**
- Sovrascrivere `results/.../gcd/flowlab/` o `memory_aes.jsonl` riga `febe6804241c`
- TPE su spi @ 1 ns
- Spostare ORFS o i moduli prodotto per “pulizia”
- Riscrivere piani congelati ([docs/piani.md](docs/piani.md))
- `pkill -f` (kill per PID)

## Documentazione

Titoli di ricetta per gli umani (`Place più denso`, non `camp_gcd_tpe_*`).
Sempre area, potenza, leakage, IR insieme. Win/lose onesti.
Se cambi un entry point, aggiorna `docs/` e il test della mappa in
`test_dse_next.py`.
