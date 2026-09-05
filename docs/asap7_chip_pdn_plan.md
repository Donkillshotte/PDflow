# ASAP7 on-die chip PDN mesh plan

Living plan. Not a frozen DSE plan. Not a course switch. Not a product
win surface. Do not restamp gold Dynamic IR **45.298 mV**. Do not
overwrite `nangate45/gcd/flowlab`. Do not write `.chip_pdn_ir.ok` gold
stamps. One heavy cook at a time.

Question: the Lab ASAP7 track cooks RTL→GDS and reads **static IR**
from `6_report` PDNSim, and `lab_asap7_pkg` covers **system/package**
compact PDN. What is missing for **on-die mesh** analysis
(`write_pg_spice` + `pdn_transient.py`) on `lab_asap7_*` finishes —
and how do we wire it without mixing Nangate gold or product surfaces?

**Answer: the Nangate chip-PDN stack exists (`run_chip_pdn_ir.sh`) but
is hard-coded to `nangate45/gcd/{flowlab,learn}`. ASAP7 has no
`pg_vdd_bumps.sp`, no leftover-named chip-PDN script, no folio field,
no suite hook. This plan adds a Lab-only mesh path parallel to the
existing e2e analysis chain (DRC, LVS, MMMC, layer-1, PKG).**

Checked on disk 2026-09-05. Parent consolidation:
[`asap7_e2e_plan.md`](asap7_e2e_plan.md) (W1–W10 landed; PKG
workstream landed). Backside BPR fork reading:
[`asap7_research.md`](asap7_research.md) § Backside PDN forks.

---

## 1. Three PDN tiers (do not confuse)

| Tier | Question | Today on ASAP7 Lab | This plan |
|---|---|---|---|
| **A — Cook PDNSim** | Worst static IR on the finished grid? | ✅ `6_report` → `ir_drop_vdd_mv` in folio | Compare against tier B |
| **B — Chip mesh** | R-mesh + I(t) on `write_pg_spice`? | ❌ not wired | **W13 target** |
| **C — System/package** | VRM→board→pkg ladder? | ✅ `lab_asap7_pkg` compact ngspice | Already done; keep separate |

Tier B is what Nangate calls **chip PDN** (`run_chip_pdn_ir.sh`).
Tier C is what `lab_asap7_pkg` does. Tier A is embedded in `finish`.
All three can coexist; none replaces another.

Do **not** compare tier-C droop (~1.6 mV compact) to tier-A/B on-die
IR (~2.5 mV on gcd 480 ps) as if they were the same physics.

---

## 2. Template: what Nangate chip PDN does

`learn/scripts/run_chip_pdn_ir.sh` on `nangate45/gcd/flowlab`:

1. `read_db 6_final.odb` + liberty + SDC + activity (`report_power`)
2. `set_pdnsim_source_settings` (bump pitch, `PKG_R` proxy)
3. `analyze_power_grid` — STRAPS, FULL, BUMPS
4. `write_pg_spice -net VDD -source_type BUMPS` → `pdn/pg_vdd_bumps.sp`
5. `pdn_transient.py` — backward-Euler dynamic IR on that mesh
6. Report `pdn_chip_ir_<variant>.json` + waveform CSV

Validation on Nangate: static engine ≈ **4.56 mV** vs OpenROAD ≈
**4.47 mV** (`learn/reference/system-pdn.md`).

ASAP7 must **not** reuse Nangate paths, bump geometry (140 µm pitch on
an ~8.8 µm gcd die), or 1.1 V assumptions.

---

## 3. ASAP7-specific constraints

| Topic | ORFS 7.5T Lab cook | Implication for mesh |
|---|---|---|
| Die size | gcd ≈ 8.8 µm (`8786×8786` DBU @ 1000) | Bump pitch/size must be **scaled**, not Nangate 140/70 |
| Vdd | TC **0.70 V** (corner-dependent) | `set_pdnsim` / SPICE at cook voltage |
| Liberty | `platforms/asap7/lib/NLDM` per corner/VT | Resolve from variant name (like `lab_asap7_mmmc.py`) |
| SDC | `learn/sim/dse/sdc/asap7_<variant>.sdc` when `LAB_CLK_PS` set | Read from result dir or regenerated path |
| Mesh output | **No** `pg_vdd_bumps.sp` today | Must create under `results/asap7/.../pdn/` |
| IR in folio | `finish__design_powergrid__drop__worst__net:VDD` | Tier A baseline for sanity check |
| Gold | Nangate 45.298 mV | `comparable_to_gold_ir: false` always |

Open questions for **W13.0 spike** (must answer before implementation):

1. Does OpenROAD PDNSim `write_pg_spice` succeed on ASAP7 `6_final.odb`
   without Tcl changes?
