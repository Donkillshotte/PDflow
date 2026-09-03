# Social preview (GitHub · LinkedIn)

Use these assets when sharing **PDflow** on LinkedIn or GitHub.

## GitHub repository social preview

1. Open **Settings → General → Social preview** on `Donkillshotte/PDflow`.
2. Upload [`docs/assets/social-preview.png`](assets/social-preview.png) (1280×640 minimum recommended; source is 1600×900).
3. Save. Links to the repo will show the FlowLab hero instead of a generic card.

The README hero uses the same image family:
[`studio/docs/images/flowlab/flowlab-pro-hero.png`](../studio/docs/images/flowlab/flowlab-pro-hero.png).

## LinkedIn post checklist

Suggested one-liner:

> Open-source RTL→GDS on OpenROAD with **honest signoff**: STA/DRC/power pass, LVS labeled FAIL, full gate-VCD → chip IR → package PDN chain, and a written product win rule. Not a foundry deck — educational Nangate45.

Link: `https://github.com/Donkillshotte/PDflow`

Attach one screenshot from [`studio/docs/images/flowlab/`](../studio/docs/images/flowlab/) or the social preview PNG.

## Pin these paths for reviewers

| What to open | Path |
|---|---|
| Homepage story | [README.md](../README.md) |
| Live WORKS / FAIL / GAP | [suite-status.md](../learn/reference/suite-status.md) |
| Win / lose discipline | [win_rule.py](../learn/dse/win_rule.py) · [results.md](results.md) |
| FlowLab UI | `./scripts/run_studio.sh` → `/flow` |
| Dynamic IR heatmap | [dynamic_ir_flowlab.svg](../learn/sim/reports/dynamic_ir_flowlab.svg) |

## Do not claim on social

- Foundry / PrimeTime / Tempus / Voltus sign-off
- LVS clean (it is an honest **FAIL** on FreePDK45 GCD)
- Tapeout-ready C4 bumps (dummy RDL only)
- Course **8/8** unless you actually completed the lessons
