export const REPORT_STATUSES = [
  "PASS",
  "FAIL",
  "WARN",
  "PARTIAL",
  "PROXY",
  "GAP",
  "NOT_RUN",
] as const;

export type ReportStatus = (typeof REPORT_STATUSES)[number];

export const JOB_STATES = [
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "GAP",
  "DIRTY",
  "ORPHANED",
] as const;

export type JobState = (typeof JOB_STATES)[number];
export type Surface = "product" | "flow" | "package" | "lab" | "tools";
export type ArtifactAuthority = "finish" | "candidate" | "generated" | "source";

export type TerminationCause =
  | "cancelled"
  | "timeout"
  | "memory"
  | "resource_isolation"
  | "refused"
  | "crash";

export type ResourceRecord = {
  executor?: string;
  unit?: string;
  cgroup?: string | null;
  queue_wait_seconds?: number;
  limits?: {
    memory_max_bytes?: number;
    memory_high_bytes?: number;
    memory_swap_max_bytes?: number;
    cpu_quota_percent?: number;
    timeout_seconds?: number;
    log_max_bytes?: number;
  };
  initial_host?: { mem_available_bytes?: number | null };
  final_host?: { mem_available_bytes?: number | null };
  systemd?: {
    memory_peak_bytes?: number | null;
    memory_current?: number | null;
    memory_swap_current?: number | null;
    cpu_usage_ns?: number | null;
    result?: string | null;
  };
  memory_events?: Record<string, number>;
  resource_exhausted?: boolean;
  resource_cause?: string | null;
  termination_requested?: string | null;
};

export type ArtifactRef = {
  artifact_id: string;
  kind: string;
  scope: Surface | "generated";
  variant: string;
  relative_path: string;
  content_hash: string | null;
  size: number;
  mtime_ns: number;
  revision: number;
  producer: string;
  run_id: string | null;
  authority: ArtifactAuthority;
  mutable: boolean;
};

export type ToolAvailability =
  | "READY"
  | "MISSING"
  | "MISCONFIGURED"
  | "INCOMPATIBLE"
  // Browser/Next fallback can locate an executable but cannot probe it. It
  // must not be presented as READY while the local agent is unavailable.
  | "UNVERIFIED";

export type ToolDescriptor = {
  tool_id: string;
  display_name: string;
  required: boolean;
  description: string;
  capabilities: string[];
  input_kinds: string[];
  output_kinds: string[];
  timeout_seconds: number;
  required_dependencies: string[];
  version_probe?: string[];
  version_probe_exit_codes?: number[];
  version_label?: string | null;
  launch_profiles?: string[];
  report_parsers?: string[];
  status_mapping?: Record<string, string>;
  availability: ToolAvailability;
  executable: string | null;
  version: string | null;
};

export type RunContext = {
  schema_version: number;
  run_id: string | null;
  surface: Surface;
  design_id: string;
  pdk_id: string;
  profile: string;
  finish: ArtifactRef[];
  candidates: ArtifactRef[];
  input_artifacts?: string[];
  tool_versions: Record<string, string | null>;
  finish_mutable: false;
  comparison_scope: "same-live-invocation" | "not-comparable" | "none";
  generated_at: string;
};

export type JobRecord = {
  job_id: string;
  tool_id: string;
  action?: string | null;
  operation: string;
  state: JobState;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  run_id: string | null;
  artifact: ArtifactRef | null;
  mode?: "view" | "edit";
  command?: string[];
  timeout_seconds?: number;
  pid?: number;
  code?: number | null;
  reason?: string | null;
  termination_cause?: TerminationCause | null;
  log_path?: string;
  log_tail?: string;
  log_bytes?: number;
  log_bytes_seen?: number;
  log_truncated?: boolean;
  resource?: ResourceRecord;
  report?: ReportEnvelope;
};

export type ReportEnvelope = {
  schema_version: number;
  report_id: string;
  run_id: string | null;
  scope: Surface | "generated";
  status: ReportStatus;
  ok: boolean;
  execution_status?: string;
  evidence_status?: ReportStatus | string;
  requirement_status?: ReportStatus | string;
  signoff_status?: ReportStatus | string;
  product_signoff?: boolean;
  checkpoint_id?: string | null;
  configuration_hash?: string | null;
  units?: Record<string, string>;
  corner?: string | null;
  mode?: string | null;
  activity_source?: string | null;
  limitations?: string[];
  required_checks?: Array<Record<string, unknown>>;
  input_artifacts: string[];
  input_artifact_refs?: ArtifactRef[];
  output_artifacts: string[];
  output_artifact_refs?: ArtifactRef[];
  mesh_id?: string | null;
  oracle?: string | null;
  metrics?: Record<string, unknown>;
  relative?: Array<Record<string, unknown>>;
  comparison_scope: "same-live-invocation" | "not-comparable" | "none";
  report_paths?: string[];
  reason?: string | null;
  tool_versions?: Record<string, string | null>;
  environment?: Record<string, string>;
  job_id?: string | null;
  operation?: string | null;
  resource?: ResourceRecord;
  termination_cause?: TerminationCause | null;
  stale?: boolean;
};

