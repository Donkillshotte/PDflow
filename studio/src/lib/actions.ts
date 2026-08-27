/** Single source for action timing / confirmation flags (Studio + FlowLab). */

export const LONG_ACTIONS = new Set([
  "cts",
  "route",
  "finish",
  "test_course",
  "klayout_drc",
  "power_chain",
  "chip_pdn_ir",
]);

/** Actions that may exceed 5 minutes — extended SSE timeout. */
export const EXTENDED_TIMEOUT_ACTIONS = new Set([
  "finish",
  "route",
  "test_course",
  "klayout_drc",
  "power_chain",
  "chip_pdn_ir",
]);

export function defaultActionTimeoutMs(action: string): number {
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
  "chip_pdn_ir",
  "system_pdn",
  "export_spice_lab",
  "power_chain",
] as const;

export type PowerAction = (typeof POWER_ACTIONS)[number];

export function isPowerAction(action: string): action is PowerAction {
  return (POWER_ACTIONS as readonly string[]).includes(action);
}