2. What bump `dx/dy/size` produces a non-empty mesh on ~9 µm die?
3. Does `pdn_transient.py` parse ASAP7 node names unchanged?
4. How close is tier-B static IR to tier-A `6_report` (expect same order
   of magnitude, not bit-identical)?

---

## 4. Work packages

### W13.0 — Spike (manual, one closed cook)

**Why.** FinFET 7.5T mesh on a micro-die may fail or need Tcl tuning.
Do not commit scripts until one live extraction works.

**What.**

1. Pick `lab_asap7_gcd_tc_rvt_nldm_7p5_480ps` (timing-closed, GDS live).
2. OpenROAD Tcl probe (sidecar log only):
   - `read_liberty` (TC RVT NLDM set)
   - `read_db` `6_final.odb`
   - `read_sdc` cook SDC
   - `report_power`
   - `analyze_power_grid` STRAPS/FULL/BUMPS
   - `write_pg_spice` → `pdn/pg_vdd_bumps.sp`
3. Record: R count, V source count, worst IR from log, file size.
4. If mesh parses, run `pdn_transient.py` once by hand.
5. Document scaled bump parameters that worked.

**Acceptance.** A gitignored spike log under
`learn/sim/reports/lab_asap7_chip_pdn_spike.log` proves
`write_pg_spice` ran OR names the honest GAP (e.g. PDNSim refuses
tiny die).

### W13.1 — Leftover-named script + wrapper

**Why.** Repeatable, refused, Lab-only entry point.

**What.**

- `learn/scripts/lab_asap7_chip_pdn.py` — orchestrator
- `learn/scripts/run_lab_asap7_chip_pdn.sh` — thin wrapper
- Refuse unless `variant.startswith("lab_asap7_")`
- Refuse locked variants; refuse `nangate45` paths
- Resolve `odb`, `lib*` list, `sdc`, `vdd` from variant + `asap7_lab.CORNERS`
- Bump settings: **ASAP7-scaled** defaults (from W13.0), overridable via env
- `PKG_R` / `PKG_L` defaults aligned with `learn/lab/asap7/pkg/asap7_system_pdn.json` (educational, not gold)
- OpenROAD pass → `write_pg_spice`
- `pdn_transient.py` pass → static + transient summary
- Report `learn/sim/reports/lab_asap7_chip_pdn.json` (+ optional
  `lab_asap7_chip_pdn_<variant>.json`)
- Fields: `product_win: false`, `comparable_to_gold_ir: false`,
  `tier: "chip_mesh"`, `pdnsim_6_report_mv`, `mesh_static_mv`,
  `mesh_transient_droop_mv`, `n_r`, `n_sources`, `spice_path`
- Never write `.chip_pdn_ir.ok` stamp files

**Acceptance.** Script exits 0 on closed gcd when spike succeeded;
exits 0 with `status: GAP` when OpenROAD/ngspice missing (honest).

### W13.2 — E2e runner + folio

**Why.** Mesh analysis must run with the other post-finish hooks.

**What.**

- `run_asap7_e2e.py` `run_analysis()` calls `lab_asap7_chip_pdn.py`
  on first closed variant (same selection as PKG/MMMC)
- `collect_report()` / folio row may gain optional `chip_pdn` summary
  when report exists (read-only; no cook change)
- `write_folio()` `closure_ladder` unchanged

**Acceptance.** `run_asap7_e2e.py --skip-analysis` unchanged; full e2e
populates `lab_asap7_chip_pdn.json` when tier-2 GDS live.

### W13.3 — Tests (two-tier)

**Why.** Same honesty contract as DRC/LVS/PKG.

**Tier 1** (`test_asap7_lab.py` — no GDS):

- Script + wrapper exist
- Refuses non-`lab_asap7_*` variant
- No `45.298`, no `nangate45/gcd/flowlab` paths in script
- `product_win: false` in report schema docstring or default payload
- Does not import Nangate `run_chip_pdn_ir.sh` as-is

**Tier 2** (`test_asap7_e2e.py` — live GDS):

- `lab_asap7_chip_pdn.json` exists after e2e analysis
- `n_r > 0` (or named GAP with reason)
- `mesh_static_mv` within sane band vs `pdnsim_6_report_mv` (e.g. same
  order of magnitude; document tolerance after W13.0)
- `comparable_to_gold_ir: false`
- No `45.298` in report

Fast gate: `test_asap7_lab.py` always; tier 2 only when folio ≥ 8.

### W13.4 — Studio, catalog, docs

**Why.** Visibility without promoting to product.

**What.**

