/** Shared FlowLab layout-studio catalog (no Node APIs — safe for client + server). */

export type LayoutPhaseId =
  | "rtl"
  | "synth"
  | "floorplan"
  | "pdn"
  | "place"
  | "cts"
  | "route"
  | "finish"
  | "pkg";

export type GalleryShot = {
  file: string;
  title: string;
  caption: string;
};

export type ComparePair = {
  id: string;
  label: string;
  left: { file: string; title: string };
  right: { file: string; title: string };
};

export type LayerSwatch = {
  id: string;
  name: string;
  color: string;
  role: string;
  /** Switch the viewport to this gui-shot (OpenROAD Display Control equivalent). */
  soloShot?: string;
};

export const PHASE_GALLERY: Record<LayoutPhaseId, GalleryShot[]> = {
  rtl: [],
  synth: [
    { file: "win_synth.png", title: "ODB synth", caption: "Die 0×0 — netlist, not layout" },
  ],
  floorplan: [
    { file: "03_pdn.png", title: "Die + PDN", caption: "VDD/VSS straps on floorplan" },
    { file: "win_floorplan.png", title: "GUI floorplan", caption: "OpenROAD window" },
    { file: "win_pdn.png", title: "GUI PDN", caption: "Display Control" },
    { file: "win_tapcell.png", title: "Tapcells", caption: "Well taps on rows" },
    { file: "win_anatomy_labeled.png", title: "GUI anatomy", caption: "Zones A–G of the window" },
  ],
  pdn: [
    { file: "03_pdn_labeled.png", title: "PDN labeled", caption: "VDD / VSS annotate" },
    { file: "03_pdn.png", title: "PDN", caption: "Straps metal" },
    { file: "win_pdn.png", title: "GUI PDN", caption: "OpenROAD window" },
  ],
  place: [
    { file: "05_place_dp.png", title: "Detailed place", caption: "Cells legalized on rows" },
    { file: "04_place_gp_labeled.png", title: "Global place", caption: "Before legalization" },
    { file: "04_place_gp.png", title: "GP", caption: "Global placement" },
    { file: "win_place_dp.png", title: "GUI DP", caption: "OpenROAD window" },
    { file: "win_place_gp.png", title: "GUI GP", caption: "Global place window" },
  ],
  cts: [
    { file: "06_cts.png", title: "Clock tree", caption: "CTS buffers on die" },
    { file: "win_cts.png", title: "GUI CTS", caption: "OpenROAD window" },
    { file: "orfs_cts_clock_tree.png", title: "Clock diagram", caption: "Report ORFS" },
    { file: "win_clock_filter.png", title: "Clock nets", caption: "Display Control filter" },
    { file: "orfs_cts_clock_layout.png", title: "Clock layout", caption: "Heatmap clock" },
  ],
  route: [
    { file: "08_route_labeled.png", title: "DRT labeled", caption: "M2 red · M3 green" },
    { file: "07_grt.png", title: "Global route", caption: "GRT guides (not final metal)" },
    { file: "win_layers_m2m3.png", title: "M2/M3 only", caption: "Isolated Display Control" },
    { file: "win_grt.png", title: "GUI GRT", caption: "Global congestion" },
    { file: "win_route.png", title: "GUI DRT", caption: "Detailed route window" },
    { file: "orfs_final_congestion.png", title: "Congestion", caption: "Heatmap ORFS" },
  ],
  finish: [
    { file: "09_final.png", title: "Final GDS", caption: "Signoff view" },
    { file: "win_final.png", title: "GUI final", caption: "OpenROAD window" },
    { file: "orfs_final_worst_path.png", title: "Worst path", caption: "Timing path" },
    { file: "orfs_final_clocks.png", title: "Clocks", caption: "Clock nets" },
    { file: "orfs_final_congestion.png", title: "Congestion", caption: "Heatmap" },
  ],
  pkg: [
    { file: "orfs_final_ir_drop.png", title: "IR drop", caption: "Post-finish heatmap" },
    { file: "09_final.png", title: "Final GDS", caption: "Complete layout" },
    { file: "orfs_final_worst_path.png", title: "Worst path", caption: "Timing" },
  ],
};

