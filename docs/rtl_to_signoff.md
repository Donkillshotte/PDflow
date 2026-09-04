# RTL-to-signoff campaign status

Living campaign log for the course close on Nangate45 GCD. **Not a frozen
DSE plan.** Do not fold this review into `tpe_plan.md`, `product.md`,
`arch_review.md`, `next_iteration_plan.md`, `PLAN.md`,
`experiment_campaign_plan.md`, or `joint_recipe_plan.md`.

| Field | Value |
|---|---|
| Stopped | 2026-09-04 |
| Branch | `cursor/complete-pd-flow-86b9` @ `3bb105d` |
| Surface | Course / Studio only |
| Verdict | **Stopped, not achieved.** Path is leftover-named and functional on the educational golden. It is **not leftover-free.** |

The leftover-free RTL-to-signoff goal ran ~17 h and was stopped on
request. Green `signoff_all` still names leftovers. Do not redefine
leftover-named as leftover-free.

Evidence files (authoritative for numbers below):

- `learn/sim/reports/signoff_all_flowlab.json`
- `learn/sim/reports/signoff_all_eco_scratch.json`
- `learn/sim/reports/lib_corner_coverage.json`
- `learn/sim/reports/drc_deck_coverage.json`
- `learn/reference/gaps.md`

---

## Original nine items

| # | Ask | Status | Evidence |
|---|---|---|---|
| 1 | Fix LVS (well pins + empty FILL/TAP CDL) so `signoff_all` is not blocked | **Proven** | KLayout prints `CONGRATULATIONS! Netlists match`. Leftover must-connect **2** on `DFF_X2`. Nangate does **not** block LVS. |
| 2 | Minimal ECO loop that cannot bypass `signoff_all` | **Proven** | Apply refused on `flowlab`. Close is `FLOW_VARIANT=<copy> ./learn/scripts/run_signoff_all.sh`. Two-process apply: SPEF size-up then BufferMove without SPEF. |
| 3 | DSE stays proposer, never orchestrator | **Proven** | `learn/dse/flow_role.py` |
| 4 | Docs: license-gated vs to-build GAPs | **Proven** | `learn/reference/gaps.md` |
| 5 | Verify antenna / density / ERC in the KLayout DRC deck | **Proven (honest)** | Antenna **300:1** is in `FreePDK45.lydrc`. Density and named ERC are **not**. Stamped as leftover. |
| 6 | Evaluate MCMM honestly | **Proven (honest)** | One `NangateOpenCellLibrary_typical.lib`. Stamped leftover no MCMM. |
| 7 | Iterate until the path is clean and functional | **Functional, not leftover-free** | `eco_scratch` four pillars `ok`. R2R MET. Leftover WNS −0.01 on `resp_msg[14]`. Locked `flowlab` still WNS −0.02 / 16 viol. |
| 8 | Professionalize Studio / FlowLab UI | **Substantial, leftover-named** | Home leftover above the fold (compact). Finish: Signoff / ECO above the GDS viewport. Variant compare: locked `flowlab` vs `eco_scratch`. Matrix default stays `flowlab`. |
| 9 | Docs: serious, not AI-portfolio | **Landed on course pages** | Root / Studio / course / results / signoff-matrix name leftover. Course guillemets removed from five course files. Frozen `arch_review.md` still has `«»`. |

---

## Live leftover (do not hide)

Educational STA golden is WNS ≥ −0.04 ns, so the timing pillar stays
`ok` while setup is still open at the course 0.46 ns clock.

| | Locked `flowlab` | Copy `eco_scratch` |
|---|---|---|
| OpenSTA WNS | −0.02 ns · TNS −0.14 · **16 viol** | −0.01 ns · TNS −0.01 · **1 viol** |
| Worst endpoint | register-to-register (era) | `resp_msg[14]` (output) |
| R2R | **VIOLATED** | **MET** (~+2.7 ps on `dpath.a_reg.out[15]`) |
| `period_min` | 0.48 ns era | 0.46 ns |
| LVS | match + leftover must-connect 2 (`DFF_X2`) | same |
| GDS DRC | 0 items · leftover no density / named ERC | same |
| Chip IR | 1.05 mV | 1.06 mV |
| Transient | 9.47 mV | 9.83 mV |
| IR meshes | `comparable: false` (5 meshes) | `comparable: false` (3 meshes) |
| `signoff_all` | four pillars `ok` | four pillars `ok` |