export type ActionDescriptor = {
  action_id: string;
  display_name: string;
  surface: Surface | "generated";
  timeout_seconds: number;
  required_tools: string[];
  mutates: boolean;
  availability: "READY" | "MISSING" | "GAP";
  missing_tools: string[];
};

export type AgentHealth = {
  ok: boolean;
  service: string;
  schema_version: number;
  host: string;
  port: number;
  pid: number;
  watcher: {
    mode: "polling" | "inotify";
    interval_seconds?: number;
  };
  running_jobs: number;
  display_available: boolean;
  auth: boolean;
  resources?: ResourceRecord & {
    available?: boolean;
    isolation?: string;
    queue?: string;
  };
};

export type AgentEvent = {
  event_id: number;
  type: string;
  timestamp: number;
  payload: Record<string, unknown>;
};

export type PackageManifestArtifact = {
  role?: string;
  path?: string;
  exists?: boolean;
  bytes?: number;
  sha256?: string | null;
  authority?: string;
};

export type PackageManifestCheck = {
  id?: string;
  label?: string;
  status?: ReportStatus;
  ok?: boolean;
  evidence_ok?: boolean;
  required?: boolean;
  detail?: string;
  routed_nets?: string[];
  missing_nets?: string[];
};

export type PackageManifest = {
  schema_version?: number;
  kind?: string;
  scope?: "package" | string;
  variant?: string;
  design?: string;
  status?: ReportStatus;
  evidence_ok?: boolean;
  product_signoff?: boolean;
  comparison_scope?: string;
  oracle?: string;
  checkpoint?: Record<string, unknown>;
  interface?: {
    die?: Record<string, unknown> | null;
    ports?: Array<Record<string, unknown>>;
    port_count?: number;
    signal_port_count?: number;
    power_nets_from_def?: string[];
    specialnet_nets?: string[];
    package_nets?: string[];
    boundary_nets?: string[];
    missing_package_nets?: string[];
    database_units_per_micron?: number | null;
  };
  bump_array?: {
    master?: string;
    rows?: number;
    columns?: number;
    origin_um?: number[];
    pitch_um?: number[];
    configured_count?: number;
    observed_component_count?: number;
    configured_observed_count?: number;
    mapping_complete?: boolean;
    coordinate_bounds_ok?: boolean;
    assigned_count?: number;
    unassigned_instances?: string[];
    map?: Array<Record<string, unknown>>;
  };
  rdl?: {
    input_odb?: string;
    sidecar_odb?: string;
    sidecar_def?: string;
    ready?: boolean;
    layers?: string[];
    route_segments?: number;
    route_length_um_est?: number;
    required_nets?: string[];
    routed_nets?: string[];
    missing_nets?: string[];
    mapped_nets?: string[];
    conflicts?: Array<Record<string, string>>;
    nets?: Array<Record<string, unknown>>;
  };
  electrical_model?: {
    vdd?: number;
    n_supply_bumps?: number;
    mapped_power_bumps?: number;
    mapped_ground_bumps?: number;
    sparse_breakout?: boolean;
    r_bump_ohm?: number;
    l_bump_h?: number;
    r_pkg_ohm?: number;
    l_pkg_h?: number;
    c_pkg_f?: number;
    effective_supply_r_ohm?: number;
    effective_supply_l_h?: number;
    series_resonance_hz_est?: number | null;
    model_kind?: string;
    qualification?: string;
  };
  system_pdn?: {
    report?: string;
    ok?: boolean;
    engine?: string | null;
    i_die_avg_a?: number | null;
    droop_mv?: number | null;
    droop_pct?: number | null;
    z_max_mohm?: number | null;
    f_at_zmax_hz?: number | null;
    z_target_mohm?: number | null;
    pass_target?: boolean | null;
  };
  checks?: PackageManifestCheck[];
  provenance?: {
    input_fingerprint?: string;
    artifacts?: PackageManifestArtifact[];
  };
  limits?: Record<string, string>;
  summary?: string;
};

export type PackageEvidence = {
  schema_version: number;
  scope: "package";
  variant: string;
  status: ReportStatus;
  ok: boolean;
  evidence_ok?: boolean;
  comparison_scope: "same-live-invocation" | "not-comparable" | "none";
  oracle: string;
  input_artifacts: ArtifactRef[];
  input_fingerprint: string;
  manifest?: PackageManifest | null;
  steps: Record<
    string,
    {
      status: ReportStatus;
      ok: boolean;
      evidence_ok?: boolean;
      summary?: string;
      reason?: string | null;
      engine?: string | null;
      droop_mv?: number | null;
      zmax_mohm?: number | null;
      report?: string;
      educational?: boolean;
      manifest?: boolean;
    }
  >;
  product_signoff: {
    status: ReportStatus;
    reason: string;
  };
  generated_at: string;
};

