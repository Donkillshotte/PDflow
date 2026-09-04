/**
 * Client-safe leftover labels. Ids match learn/signoff/leftover_catalog.json.
 * Gated leftovers stay named; they are not closed on Nangate45.
 */

export type LeftoverTone = "leftover" | "locked" | "built" | "gap";

export type LeftoverChipDef = {
  id: string;
  label: string;
  tone: LeftoverTone;
  needles: string[];
};

export const LEFTOVER_CHIPS: LeftoverChipDef[] = [
  {
    id: "setup_open_flowlab",
    label: "leftover setup open (flowlab)",
    tone: "leftover",
    needles: ["leftover setup open"],
  },
  {
    id: "setup_open_eco_io",
    label: "leftover I/O (resp_msg[14])",
    tone: "leftover",
    needles: ["resp_msg[14]", "course output delay"],
  },
  {
    id: "must_connect_dff_x2",
    label: "leftover must-connect 2 (DFF_X2)",
    tone: "leftover",
    needles: ["leftover must-connect", "DFF_X2"],
  },
  {
    id: "via_flatten",
    label: "leftover VIA_* flatten",
    tone: "leftover",
    needles: ["VIA_* flatten", "blank_circuit"],
  },
  {
    id: "no_mcmm",
    label: "leftover no MCMM",
    tone: "leftover",
    needles: ["leftover no MCMM"],
  },
  {
    id: "no_density_erc",
    label: "leftover no density / ERC",
    tone: "leftover",
    needles: ["leftover no density", "named ERC"],
  },
  {
    id: "em_checked_0",
    label: "leftover em_checked 0",
    tone: "leftover",
    needles: ["em_checked 0", "no emlimit"],
  },
  {
    id: "ir_meshes_incomparable",
    label: "IR meshes not comparable",
    tone: "leftover",
    needles: ["IR meshes not comparable"],
  },
  {
    id: "no_ccs_official",
    label: "official liberty NLDM",
    tone: "leftover",
    needles: ["official Nangate liberty stays NLDM"],
  },
  {
    id: "no_starrc",
    label: "StarRC / Raphael GAP",
    tone: "gap",
    needles: ["Raphael GAP", "not StarRC"],
  },
  {
    id: "no_sparam",
    label: "leftover no Touchstone",
    tone: "leftover",
    needles: ["no Touchstone"],
  },
  {
    id: "no_magic_netgen",
    label: "Magic / Netgen GAP",
    tone: "gap",
    needles: ["no FreePDK45 .tech", "not installed"],
  },
  {
    id: "no_sky130_course",
    label: "Nangate45 only",
    tone: "locked",
    needles: ["Nangate45 only", "Different PDK"],
  },
  {
    id: "gold_ir_locked",
    label: "gold IR 45.298 locked",
    tone: "locked",
    needles: ["45.298"],
  },
  {
    id: "course_0_8",
    label: "course 0/8",
    tone: "locked",
    needles: ["0/8"],
  },
  {
    id: "aes_row_locked",
    label: "AES row locked",
    tone: "locked",
    needles: ["febe6804241c"],
  },
  {
    id: "antenna_300",
    label: "antenna 300:1",
    tone: "built",
    needles: ["antenna 300:1"],
  },
  {
    id: "lvs_match",
    label: "KLayout match",
    tone: "built",
    needles: ["KLayout match", "CONGRATULATIONS"],
  },
  {
    id: "eco_two_process",
    label: "ECO two-process apply",
    tone: "built",
    needles: ["two OpenROAD processes", "BufferMove without SPEF"],
  },
  {
    id: "dse_proposer",
    label: "DSE proposer only",
    tone: "built",
    needles: ["Proposer only", "does not run signoff_all"],
  },
  {
    id: "gap_class",
    label: "license vs to-build",
    tone: "built",
    needles: ["license/PDK gated", "to-build"],
  },
  {
    id: "ir_ledger",
    label: "IR mesh ledger",
    tone: "built",
    needles: ["ir_mesh_ledger"],
  },
  {
    id: "ccs_sidecar",
    label: "PTM CCS sidecar",
    tone: "built",
    needles: ["PTM", "sidecar"],
  },
];

const BY_ID = new Map(LEFTOVER_CHIPS.map((c) => [c.id, c]));

export function leftoverLabel(id: string): string {
  return BY_ID.get(id)?.label ?? id.replaceAll("_", " ");
}

export function leftoverTone(id: string): LeftoverTone {
  return BY_ID.get(id)?.tone ?? "leftover";
}

export function leftoverIdsFromText(text: string | null | undefined): string[] {
  if (!text) return [];
  return LEFTOVER_CHIPS.filter((c) =>
    c.needles.some((needle) => text.includes(needle)),
  ).map((c) => c.id);
}

export function leftoverNamedIds(ids: string[] | undefined): string[] {
  if (!ids?.length) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of ids) {
    const tone = leftoverTone(id);
    if (tone !== "leftover" && tone !== "locked" && tone !== "gap") continue;
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function hookVisualState(
  ok: boolean,
  leftoverIds?: string[],
): "ok" | "leftover" | "gap" {
  if (!ok) return "gap";
  if (leftoverNamedIds(leftoverIds).length) return "leftover";
  return "ok";
}