Shared cone on the copy: NAND2_X2 `_647_` drives `net42` =
`output42/A` (BUF_X1 → `resp_msg[14]`) **and** `_809_/A2` (NAND2_X4,
R2R). Repairing that cone regresses R2R.

---

## What landed (keep)

### Signoff and ECO

- LVS filter unused CDL, inject FILL from DEF, map wells to VDD/VSS,
  `blank_circuit` on empty FILL/TAP. `.lvs.ok` only on a real match.
- Two-process ECO apply (`learn/scripts/eco_repair.tcl` +
  `learn/scripts/run_eco.py`):
  1. `ECO_PHASE=sizeup` — read SPEF, `set_false_path -to [all_outputs]`,
     `repair_timing -setup -skip_buffering -sequence "sizeup,swap"`,
     `global_connect`, DPL, incremental GRT, `detailed_route`, RCX.
  2. `ECO_PHASE=buffer` — **no SPEF** (`ECO_SKIP_SPEF`).
     `estimate_parasitics -global_routing` before incremental GRT, then
     `repair_timing -sequence "buffer"`.
- SPEF + BufferMove in one OpenROAD session is **RSZ-0074**.
- `global_connect` after repair is required so new cells have VDD/VSS.
- Live copy: 29 buffers, R2R MET.
- `stamp_signoff_all.py` writes leftover setup, leftover no MCMM,
  leftover DRC deck, leftover must-connect, IR mesh ledger.
- `lib_corner_coverage.py` → `learn/sim/reports/lib_corner_coverage.json`
- `drc_deck_coverage.py` → `learn/sim/reports/drc_deck_coverage.json`

### Studio

- EcoPanel names I/O leftover vs R2R MET and the shared NAND2_X2 cone.
- `leftoverSetupOpenDetail` + `appendSetupLeftover` +
  `leftoverNamedBit()` (home does **not** dump the full `signoff_all`
  line).
- Finish: Signoff / ECO **above** the GDS viewport.
- Variant compare strip: locked `flowlab` vs `eco_scratch`.
- SignoffMatrix **stays default `flowlab`** so Run / Full signoff still
  maps to the locked variant. Do not switch the default to
  `eco_scratch` without remapping Run.
- Geometry pillar: antenna 300:1 · leftover no density / named ERC.
- Timing pillar: leftover no MCMM (`typical.lib` only).
- Recook of locked `gcd/flowlab` is HTTP 403 after `6_final.gds`.

### Docs (course pages)

- `README.md`, `studio/README.md`, `docs/course.md`, `docs/results.md`,
  `learn/reference/signoff-matrix.md` name leftover.
- Course guillemets removed from `learn/README.md`, `learn/EVIDENCE.md`,
  `learn/reference/gui-openroad.md`, `learn/reference/debug-playbook.md`,
  `learn/workbook/solutions.md`. Tests lock those five files.

---

## What is still missing

Two kinds. Do not put gated items on a build sprint. Full table:
[`learn/reference/gaps.md`](../learn/reference/gaps.md).

### License / PDK / SDC gated (will not close on this PDK)

