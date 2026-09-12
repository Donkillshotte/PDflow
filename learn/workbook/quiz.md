# Quiz

Answer from the current logs and the live-analysis contract.

## GUI

1. Which panel controls visible layers?
2. Which artifact is loaded into the layout canvas?
3. How do you distinguish global from detailed placement?
4. What evidence belongs in the inspector for a selected net?
5. Why can a native Qt window not be shown in an HTTP preview?
6. Which current report confirms that the view is not stale?
7. How do you record a missing optional engine?

## Flow

8. What does Yosys produce?
9. Why does placement make wire delay visible?
10. What does CTS distribute?
11. What is the role of SPEF?
12. Why are DRC and LVS separate checks?
13. What does `write_pg_spice` identify?
14. Why must activity carry a scenario id?
15. What does `GAP` mean?

## Data integrity

16. What fields establish a comparable result?
17. What should happen when the report is missing a metric?
18. Can a chip mesh be compared directly with an on-die mesh?
19. Where should transient DSE memory be written?
20. What does the UI do after a job finishes?

## Reflection

21. Name one observation from your current finish report.
22. Name one limitation of the selected PDK or engine.
23. Which command would you rerun after changing the SDC?
24. Which source file would you inspect before changing a Tcl stage?
25. Why is a green process exit not enough for signoff?

Discuss answers with the current report paths, not with a preset result.

## Quiz GUI — evidence rubric

For questions 1–7, attach one screenshot or viewer capture and one artifact
path. The capture should identify the phase, variant, and selected ODB. The
artifact path should be copied from the current Studio card or command log.

For questions 8–15, cite the command that produced the log and name the
report field that supports the answer. If an optional tool is absent, answer
with `GAP` and include the reported reason.

For questions 16–20, list the run id and fingerprints before writing a delta.
If a fingerprint is missing or incompatible, explain why the comparison is
not available instead of filling the cell with zero.

For questions 21–25, use one current finish or signoff report. Include a
short excerpt of the status and the path to the complete file. A green shell
exit is only evidence that the process returned; it is not evidence that all
signoff pillars completed.

The instructor can reproduce the submission by running the command in the
workbook, opening the named artifact in the app, and refreshing the phase
panel. The expected outcome is an auditable observation, not a fixed number.

Use the following submission labels: `READY` for a completed current check,
`GAP` for an unavailable dependency, `FAIL` for a failed command, and
`REFUSED` for a safety or contract rejection. Include one sentence explaining
the label and one path that lets another student reproduce it.