export const PHASE_COMPARE: Partial<Record<LayoutPhaseId, ComparePair[]>> = {
  floorplan: [
    {
      id: "pdn-place",
      label: "PDN ↔ Place",
      left: { file: "03_pdn.png", title: "Floorplan + PDN" },
      right: { file: "05_place_dp.png", title: "Placement" },
    },
  ],
  pdn: [
    {
      id: "pdn-place",
      label: "PDN ↔ Place",
      left: { file: "03_pdn_labeled.png", title: "PDN" },
      right: { file: "05_place_dp.png", title: "Placement" },
    },
  ],
  place: [
    {
      id: "place-route",
      label: "Place ↔ Route",
      left: { file: "05_place_dp.png", title: "Place" },
      right: { file: "08_route_labeled.png", title: "Route" },
    },
    {
      id: "gp-dp",
      label: "GP ↔ DP",
      left: { file: "04_place_gp.png", title: "Global place" },
      right: { file: "05_place_dp.png", title: "Detailed place" },
    },
  ],
  cts: [
    {
      id: "cts-route",
      label: "CTS ↔ Route",
      left: { file: "06_cts.png", title: "Clock tree" },
      right: { file: "08_route_labeled.png", title: "Detailed route" },
    },
  ],
  route: [
    {
      id: "grt-drt",
      label: "GRT ↔ DRT",
      left: { file: "07_grt.png", title: "Global route" },
      right: { file: "08_route_labeled.png", title: "Detailed route" },
    },
    {
      id: "place-route",
      label: "Place ↔ Route",
      left: { file: "05_place_dp.png", title: "Place" },
      right: { file: "08_route_labeled.png", title: "Route" },
    },
  ],
  finish: [
    {
      id: "route-final",
      label: "Route ↔ Final",
      left: { file: "08_route_labeled.png", title: "DRT" },
      right: { file: "09_final.png", title: "Finish" },
    },
  ],
  pkg: [
    {
      id: "gds-ir",
      label: "GDS ↔ IR",
      left: { file: "09_final.png", title: "Final GDS" },
      right: { file: "orfs_final_ir_drop.png", title: "IR drop" },
    },
  ],
};

export const PHASE_LAYERS: Partial<Record<LayoutPhaseId, LayerSwatch[]>> = {
  floorplan: [
    { id: "die", name: "Die", color: "#6e7681", role: "Chip outline" },
    { id: "rows", name: "Rows", color: "#3d4a5c", role: "Siti standard-cell" },
    { id: "m1", name: "Metal1", color: "#4b8bff", role: "Rail VDD/VSS followpin" },
    { id: "pdn", name: "PDN straps", color: "#e6c84a", role: "VDD/VSS su M4/M7" },
  ],
  pdn: [
    { id: "m1", name: "Metal1", color: "#4b8bff", role: "Followpin on rows" },
    { id: "m4", name: "Metal4", color: "#c8d44a", role: "Strap PDN verticali" },
    { id: "m7", name: "Metal7", color: "#f0883e", role: "Strap PDN superiori" },
  ],
  place: [
    { id: "cells", name: "Cells", color: "#58a6ff", role: "Legalized LEF boxes" },
    { id: "rows", name: "Rows", color: "#3d4a5c", role: "Placement alignment" },
    { id: "m1", name: "Metal1", color: "#4b8bff", role: "Pin + rail, not yet signal route" },
  ],
  cts: [
    { id: "clk", name: "Clock", color: "#f0883e", role: "Net di clock + buffer" },
    { id: "cells", name: "Cells", color: "#58a6ff", role: "Stdcell + clock inverters" },
    { id: "m2", name: "Metal2", color: "#e23d3d", role: "Spine clock (tipico)" },
  ],
  route: [
    { id: "m1", name: "Metal1", color: "#4b8bff", role: "Rail + pin locali" },
    {
      id: "m2",
      name: "Metal2",
      color: "#e23d3d",
      role: "Signal — red in GUI",
      soloShot: "win_layers_m2m3.png",
    },
    {
      id: "m3",
      name: "Metal3",
      color: "#3ecf4c",
      role: "Signal — green in GUI",
      soloShot: "win_layers_m2m3.png",
    },
    { id: "pdn", name: "PDN", color: "#e6c84a", role: "Power straps" },
    { id: "via", name: "Via", color: "#a371f7", role: "Tagli tra metal" },
  ],
  finish: [
    { id: "all", name: "All metal", color: "#58a6ff", role: "GDS composito" },
    {
      id: "m2m3",
      name: "M2/M3",
      color: "#e23d3d",
      role: "Signal layers",
      soloShot: "win_layers_m2m3.png",
    },
    { id: "clk", name: "Clock", color: "#f0883e", role: "Clock nets", soloShot: "orfs_final_clocks.png" },
  ],
  pkg: [
    { id: "ir", name: "IR drop", color: "#f85149", role: "Heatmap tensione" },
    { id: "gds", name: "GDS", color: "#58a6ff", role: "Layout finale", soloShot: "09_final.png" },
  ],
};