| Leftover | Why it stays |
|---|---|
| Course **20% output delay** on `eco_scratch` (WNS −0.01 on `resp_msg[14]`) | Tutorial SDC (`clk_period` 0.46, `clk_io_pct` 0.2). Do not rewrite the SDC. |
| Locked `flowlab` R2R leftover (WNS −0.02, 16 viol) | Locked variant. Do not overwrite `results/.../gcd/flowlab/`. |
| LVS must-connect **2** on `DFF_X2` | Nangate split wells. Unpin / flatten already failed. |
| `VIA_*` flatten (`blank_circuit`) | Routing vias have no CDL. Do not invent devices. |
| Density / named ERC | Not in `FreePDK45.lydrc`. Do not invent rules. |
| MCMM | Single `typical.lib`. Extra corners need the full kit or a foundry PDK. |
| EM `em_checked` 0 | No foundry `emlimit`. Do not invent a limit. |
| IR meshes `comparable: false` | Gold / current_run / chip / vyges / system stay on their own meshes. |
| Official CCS liberty, StarRC / Raphael, board S-parameter, Magic+Netgen on FreePDK45, PrimeTime / Tempus / Voltus | License or wrong tool. |
| sky130 as the course PDK | Different PDK. Do not mix it into this course. |

### To-build that is already built

LVS match, ECO two-process apply, antenna check, DSE-as-proposer wall,
IR mesh ledger. See `gaps.md` “To build (or already built)”.

### Studio / docs polish that is **not** a leftover-free close

Further leftover-only captions that do not change the flow are not the
next job. Item 8 is leftover-named, not leftover-free. Item 9 is honest
on course pages; frozen `arch_review.md` still uses `«»` and must stay
frozen.

---

## Failed closes — do not retry

These were run live and do **not** close the I/O leftover without
regressing R2R or staying at WNS −0.01:

- `ECO_PHASE=io`
- BUF_X1 → BUF_X4 on `output42`
- RSZ `clone,split` (cloned a NAND4, not `_647_`)
- Manual clone of `_647_`
- I/O-only liberty swaps of `output42` to CLKBUF_X1/X2/X3 or BUF_X2

Default apply stays **two** OpenROAD processes. Do not add a third.
If BufferMove cannot legalize: `ECO_KEEP_SIZEUP`. If DRT-0206: restore
the source ODB (file copy). Never write `gcd/flowlab/`. Never call
`signoff_all` from apply.

---

## Locked invariants (keep)

- Three surfaces: Product / Lab / Course. Do not mix. Do not promote a
  lab result to a product win.
- Course stays **Nangate45**. Wrapper refuses `FLOW_VARIANT` in
  `{flowlab, learn, base}`.
- Do not restamp gold GCD Dynamic IR **45.298 mV**.
- Do not overwrite `results/.../gcd/flowlab/` or
  `learn/sim/dse/memory_aes.jsonl` row `febe6804241c`.
- Do not overwrite locked `gcd/flowlab/` artifacts. Live sha256 of
  `6_final.gds` is
  `439f5eba0de2abd61d6c14328c8ac4d966dee085e9c51687b8ee09182244bcb3`.
  ODB sha256
  `f691539f60f2f66f025108163819b827df43670a660f24362368d0ce56e62594`
  is also the baseline in `learn/dse/f6_finish.py`.
- No `if design ==` in tuner, space, score, coordinator, or transfer.
- No fake `.lvs.ok`. Kill by PID only.
- Krylov / MOR not on AES (~50–70k-R).

---

## Tests that still hold this close

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_signoff_honesty.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_eco.py
```

`test_eco.py` live close still requires leftover setup open
(`setup_open is True`). That is the contract, not a bug.

---

## What a later resume may do

Resume is a **new** goal, not a silent continuation of leftover-free.

Allowed without a new PDK / SDC:

- Keep leftovers named when reports or Studio drift.
- Product DSE on official netlists (not this course close).
- Lab IR / F4 work that does not restamp 45.298 or overwrite FlowLab.

Not allowed as “finishing this campaign”:

- Another LVS flatten / unpin on DFF_X2.
- Inventing `emlimit`, density rules, named ERC, or slow/fast liberty.
- Rewriting course SDC to hide the 20% output leftover.
- A third ECO apply phase, `ECO_PHASE=io`, or shared-cone clone.
- Switching SignoffMatrix default to `eco_scratch` without remapping Run.
- Mixing sky130 into the course.
- Rewriting frozen DSE plans after data.