export type PathLedger = {
  schema_version: number;
  scope: "flow";
  variant: string;
  status: ReportStatus;
  ok: boolean;
  mesh_id: string;
  oracle: string;
  comparison_scope: "same-live-invocation" | "not-comparable" | "none";
  entries: Array<Record<string, unknown>>;
  meshes: Array<Record<string, unknown>>;
  note: string;
  generated_at: string;
};

export type CheckEvidenceClass =
  | "PROXY"
  | "PARTIAL"
  | "CHECKPOINT_EVIDENCE"
  | "PRODUCT_INPUT"
  | "PACKAGE_EVIDENCE"
  | "GAP";

export type CheckEligibility = {
  schema_version: number;
  check_id: string;
  display_name: string;
  description: string;
  scope: Surface | "generated";
  stage: string;
  variant: string;
  run_id: string | null;
  eligible: boolean;
  status: ReportStatus;
  stale: boolean;
  evidence_class: CheckEvidenceClass | string;
  execution_class?: "UNAVAILABLE" | "NATIVE_JOB" | "EVIDENCE_ONLY" | string;
  expected_evidence_class?: CheckEvidenceClass | string;
  execution_status?: "QUEUED" | "RUNNING" | "COMPLETED" | "CANCELLED" | "FAILED" | "NOT_RUN" | string;
  evidence_status?: ReportStatus | string;
  requirement_status?: ReportStatus | string;
  signoff_status?: ReportStatus | string;
  action: string | null;
  default_trigger: "on-stage-success" | "manual" | "signoff-bundle" | string;
  cost_class: "light" | "medium" | "heavy" | string;
  required_tools: string[];
  missing_tools: string[];
  required_artifacts: string[];
  artifact: ArtifactRef | null;
  missing: string[];
  incompatible: string[];
  missing_inputs?: string[];
  stale_inputs?: string[];
  blocking_reasons?: string[];
  warnings: string[];
  knobs: string[];
  knob_schema?: Record<string, Record<string, unknown>>;
  required_capabilities?: string[];
  estimated_duration_seconds?: number;
  resource_limit?: {
    queue?: string;
    timeout_seconds?: number;
  };
  downstream_invalidations?: string[];
  report_reason: string | null;
  report_file: string | null;
  metrics?: Record<string, unknown>;
};

export type EvidenceRecord = {
  schema_version: number;
  report_id: string;
  check_id: string;
  stage: string;
  variant: string;
  checkpoint_id: string | null;
  analysis_run_id: string | null;
  input_artifacts: Array<ArtifactRef | string>;
  input_artifact_hashes: string[];
  configuration_hash?: string | null;
  tool_versions: Record<string, string | null>;
  units: Record<string, string>;
  corner?: string | null;
  mode?: string | null;
  mesh_id?: string | null;
  activity_source?: string | null;
  execution_status: string;
  evidence_status: ReportStatus | string;
  requirement_status: ReportStatus | string;
  signoff_status: ReportStatus | string;
  status: ReportStatus;
  ok: boolean;
  stale: boolean;
  limitations: string[];
  metrics: Record<string, unknown>;
  artifacts: Array<ArtifactRef | string>;
  report_paths: string[];
  reason?: string | null;
};

export type EvidenceIndex = {
  schema_version: number;
  stage: string;
  variant: string;
  run_id: string | null;
  evidence: EvidenceRecord[];
  count: number;
  principle: string;
  reason?: string;
};

export type CheckPolicy = {
  schema_version: number;
  stage: string;
  variant: string;
  run_id: string | null;
  checks: CheckEligibility[];
  stage_order: string[];
  principle: string;
  reason?: string;
};

export type AnalysisBundleJob = {
  check_id: string;
  display_name?: string;
  action?: string | null;
  eligible: boolean;
  runnable: boolean;
  status: ReportStatus | string;
  evidence_class?: string;
  execution_class?: string;
  cost_class?: string;
  estimated_duration_seconds?: number;
  timeout_seconds?: number;
  report_file?: string | null;
  parameters?: Record<string, unknown>;
  missing: string[];
  warnings: string[];
  invalidations: string[];
  reason?: string;
}

export type AnalysisBundlePlan = {
  schema_version: number;
  bundle_id: string;
  label: string;
  description: string;
  trigger: string;
  stage: string;
  variant: string;
  run_id: string | null;
  check_ids: string[];
  jobs: AnalysisBundleJob[];
  ready: boolean;
  confirmation_required: boolean;
  read_only: true;
  estimated_duration_seconds: number;
  resource_limit: {
    queue: string;
    timeout_seconds: number;
  };
  resource_preflight?: Record<string, unknown>;
  resource_blocking_reason?: string;
  downstream_invalidations: string[];
  missing_checks: string[];
  principle: string;
};

export type AnalysisRun = {
  schema_version: number;
  analysis_run_id: string;
  run_id: string | null;
  stage: string;
  variant: string;
  bundle_id: string;
  check_ids: string[];
  parameters: Record<string, unknown>;
  state: string;
  created_at: string;
  jobs: string[];
  plan: AnalysisBundlePlan;
  job_records?: JobRecord[];
};
