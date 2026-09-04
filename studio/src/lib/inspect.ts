import { spawnSync } from "child_process";
import fs from "fs";
import path from "path";
import { REPO_ROOT } from "./course";
import { preferredResultsVariant, resultsDir } from "./open";

const FLOW = () => path.join(REPO_ROOT, "tools/OpenROAD-flow-scripts/flow");
const LIB = () =>
  path.join(FLOW(), "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib");
const SDC = () =>
  path.join(FLOW(), "designs/nangate45/gcd-tutorial/constraint.sdc");

export type OdbStats = {
  design: string;
  instances: number;
  nets: number;
  dieDbu: { dx: number; dy: number };
  artifact: string;
};

export type StaSummary = {
  source: string;
  wns?: string;
  tns?: string;
  worstSlack?: string;
  paths: { endpoint: string; slack: string; status: string }[];
  jsonPaths?: number;
};

export type YosysStat = {
  cells?: string;
  area?: string;
  dff?: string;
  rawHits: string[];
};

export type StageInspect = {
  stage: string;
  odb: OdbStats | null;
  sta: StaSummary | null;
  yosys: YosysStat | null;
  hooks: { id: string; label: string; detail: string }[];
  variant?: string;
};

const STAGE_PRIMARY_ODB: Record<string, string> = {
  synth: "1_synth.odb",
  floorplan: "2_floorplan.odb",
  pdn: "2_4_floorplan_pdn.odb",
  place: "3_place.odb",
  cts: "4_cts.odb",
  route: "5_route.odb",
  finish: "6_final.odb",
};

const STAGE_NETLIST: Record<string, string | null> = {
  synth: "1_2_yosys.v",
  floorplan: "1_2_yosys.v",
  pdn: "1_2_yosys.v",
  place: "1_2_yosys.v",
  cts: null,
  route: null,
  finish: "6_final.v",
};

function runCapture(
  cmd: string,
  args: string[],
  opts: { cwd?: string; env?: NodeJS.ProcessEnv; input?: string; timeoutMs?: number },
) {
  return spawnSync(cmd, args, {
    cwd: opts.cwd,
    env: opts.env ?? process.env,
    input: opts.input,
    encoding: "utf8",
    timeout: opts.timeoutMs ?? 60_000,
    maxBuffer: 8 * 1024 * 1024,
  });
}

export function inspectOdb(
  artifact: string,
  variant: string = preferredResultsVariant(),
): OdbStats | null {
  const abs = path.join(resultsDir(variant), artifact);
  if (!fs.existsSync(abs)) return null;
  const py = `
import odb
db = odb.dbDatabase.create()
odb.read_db(db, ${JSON.stringify(abs)})
chip = db.getChip()
block = chip.getBlock()
die = block.getDieArea()
print("DESIGN", block.getName())
print("INSTS", len(block.getInsts()))
print("NETS", len(block.getNets()))
print("DIE", die.dx(), die.dy())
`;
  const r = runCapture("openroad", ["-python", "-no_init", "-exit"], {
    input: py,
    timeoutMs: 45_000,
  });
  const out = `${r.stdout || ""}\n${r.stderr || ""}`;
  const design = out.match(/DESIGN\s+(\S+)/)?.[1];
  const insts = Number(out.match(/INSTS\s+(\d+)/)?.[1]);
  const nets = Number(out.match(/NETS\s+(\d+)/)?.[1]);
  const die = out.match(/DIE\s+(\d+)\s+(\d+)/);
  if (!design || !Number.isFinite(insts)) return null;
  return {
    design,
    instances: insts,
    nets: Number.isFinite(nets) ? nets : 0,
    dieDbu: { dx: Number(die?.[1] || 0), dy: Number(die?.[2] || 0) },
    artifact,
  };
}

export function inspectSta(opts: {
  verilog?: string;
  spef?: string;
  label: string;
  variant?: string;
}): StaSummary | null {
  const variant = opts.variant ?? preferredResultsVariant();
  const v = opts.verilog ? path.join(resultsDir(variant), opts.verilog) : null;
  if (!v || !fs.existsSync(v)) return null;
  if (!fs.existsSync(LIB()) || !fs.existsSync(SDC())) return null;

  const spefAbs = opts.spef ? path.join(resultsDir(variant), opts.spef) : null;
  const spefLine =
    spefAbs && fs.existsSync(spefAbs) ? `read_spef ${spefAbs}` : "";

  const script = `
read_liberty ${LIB()}
read_verilog ${v}
link_design gcd
read_sdc ${SDC()}
${spefLine}
report_wns
report_tns
report_worst_slack -max
report_checks -format end -group_path_count 5
report_checks -format json -group_path_count 3 > /tmp/studio-sta-checks.json
`;
  const r = runCapture("sta", ["-no_init", "-exit"], {
    cwd: FLOW(),
    input: script,
    timeoutMs: 90_000,
  });
  const out = `${r.stdout || ""}\n${r.stderr || ""}`;
  const wns = out.match(/wns max\s+([-\d.]+)/)?.[1];
  const tns = out.match(/tns max\s+([-\d.]+)/)?.[1];
  const worstSlack = out.match(/worst slack max\s+([-\d.]+)/)?.[1];
  const paths: StaSummary["paths"] = [];
  for (const line of out.split("\n")) {
    const m = line.match(
      /^(\S+)\s+\([^)]+\)\s+[\d.]+\s+[\d.]+\s+([-\d.]+)\s+\((MET|VIOLATED)\)/,
    );
    if (m) paths.push({ endpoint: m[1], slack: m[2], status: m[3] });
  }
  let jsonPaths: number | undefined;
  try {
    const j = JSON.parse(fs.readFileSync("/tmp/studio-sta-checks.json", "utf8"));
    jsonPaths = Array.isArray(j.checks) ? j.checks.length : undefined;
  } catch {
    /* ignore */
  }
  return {
    source: opts.label,
    wns,
    tns,
    worstSlack,
    paths: paths.slice(0, 5),
    jsonPaths,
  };
}

