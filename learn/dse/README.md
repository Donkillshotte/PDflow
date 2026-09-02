# Hardware DSE

**Product** (what we ship decisions on): physical knobs on the official
netlist, with the official floorplan pinned (area, size, shape). Win rule
includes slack, area, power, leakage, and IR — see `learn/dse/product.md`.
Loop: `learn/scripts/run_recipe_loop.py`.

**Lab** (not the product): the older controller — e-graph / RTL rewrite /
F4 IR / refine. It stays in the tree. It does not decide product wins.

Budget-aware, multi-fidelity search over architecture → logic → synthesis →
place → route → PDN. Levels stay separate. Dynamic IR is an OpenROAD/ODB
oracle, never a neural voltage map.

## Designs

| id | top | cones | architecture extracts | F1 |
|----|-----|-------|------------------------|----|
| `gcd` | `gcd` | `dpath`, `ctrl` | e-graph (GCD fixtures only) | Yosys Verilog + equiv |
| `aes` | `aes_cipher_top` | none | none | 4-file Verilog, equiv off |
| `ibex` | `ibex_core` | none | none | refused (`f1_ready=False`, slang) |

`dpath` / `ctrl` exist only on GCD. aes uses the same refine / F4 / PDN stack
without inheriting those names. Inverse-cipher RTL (`aes_inv_*`) is a
different top and is not mixed into `aes`.

F1 for aes reads **four** Verilog files (cipher + key_expand + sbox + rcon)
with `-I` so `` `include "timescale.v" `` resolves. Equiv is skipped
(`f1_equiv=False`); timeout 240s. F3 / arrivals use `DesignSpec.constraint`
(aes 0.82 ns, gcd 0.46 ns) — never a silent GCD SDC borrow. ibex stays GAP
until a slang frontend exists — not a fake Verilog remap.

```python
from dse.designs import resolve
resolve("aes").rtl  # ORFS nangate45 aes_cipher_top
```

Live aes F1 + F2-fast + F3 (aes 0.82 ns SDC) + budgeted GPL + candidate
write_pg_spice. Meshes above 40k R pay Krylov/MOR (DirectLU refuses above 40k R; AMG
timed out on the 73k-R aes mesh). Clock for I(t) is
`DesignSpec.clk_period_ns` (aes 0.82, gcd 0.46). A VCD/SAIF on disk is
passed to the F4 worker as a name-join only — missing stays missing,
SAIF TC=0 idle-zeros a matched pulse and never invents t50.
`inspect_and_choose` attributes the latest F4 via the ODB hotspot join
and opens refine[0] size-up on that design's cells (aes flattened names
stay under `aes_cipher_top`, never GCD `dpath`/`ctrl`). Separate memory,
never FlowLab GCD / gold 45.298:

```bash
python3 learn/scripts/run_aes_slice.py
python3 learn/scripts/run_aes_f4.py
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
- **solver** — DirectLU (default F4), AMG, RAS, Krylov/MOR. `solver_devices()`
  reports `cpu` always and `cuda` only when `nvidia-smi -L` lists a GPU.
  `solve_f4(..., device="cuda")` is GAP when CUDA is absent — not a host
  solve restamped as GPU.
- **surrogate** — SSK-GP, GNN, residual models
- **proposer** — symbolic + optional LLM (`DSE_LLM=mock` in CI, or `DSE_LLM_URL`)

## Invariants

- Gold GCD Dynamic IR **45.298 mV** is never restamped.
- `winning_host_pdn` is host-only.
- `winning_ir_pdn` is host-win + IR-cell family. Catalogs stay separate
  (decap/pkg L ≠ pkg_r ≠ bumps ≠ pitch ≠ width).
- `QoR.static_ir_mv` is on-die ideal-bump; package-inclusive is
  `static_ir_pkg_mv` only.
- `QoR.area_um2` is mapped **stdcell / instance** area, not die size.
  `n_cells` is the instance count. `power_w` is OpenSTA Total;
  `leakage_w` is the Leakage column. Internal/switching are observation
  fields, not Pareto axes. `tns_cost` is `-TNS`. `hpwl_um` is OpenROAD
  microns (never F2-fast grid HPWL). Missing ≠ 0.
- Do not flatten architecture + ABC + util + PDN into one vector.
- ``Candidate`` roles stay split: ``knobs`` action, ``artifacts`` observation,
  ``attr`` interpretation, ``pred`` prediction, ``delta`` vs parent.
  ``SolveResult`` (``dse.solve_result``) is the F4 observation contract;
  DirectLU is the numerical reference. ``admit_solve`` is the resource gate.

## Campaign

Default CLI is one ``run_controller`` pass. ``--campaign`` loops that pass on
the **same** JSONL until gated hypervolume (logic area vs ``wns_cost``) stops
growing, the wall budget ends, or an inner run adds zero new ``ok`` rows.
Lifetime shot caps start at today's defaults (GPL/F5/CTS/cell/net = 1) and
rise by one per inner so a later parent can be placed; knobs fingerprints
still skip duplicates. ``Candidate.pred`` is order/tie-break only.

```bash
python3 -m dse   # or the Studio DSE action
python3 learn/scripts/run_dse.py --campaign --wall-s 180 --hv-eps 0.001
python3 learn/scripts/test_dse.py
python3 learn/scripts/test_frame.py
python3 learn/scripts/test_actions.py
python3 learn/scripts/test_dispatch.py
python3 learn/scripts/test_designs.py
python3 learn/scripts/test_candidate_schema.py
python3 learn/scripts/test_krylov_rlc.py
python3 learn/scripts/test_activity_it.py
python3 learn/scripts/run_aes_slice.py
```

Studio: `cd studio && npm run dev` (port 43217).

GCD vs ORFS `make finish` (honest, not a slide):
[`flow_vs_orfs_gcd.md`](flow_vs_orfs_gcd.md).
Piano per cucinare i winner DSE con lo stesso finish:
[`handoff_finish_plan.md`](handoff_finish_plan.md).
Esito (A resta): [`handoff_finish_bakeoff.md`](handoff_finish_bakeoff.md).
