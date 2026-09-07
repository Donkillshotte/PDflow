# ASAP7 research (investigation)

Living note. Not a frozen DSE plan. Not a course switch.

Question: ASAP7 looks like the best open kit for *our* research.
Is that true, and which open-source projects actually enlarge it?

**Answer: yes for Lab / EDA / FinFET research. No as a replacement
for the Nangate45 course or product campaign.** ASAP7 is the strongest
*predictive* open PDK in this tree (CCS, corners, multi-VT, FinFET
BEOL). It is not manufacturable. Do not migrate the course. Do not
promote an ASAP7 finish to a product win. Do not restamp gold
Dynamic IR **45.298 mV**. Do not overwrite `nangate45/gcd/flowlab`.

Checked on disk in this tree (2026-09-05). No ASAP7 `make finish`
was run for this note.

---

## What ASAP7 is

ASAP7 is a **predictive 7 nm FinFET** PDK from ASU (Lawrence Clark)
with ARM Research (2016). BSD-3. Official line from ASU: academic
and research aid only; designs are **not manufacturable**. No foundry
sign-off, no MPW, no Tiny Tapeout.

Paper to cite if we publish on it:

L. T. Clark et al., "ASAP7: A 7-nm finFET predictive process design
kit," *Microelectronics Journal*, vol. 53, pp. 105-115, Jul. 2016.

Umbrella repo: https://github.com/The-OpenROAD-Project/asap7
ASU page: https://asap.asu.edu/

This ORFS tree ships a **slim pack** at
`tools/OpenROAD-flow-scripts/flow/platforms/asap7/` (PDK 1.7,
7.5-track cells v28). That is enough to run digital P&R. It is not
the full Calibre / Virtuoso / HSpice kit.

SEE_FULL_FILE_AT_PR1_HEAD_BLOB_ace66203
