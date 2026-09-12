# PDflow UI Workbench

## Purpose

PDflow uses a Linux-first application workbench for physical-design work. The
design or evidence view is the primary workspace. Navigation, provenance,
diagnostics and logs are available beside it without permanently consuming the
canvas.

The browser development route and the Tauri desktop shell use the same React
layout. The local Python agent remains the owner of native processes, artifact
resolution, report validity and resource isolation.

## Shell regions

The root shell has five regions:

1. The application navigation rail.
2. The runtime status strip and workspace context bar.
3. The central scrollable workspace.
4. The optional context inspector.
5. The optional runtime dock.

The shell fills the viewport. It does not impose a global max-width. Long-form
reference text applies its own readable measure, while operational surfaces use
the available width.

The navigation is 224 px when expanded and 56 px when compact. Viewports from
768 px through 1599 px use compact navigation by default. Below 768 px the
navigation becomes a drawer. The minimum certified desktop Tauri window is
980 × 680 is the target minimum; certification requires the viewport checks below.

The inspector starts closed and is 320 px wide when opened. It is bounded to
280–420 px. The runtime dock starts closed, opens at 220 px, and is bounded to
160 px and 35% of the available height. Layout preferences are versioned in
local storage and may be reset with the workspace layout reset action. Desktop
preferences are not reused as an always-open mobile drawer: below 768 px the
navigation is closed by default and is opened from the context bar as a drawer.
Between 768 and 1199 px the inspector overlays the workspace. The dock is
temporarily collapsed when the available height cannot preserve the viewer's
320 px minimum and its controls; the saved open preference is retained.

FlowLab also has a local focus mode. It hides the application rail, inspector
and runtime dock while retaining artifact identity, finish/candidate authority
and the essential viewer toolbar. `Esc` restores the previous layout.

Opening a panel is a UI operation only. It must not submit a job, regenerate a
preview or recalculate an inspection.

## Surface rules

### FlowLab

FlowLab is a design workbench. The selected physical artifact is displayed in
the main area, while controls and detailed diagnostics remain secondary.

The PNG preview is an honest preview of a saved artifact. Layer selection is
only presented as interactive when the selected viewer supports it. OpenROAD
and KLayout remain native tools launched through the local agent.

The finish artifact is always labelled FINISH · READ ONLY. Mutating actions
must use an isolated candidate. A saved candidate revision generates the
artifact event used to refresh the preview and invalidate dependent reports.
Unsaved native-tool state is never represented as a new geometry revision.

### Product

Product contains Summary, Checks and Layout views. It only displays current
invocation evidence and explicit same-invocation comparisons. A missing or
incompatible comparison is shown as unavailable; it is not converted into a
zero delta or historical baseline.

### Package

Package contains System PDN, Geometry, Connectivity and References views.
System PDN evidence is separate from Product signoff. A conceptual die-to-board
diagram is labelled as such and cannot be interpreted as measured package
geometry. Missing package artifacts or SPICE dependencies remain GAP.

### Lab

Lab contains Bench, DSE compare and Provenance views. The default Bench is the
standalone ASAP7 native workbench: it exposes the same RTL-to-GDS checkpoint
viewer, typed experiment profile and local-agent runner as the ASAP7 FlowLab
route. This keeps ASAP7 experiments in a full-width design workspace rather
than hiding them behind a secondary dashboard card. The older course bench is
still available explicitly with `/lab?track=course`.

Lab results are experimental proposals and never create a Product badge. Mesh,
oracle, activity and run provenance remain visible with the selected result.

### Tools

Tools contains Registry, Operations, Run and Results views. Only the selected
view is mounted. Stage and action query parameters remain compatible with
existing deep links. The runtime timeline is in the shared dock, so pages do
not mount independent high-frequency timelines.

## Runtime updates

The application shell owns the event stream. Surface components may request a
refresh, but they must not create a second global event stream. Runtime events
are coalesced before React state is updated. The timeline uses event-triggered
refreshes and a low-frequency recovery poll.

Complete logs remain on disk under the agent resource policy. The browser
keeps at most 2,000 lines or 512 KiB in the FlowLab interactive buffer (the
Tools console uses a stricter 32 KiB tail) and mounts at most 200 FlowLab log
rows at once. Report pages expose structured status, provenance and results
first; raw JSON is an explicit secondary action.
Agent logs can be downloaded through `GET /api/jobs/:jobId/log`. The response
streams a file snapshot without loading the complete log into React or Next
memory. Restart the local agent after upgrading to enable this endpoint.

Opening `Inspect`, `Results`, a report, a stage tab or a native-tool bridge is
read-only. These views use `GET /api/inspections`, artifact metadata and
existing reports. A process is submitted only after the user presses an
explicit Run, Recalculate or native launch action. `#signoff` selects the
Finish signoff tab; Tools deep links such as
`/tools?stage=floorplan&tab=results&action=floorplan` select the requested view
without starting a job.

## ASAP7 standalone entry points

Use these routes when working on the native ASAP7 track:

- `/flow?platform=asap7&phase=finish` opens the full-width RTL-to-GDS
  workbench. Add a validated `variant=lab_asap7_*` to select a specific live
  experiment.
- `/lab` opens the same ASAP7 workbench as the primary Lab Bench. Use
  `/lab?tab=dse` for experiment comparison and `/lab?track=course` only for
  the legacy Nangate45 teaching bench.
- `/pkg` opens the ASAP7 Package/System PDN workspace by default. Pass
  `variant=lab_asap7_*` to keep the package analysis on the same finish.

All three native surfaces share the application viewport, but the design
canvas remains the dominant region. OpenROAD and KLayout are external native
windows; the UI updates only after a recognized candidate artifact is saved.
The finish remains read-only and no panel opening starts a flow.

## Accessibility

The workbench must remain keyboard usable. Panel resize separators expose
role=separator and support ArrowLeft, ArrowRight, Home and End. Focus
indicators remain visible. Status is communicated by text and not by colour
alone. Reduced-motion preferences disable non-essential transitions.

At narrow widths, tables and code scroll locally. The page itself must not
create horizontal overflow. At 200% zoom, the primary action and selected
design view remain reachable.

## UI verification

Run the following from studio/:

~~~bash
./node-runtime/node node_modules/typescript/bin/tsc --noEmit --pretty false
./node-runtime/node node_modules/eslint/bin/eslint.js src --max-warnings=0
./node-runtime/node tests/preflight-isolation.cjs
../scripts/run_resource_job.sh studio-next-build ./node-runtime/node node_modules/next/dist/bin/next build --webpack
~~~

Exercise the browser route at 980 × 680, 1280 × 720, 1440 × 960,
1920 × 1080, 2560 × 1440 and 3440 × 1440. Repeat at 390 × 844 and 768 ×
1024. Check the shell with the inspector and dock independently and together.

The primary native smoke path is:

1. Open FlowLab and select a physical phase.
2. Verify the artifact id, authority, revision and hash.
3. Open OpenROAD through the native bridge.
4. Save only to a candidate.
5. Confirm the artifact event, refreshed revision and stale-report state.
6. Open KLayout for the saved GDS and inspect the current DRC/LVS evidence.
7. Verify that the canonical finish hash is unchanged.

The absence of a tool, artifact or report is a tested state. It must be
rendered as GAP, NOT_RUN, FAIL or STALE according to the agent contract, never
as a successful placeholder.

Missing-input and lock tests use disposable fixture roots. The Studio API
smoke suite must never rename canonical ODB/netlist files or replace a live
application lock to manufacture a dependency failure.
