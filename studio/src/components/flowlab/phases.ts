import { LONG_ACTIONS } from "@/lib/actions";
import type { Phase } from "./types";

export { LONG_ACTIONS };

export const PHASES: Phase[] = [
  {
    id: "rtl",
    label: "RTL",
    title: "Write and simulate RTL",
    action: "rtl_sim",
    hint: "Verilog · Icarus",
    help: "Edit the Verilog design, autosave, then launch behavioral simulation. Gate-level sim (gate_sim) after finish dumps the name-join VCD.",
    tool: "Icarus Verilog",
    icon: "code",
    estTime: "~5 s",
  },
  {
    id: "synth",
    label: "Synth",
    title: "Logic synthesis",
    action: "synth",
    hint: "Yosys · ABC",
    help: "Transform RTL into netlist and initial physical database. Choose SDC constraints and ABC area/delay mode.",
    tool: "Yosys + OpenROAD",
    icon: "cpu",
    estTime: "~30 s",
  },
  {
    id: "floorplan",
    label: "Floorplan",
    title: "Floorplan and die",
    action: "floorplan",
    hint: "Die · IO · tap",
    help: "Defines the die, IO margins, and generates the PDN (pdngen). Core utilization affects final chip area.",
    tool: "OpenROAD init_floorplan + pdngen",
    icon: "grid",
    estTime: "~20 s",
  },
  {
    id: "pdn",
    label: "PDN",
    title: "Chip PDN analysis",
    action: "gridcheck",
    hint: "check_power_grid",
    help: "Verify VDD/VSS connectivity (PSM-0040). After finish: optional chip IR on SPICE mesh (write_pg_spice). See power chain.",
    tool: "OpenROAD check_power_grid",
    icon: "zap",
    estTime: "~5 s",
  },
  {
    id: "place",
    label: "Place",
    title: "Placement",
    action: "place",
    hint: "GP · DP",
    help: "Global and detailed placement of standard cells. Addon density controls free space between rows.",
    tool: "OpenROAD global/detail place",
    icon: "box",
    estTime: "~45 s",
  },
  {
    id: "cts",
    label: "CTS",
    title: "Clock tree synthesis",
    action: "cts",
    hint: "Skew · TNS",
    help: "Builds the clock tree and repairs post-placement timing. May take several minutes.",
    tool: "OpenROAD CTS + repair",
    icon: "branch",
    estTime: "2–5 min",
  },
  {
    id: "route",
    label: "Route",
    title: "Routing",
    action: "route",
    hint: "Global · Detail",
    help: "Routes signals on metal layers. Longest phase in the flow — confirm before starting.",
    tool: "OpenROAD global/detail route",
    icon: "route",
    estTime: "3–8 min",
  },
  {
    id: "finish",
    label: "GDSII",
    title: "Finish and signoff",
    action: "finish",
    hint: "GDS · SPEF",
    help: "Generates GDSII, SPEF, final netlist, and reports. After finish: signoff matrix (STA/DRC/LVS/power) vs golden-gcd.json — actions sta_signoff, sta_ir_aware … signoff_all. System PDN / Phase 2 stay on /pkg.",
    tool: "OpenROAD finish + KLayout",
    icon: "layers",
    estTime: "1–3 min",
  },
];

export const PHASE_IDS = PHASES.map((p) => p.id);
/** RTL → finish. System PDN lives on /pkg, not as a FlowLab phase. */
export const CLOSE_PHASES = PHASES;
export const ANALYSIS_PHASES = new Set(["pdn"]);
