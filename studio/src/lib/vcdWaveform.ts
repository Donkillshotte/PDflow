import fs from "fs";
import path from "path";
import { LEARN_ROOT } from "./course";

export type VcdWaveform = {
  exists: boolean;
  path: string;
  timescale: string;
  maxTime: number;
  signals: {
    id: string;
    code: string;
    name: string;
    width: number;
    samples: { t: number; v: string }[];
  }[];
};

const DEFAULT_VCD = path.join(LEARN_ROOT, "sim/gcd/gcd.vcd");

/** Pick tb-level signals for waveform display. */
const PREFERRED_NAMES = ["clk", "reset", "req_val", "resp_val", "req_rdy", "resp_rdy"];

export function parseVcdWaveform(
  vcdPath = DEFAULT_VCD,
  opts?: { maxTransitions?: number; maxSignals?: number; maxTimePs?: number },
): VcdWaveform | null {
  const maxTransitions = opts?.maxTransitions ?? 120;
  const maxSignals = opts?.maxSignals ?? 6;
  const maxTimePs = opts?.maxTimePs ?? 800_000;

  if (!fs.existsSync(vcdPath)) return null;

  const text = fs.readFileSync(vcdPath, "utf8");
  const lines = text.split("\n");

  let timescale = "1ps";
  const tsMatch = text.match(/\$timescale\s+([\d.]+)([a-z]+)/);
  if (tsMatch) timescale = `${tsMatch[1]}${tsMatch[2]}`;

  type SigDef = { code: string; name: string; width: number; scope: string };
  const defs: SigDef[] = [];
  let scope = "";
  const codeToDef = new Map<string, SigDef>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("$scope")) {
      scope = trimmed.split(/\s+/)[2] ?? scope;
      continue;
    }
    if (trimmed.startsWith("$var")) {
      const m = trimmed.match(/^\$var\s+\w+\s+(\d+)\s+(\S+)\s+(.+?)\s+\$end$/);
      if (!m) continue;
      const width = Number(m[1]);
      const code = m[2]!;
      const name = m[3]!.replace(/\s+\[\d+:\d+\]$/, "").trim();
      const def = { code, name, width, scope };
      defs.push(def);
      codeToDef.set(code, def);
      continue;
    }
    if (trimmed.startsWith("$enddefinitions")) break;
  }

  const tbDefs = defs.filter((d) => d.scope === "tb_gcd" || d.name === "clk" || d.name === "reset");
  const picked: SigDef[] = [];
  for (const pref of PREFERRED_NAMES) {
    const hit = tbDefs.find((d) => d.name === pref);
    if (hit && !picked.some((p) => p.code === hit.code)) picked.push(hit);
  }
  for (const d of tbDefs) {
    if (picked.length >= maxSignals) break;
    if (d.width > 16) continue;
    if (!picked.some((p) => p.code === d.code)) picked.push(d);
  }

  const tracks = new Map<string, { t: number; v: string }[]>();
  for (const s of picked) tracks.set(s.code, []);

  let time = 0;
  let transitions = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("#")) {
      time = Number(trimmed.slice(1));
      if (time > maxTimePs) break;
      continue;
    }
    if (trimmed.startsWith("$")) continue;

    let code = "";
    let val = "";
    if (/^[01xXzZ]$/.test(trimmed[0]!)) {
      val = trimmed[0]!;
      code = trimmed.slice(1).trim();
    } else if (/^[bBrR]/.test(trimmed)) {
      const parts = trimmed.split(/\s+/);
      val = parts[0]!.slice(1);
      code = parts[1] ?? "";
    } else {
      code = trimmed;
      val = "1";
    }

    const track = tracks.get(code);
    if (!track) continue;
    if (track.length === 0 || track[track.length - 1]!.v !== val) {
      track.push({ t: time, v: val });
      transitions++;
      if (transitions > maxTransitions * picked.length) break;
    }
  }

  const maxTime = time;
  const signals = picked.map((s) => ({
    id: s.name,
    code: s.code,
    name: s.name,
    width: s.width,
    samples: (tracks.get(s.code) ?? []).slice(0, maxTransitions),
  }));

  return {
    exists: true,
    path: vcdPath.replace(LEARN_ROOT + path.sep, "learn/").replace(/\\/g, "/"),
    timescale,
    maxTime,
    signals,
  };
}
