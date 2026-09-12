# Course audit

The audit checks structure and live-data discipline rather than fixed metric
values.

```bash
./scripts/test_course.sh
./scripts/test_all_phases.sh
python3 learn/scripts/test_signoff_honesty.py
```

Required surfaces:

- eight lesson directories, each with README, LAB, and `run.sh`;
- GUI atlas, Tcl walkthroughs, glossary, workbook, and live-analysis contract;
- current signoff scripts and report readers;
- Studio routes for FlowLab, lab, package, tools, jobs, and inspection.

Reviewers should verify that no code reads a committed campaign row or a
fixed metric to fill a current report. They should also verify that missing
tools are represented as `GAP` and that current reports retain their source
paths and fingerprints.