export function inspectYosys(
  verilogRel: string,
  variant: string = preferredResultsVariant(),
): YosysStat | null {
  const abs = path.join(resultsDir(variant), verilogRel);
  if (!fs.existsSync(abs)) return null;
  const r = runCapture(
    "yosys",
    ["-Q", "-p", `read_verilog ${abs}; hierarchy -top gcd; stat`],
    { timeoutMs: 45_000 },
  );
  const out = `${r.stdout || ""}\n${r.stderr || ""}`;
  const hits: string[] = [];
  for (const line of out.split("\n")) {
    if (/Number of cells|Chip area|DFF_X1|NAND2_X1|AND2_X1|\d+\s+cells/i.test(line)) {
      hits.push(line.trim().slice(0, 160));
    }
  }
  return {
    cells: out.match(/^\s*(\d+)\s+cells\s*$/m)?.[1] ?? out.match(/Number of cells:\s*(\d+)/i)?.[1],
    area: out.match(/Chip area[^:]*:\s*([\d.]+)/i)?.[1],
    dff: out.match(/^\s*(\d+)\s+DFF_X1/m)?.[1],
    rawHits: hits.slice(0, 12),
  };
}

export function inspectStage(
  stage: string,
  variant: string = preferredResultsVariant(),
): StageInspect {
  const odbName = STAGE_PRIMARY_ODB[stage];
  const netlist = STAGE_NETLIST[stage] ?? null;
  const odb = odbName ? inspectOdb(odbName, variant) : null;

  let sta: StaSummary | null = null;
  if (stage === "finish") {
    sta = inspectSta({
      verilog: "6_final.v",
      spef: "6_final.spef",
      label: "OpenSTA · 6_final.v + SPEF",
      variant,
    });
  } else if (netlist) {
    sta = inspectSta({
      verilog: netlist,
      label: `OpenSTA · ${netlist} (ideal / no parasitics)`,
      variant,
    });
  }

  const yosys =
    stage === "synth" || stage === "floorplan"
      ? inspectYosys("1_2_yosys.v", variant)
      : null;

  const hooks = [
    {
      id: "or-web",
      label: "OpenROAD -web",
      detail: "Viewer HTML+WebSocket (Studio /viewer)",
    },
    {
      id: "or-gui",
      label: "OpenROAD -gui",
      detail: "Qt Desktop via /api/open",
    },
    {
      id: "or-python",
      label: "OpenROAD -python + odb",
      detail: "inst/net/die count from .odb",
    },
    {
      id: "or-metrics",
      label: "OpenROAD -metrics JSON",
      detail: "Flow metrics in JSON",
    },
    {
      id: "gridcheck",
      label: "check_power_grid",
      detail: "learn/scripts/run_gridcheck.sh · Studio gridcheck action",
    },
    {
      id: "activity",
      label: "set_power_activity / VCD",
      detail: "run_activity_power.sh · gate VCD name-join (read_vcd)",
    },
    {
      id: "vectorless",
      label: "Vectorless vs dynamic IR",
      detail: "run_vectorless.sh · Najm 1994 + Kouroussis DAC 2003",
    },
    {
      id: "vyges-em-ir",
      label: "vyges-em-ir (engine)",
      detail: "run_vyges_em_ir.sh · CG + backward Euler on write_pg_spice",
    },
    {
      id: "dynamic-ir",
      label: "Dynamic IR I(t)",
      detail: "run_dynamic_ir.sh · STA t50 + A DirectLU current_run + B SA-AMG + heatmap",
    },
    {
      id: "yosys-equiv",
      label: "Yosys equiv",
      detail: "run_yosys_equiv.sh · RTL ↔ synth",
    },
    {
      id: "formal",
      label: "Yosys SAT formal",
      detail: "run_formal_gcd.sh · reset |-> !resp_val",
    },
    {
      id: "openrcx",
      label: "OpenRCX SPEF",
      detail: "6_final.spef · rcx_patterns.rules",
    },
    {
      id: "sta-json",
      label: "OpenSTA report_checks -format json",
      detail: "Structured path timing",
    },
    {
      id: "yosys-stat",
      label: "Yosys stat",
      detail: "Cells/area on netlist",
    },
    {
      id: "rtl-sim",
      label: "Icarus RTL sim",
      detail: "learn/scripts/run_rtl_sim.sh",
    },
    {
      id: "gate-sim",
      label: "Icarus gate sim",
      detail: "learn/scripts/run_gate_sim.sh · gcd_gate.vcd name-join",
    },
    {
      id: "ccs-char",
      label: "CCS char (INV_X1 PTM)",
      detail: "learn/scripts/run_ccs_char.sh · sidecar liberty, official NLDM stays GAP",
    },
    {
      id: "klayout",
      label: "KLayout GDS / DRC",
      detail: "Viewer + run_klayout_drc.sh",
    },
  ];

  return { stage, odb, sta, yosys, hooks, variant };
}
