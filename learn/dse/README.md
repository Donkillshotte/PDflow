# Hardware DSE

Budget-aware, multi-fidelity search over architecture → logic → synthesis →
place → route → PDN. Levels stay separate. Dynamic IR is an OpenROAD/ODB
oracle, never a neural voltage map.

## Designs

| id | top | cones | architecture extracts |
|----|-----|-------|------------------------|
| `gcd` | `gcd` | `dpath`, `ctrl` | e-graph (GCD fixtures only) |
| `aes` | `aes_cipher_top` | none | none |

`dpath` / `ctrl` exist only on GCD. aes uses the same refine / F4 / PDN stack
without inheriting those names.

```python
from dse.designs import resolve
resolve("aes").rtl  # ORFS nangate45 aes_cipher_top
```

## Refine chain

Depth is data (`dse.frame`), not a new controller block:

| depth | legacy suffix | meaning |
|------:|---------------|---------|
| 0 | *(empty)* | leftover-combo size-up on the winning-IR-region PDN |
| 1 | `_leftover` | leftover of depth 0 |
| 2 | `_leftover2` | leftover of depth 1 |
| n | `_leftover{n}` | leftover of depth n−1 |

Stage order per depth: size-up → extract → PDN → leftover size-up if cells
remain → unused Dynamic IR catalog only when leftover is empty.

The controller pays depth ≥ 1 through `dse.dispatch.run_next_refine`.
Studio shows `refine[N]`.

## Layers

Replaceable adapters in `dse.layers.ADAPTERS`:

- **extraction** — `write_pg_spice` / ingest
- **activity** — VCD/SAIF (`dse.activity`) or OpenSTA arrivals; no invented RTL→ITerm map
- **current** — triangle I(t) × F3 power scale
- **solver** — DirectLU (default F4), AMG, RAS, Krylov/MOR
- **surrogate** — SSK-GP, GNN, residual models
- **proposer** — symbolic + optional LLM (`DSE_LLM=mock` in CI, or `DSE_LLM_URL`)

## Invariants

- Gold GCD Dynamic IR **45.298 mV** is never restamped.
- `winning_host_pdn` is host-only.
- `winning_ir_pdn` is host-win + IR-cell family. Catalogs stay separate
  (decap/pkg L ≠ pkg_r ≠ bumps ≠ pitch ≠ width).
- `QoR.static_ir_mv` is on-die ideal-bump; package-inclusive is
  `static_ir_pkg_mv` only.
- Do not flatten architecture + ABC + util + PDN into one vector.

## Run

```bash
python3 -m dse   # or the Studio DSE action
python3 learn/scripts/test_dse.py
python3 learn/scripts/test_frame.py
python3 learn/scripts/test_actions.py
python3 learn/scripts/test_dispatch.py
python3 learn/scripts/test_designs.py
```

Studio: `cd studio && npm run dev` (port 43217).