- Suite hook `asap7_chip_pdn` in `studio/src/lib/suite.ts`
- `asap7ChipPdnHookDetail()` in `leftoverCatalog.ts`
- LabBench row: mesh static / transient vs `6_report` IR
- `leftover_catalog.json` item `asap7_chip_mesh` (gated)
- `suite-status.md` row: chip mesh (WORKS* / GAP)
- `docs/script.md` lists new scripts
- `learn/lab/asap7/README.md` one paragraph
- `test_dse_next.py` map checks

**Acceptance.** `GET /api/suite` exposes hook; map check passes.

### W13.5 — Optional follow-ons (out of initial W13 scope)

| Item | Notes |
|---|---|
| `lab_asap7_sta_ir_aware.py` | STA × ITerm V from mesh; after tier B stable |
| vyges on ASAP7 mesh | Likely GAP on FinFET; name honestly |
| `dynamic_ir` for `lab_asap7_*` | Heavy; separate goal; no AES |
| Couple mesh bumps to `lab_asap7_pkg` | Tier B → tier C boundary; after both stable |
| Backside mesh (W12) | Reuse tier-B tooling on bb_pdk cooks later |

---

## 5. Refuse rules (inherited + new)

| Rule | Reason |
|---|---|
| `lab_asap7_*` only | Lab surface |
| No `flowlab` / `learn` / `base` | Course/product locked |
| No writes under `nangate45/` | AGENTS.md |
| No `.chip_pdn_ir.ok` gold stamps | Honest leftover |
| `comparable_to_gold_ir: false` | Different mesh, voltage, die |
| `product_win: false` | Not win_rule |
| No `if design ==` in shared tuner/space | Product law |
| One heavy OpenROAD job at a time | AGENTS.md |
| No AES mesh “just to see” | AGENTS.md |
| Do not restamp 45.298 mV | Gold sentinel |

---

## 6. Done when (completion audit)

1. W13.0 spike log proves `write_pg_spice` on ASAP7 **or** documents
   named GAP with reproduction steps.
2. `lab_asap7_chip_pdn.py` + wrapper committed; refuses non-lab paths.
3. `run_asap7_e2e.py` analysis hook calls chip PDN on closed cook.
4. `test_asap7_lab.py` tier 1 + `test_asap7_e2e.py` tier 2 pass on
   toolchain image with live gcd 480 ps.
5. `lab_asap7_chip_pdn.json` gitignored; no frozen ASAP7 mesh gold in git.
6. Studio hook + suite-status row + map check land.
7. Gold IR SHA and Nangate FlowLab GDS untouched
   (`assert_nangate_gold_untouched()`).
8. Folio reports tier-A (`6_report`) and tier-B (mesh) side by side
   with explicit `not comparable to 45.298 mV`.

Anything less is progress, not done.

---

## 7. Order of execution

1. **W13.0** spike on existing 480 ps gcd (manual Tcl + one transient run).
2. **W13.1** script + wrapper (defaults from spike).
3. **W13.3** tier-1 tests (with W13.1).
4. **W13.2** e2e hook.
5. Run e2e analysis; fix bump scaling if tier 2 fails.
6. **W13.4** Studio + docs + map check.

Each lands as its own commit. Do not batch spike parameters with Studio.

---

## 8. Relationship to sibling workstreams

| Workstream | Relationship |
|---|---|
| **E2e W1–W10** | Parent runner; this extends `run_analysis()` |
| **PKG leftover** | Tier C; complementary; do not merge reports |
| **W11 standard 6T** | Orthogonal platform; mesh script should accept any `lab_asap7_*` ODB |
| **W12 backside BPR** | Future; may reuse tier-B tooling on ICC2-exported ODB — not W13 |
| **Nangate chip_pdn** | Template only; do not call from ASAP7 path |

---

## 9. Commands (target state)

```bash
# After W13 lands — on a live closed cook
python3 learn/scripts/lab_asap7_chip_pdn.py \
  --variant lab_asap7_gcd_tc_rvt_nldm_7p5_480ps

# Or via e2e analysis pass
python3 learn/scripts/run_asap7_e2e.py --skip-analysis  # cooks only
# re-run analysis only: (TBD helper or manual script calls)

# Spike (W13.0 — manual, pre-script)
# See learn/sim/reports/lab_asap7_chip_pdn_spike.log after W13.0
```

---

## 10. Sources

- Nangate template: `learn/scripts/run_chip_pdn_ir.sh`
- Mesh solver: `learn/scripts/pdn_transient.py`, `learn/scripts/pdn_extract.py`
- System PDN (tier C): `learn/scripts/lab_asap7_pkg.py`
- IR in cook: `learn/dse/asap7_lab.py` `collect_report()`
- Landscape: `learn/reference/system-pdn.md`, `learn/reference/spice-power-chain.md`
