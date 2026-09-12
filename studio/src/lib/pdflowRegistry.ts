import fs from "fs";
import path from "path";
import { REPO_ROOT } from "./course";
import type { ActionDescriptor, ToolDescriptor } from "./pdflowContracts";

type RegistryManifest = {
  schema_version: number;
  platform: string;
  default_timeout_seconds: number;
  tools: Array<{
    tool_id: string;
    display_name: string;
    required?: boolean;
    description?: string;
    capabilities?: string[];
    executable_env?: string[];
    executable_candidates?: string[];
    input_kinds?: string[];
    output_kinds?: string[];
    timeout_seconds?: number;
    required_dependencies?: string[];
    version_probe?: string[];
    version_probe_exit_codes?: number[];
    version_label?: string;
    launch_profiles?: string[];
    report_parsers?: string[];
    status_mapping?: Record<string, string>;
  }>;
};

const MANIFEST_PATH = path.join(
  REPO_ROOT,
  "config",
  "pdflow",
  "tool_registry.json",
);
const ACTION_MANIFEST_PATH = path.join(
  REPO_ROOT,
  "config",
  "pdflow",
  "action_registry.json",
);

function readManifest(): RegistryManifest {
  return JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf8")) as RegistryManifest;
}

function resolveExecutable(candidates: string[], envNames: string[]): string | null {
  const values = [
    ...(envNames.map((name) => process.env[name]).filter(Boolean) as string[]),
    ...candidates,
  ];
  const pathEntries = (process.env.PATH || "").split(path.delimiter).filter(Boolean);
  for (const value of values) {
    const expanded = value.startsWith("{repo}")
      ? path.join(REPO_ROOT, value.slice("{repo}".length))
      : value;
    if (path.isAbsolute(expanded)) {
      try {
        const mode = fs.statSync(expanded).mode;
        if (fs.statSync(expanded).isFile() && (mode & 0o111)) return expanded;
      } catch {
        continue;
      }
      continue;
    }
    for (const entry of pathEntries) {
      const candidate = path.join(entry, expanded);
      try {
        const mode = fs.statSync(candidate).mode;
        if (fs.statSync(candidate).isFile() && (mode & 0o111)) return candidate;
      } catch {
        continue;
      }
    }
  }
  return null;
}

function probeVersion(): string | null {
  // Version probing belongs to the local agent. Browser fallback deliberately
  // exposes availability without spawning arbitrary host processes.
  return null;
}

export function discoverStudioTools(): {
  schema_version: number;
  default_timeout_seconds: number;
  platform: string;
  tools: ToolDescriptor[];
  actions: ActionDescriptor[];
  tool_versions: Record<string, string | null>;
} {
  const manifest = readManifest();
  const tools: ToolDescriptor[] = manifest.tools.map((raw) => {
    const executable = resolveExecutable(
      raw.executable_candidates || [],
      raw.executable_env || [],
    );
    // The Next fallback is intentionally non-authoritative. Finding an
    // executable is not enough to call it READY because the fallback never
    // runs the registry's bounded version probe. The local agent remains the
    // only source allowed to promote a tool to READY.
    const availability: ToolDescriptor["availability"] = executable
      ? "UNVERIFIED"
      : "MISSING";
    return {
      tool_id: raw.tool_id,
      display_name: raw.display_name,
      required: raw.required !== false,
      description: raw.description || "",
      capabilities: raw.capabilities || [],
      input_kinds: raw.input_kinds || [],
      output_kinds: raw.output_kinds || [],
      timeout_seconds:
        raw.timeout_seconds || manifest.default_timeout_seconds || 600,
      required_dependencies: raw.required_dependencies || [],
      version_probe: raw.version_probe || ["--version"],
      version_probe_exit_codes: raw.version_probe_exit_codes || [0],
      version_label: raw.version_label || null,
      launch_profiles: raw.launch_profiles || [],
      report_parsers: raw.report_parsers || [],
      status_mapping: raw.status_mapping || {},
      availability,
      executable,
      version: probeVersion(),
    } satisfies ToolDescriptor;
  });
  let actions: ActionDescriptor[] = [];
  try {
    const actionManifest = JSON.parse(
      fs.readFileSync(ACTION_MANIFEST_PATH, "utf8"),
    ) as {
      actions?: Array<{
        action_id: string;
        display_name: string;
        surface: ActionDescriptor["surface"];
        timeout_seconds?: number;
        required_tools?: string[];
        mutates?: boolean;
      }>;
      default_timeout_seconds?: number;
    };
    const byTool = new Map(tools.map((tool) => [tool.tool_id, tool]));
    actions = (actionManifest.actions || []).map((action) => {
      const missingTools = (action.required_tools || []).filter(
        (tool) => byTool.get(tool)?.availability !== "READY",
      );
      return {
        action_id: action.action_id,
        display_name: action.display_name,
        surface: action.surface,
        timeout_seconds:
          action.timeout_seconds ||
          actionManifest.default_timeout_seconds ||
          manifest.default_timeout_seconds ||
          600,
        required_tools: action.required_tools || [],
        mutates: Boolean(action.mutates),
        availability: missingTools.length ? "GAP" : "READY",
        missing_tools: missingTools,
      };
    });
  } catch {
    actions = [];
  }
  return {
    schema_version: manifest.schema_version,
    default_timeout_seconds: manifest.default_timeout_seconds || 600,
    platform: manifest.platform,
    tools,
    actions,
    tool_versions: Object.fromEntries(
      tools.map((tool) => [tool.tool_id, tool.version]),
    ),
  };
}
