# Course and Studio

The course teaches RTL → GDS with OpenROAD/ORFS on the Nangate45 educational
flow. Studio provides the same workbench through a local app-like UI.

```bash
./scripts/learn_physical_design.sh --check
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --deep --lesson 03-floorplan
./scripts/test_course.sh
./scripts/run_studio.sh
```

Lessons 00–07 follow Explain → Run → Inspect → Verify → Reflect. Reports and
metrics are copied from the current local run into the workbook; the course
does not prescribe a fixed expected QoR value.

FlowLab exposes live phases at `/flow`; the lab and package surfaces remain
separate at `/lab` and `/pkg`. Optional signoff steps may be unavailable when
their engine or PDK input is absent, and the UI shows that state directly.

For the full map see [`../learn/README.md`](../learn/README.md) and
[`../learn/reference/live-analysis.md`](../learn/reference/live-analysis.md).
