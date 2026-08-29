/** Signoff actions, timeouts, and registry helpers. */

export const SIGNOFF_ACTIONS = [
  "sta_signoff",
  "drc_signoff",
  "klayout_lvs",
  "power_signoff",
  "signoff_all",
] as const;

/** Fase 2 signoff / packaging actions (post-finish). */
export const PHASE2_SIGNOFF_ACTIONS = [
  "thermal_signoff",
  "pkg_bump",
  "pkg_rdl",
  "pkg_signoff",
  "signoff_phase2",
] as const;

export type Phase2SignoffAction = (typeof PHASE2_SIGNOFF_ACTIONS)[number];

export function isPhase2SignoffAction(action: string): action is Phase2SignoffAction {
  return (PHASE2_SIGNOFF_ACTIONS as readonly string[]).includes(action);
}

export type SignoffAction = (typeof SIGNOFF_ACTIONS)[number];

export function isSignoffAction(action: string): action is SignoffAction {
  return (SIGNOFF_ACTIONS as readonly string[]).includes(action);
}

export const LONG_ACTIONS = new Set([
  "cts",
  "route",
  "finish",
  "test_course",
  "klayout_drc",
  "klayout_lvs",
  "drc_signoff",
  "power_chain",
  "chip_pdn_ir",
  "power_signoff",
  "signoff_all",
  "thermal_signoff",
  "pkg_signoff",
  "signoff_phase2",
]);

/** Actions that may exceed 5 minutes — extended SSE timeout. */
export const EXTENDED_TIMEOUT_ACTIONS = new Set([
  "finish",
  "route",
  "test_course",
  "klayout_drc",
  "klayout_lvs",
  "drc_signoff",
  "power_chain",
  "chip_pdn_ir",
  "power_signoff",
  "signoff_all",
  "pkg_signoff",
  "signoff_phase2",
  "tool_matrix",
]);

export function defaultActionTimeoutMs(action: string): number {
  if (action === "signoff_all") return 1_200_000;
  return EXTENDED_TIMEOUT_ACTIONS.has(action) ? 900_000 : 300_000;
}

export function isLongAction(action: string): boolean {
  return LONG_ACTIONS.has(action);
}

/** Default FLOW_VARIANT for learn/scripts when env unset. */
export const DEFAULT_FLOW_VARIANT = "flowlab";

/** Power-chain script actions (post-finish analysis). */
export const POWER_ACTIONS = [
  "activity_power",
  "vectorless",
  "chip_pdn_ir",
  "vyges_em_ir",
  "dynamic_ir",
  "system_pdn",
  "export_spice_lab",
  "power_chain",
] as const;

export type PowerAction = (typeof POWER_ACTIONS)[number];

export function isPowerAction(action: string): action is PowerAction {
  return (POWER_ACTIONS as readonly string[]).includes(action);
}

/** Formal / PEX / tool-matrix actions (RTL or post-finish). */
export const TOOL_MATRIX_ACTIONS = [
  "yosys_equiv",
  "formal_gcd",
  "openrcx_report",
  "analytical_pex",
  "layout_tools",
  "spice_engines",
  "tool_matrix",
] as const;

export type ToolMatrixAction = (typeof TOOL_MATRIX_ACTIONS)[number];

export function isToolMatrixAction(action: string): action is ToolMatrixAction {
  return (TOOL_MATRIX_ACTIONS as readonly string[]).includes(action);
}

/** All post-finish analysis actions (power + signoff + fase 2 + tool matrix). */
export const POST_FINISH_ACTIONS = [
  ...POWER_ACTIONS,
  ...SIGNOFF_ACTIONS,
  ...PHASE2_SIGNOFF_ACTIONS,
  ...TOOL_MATRIX_ACTIONS,
] as const;
