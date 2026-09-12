"""Local PDflow agent.

The agent is intentionally dependency-free. It exposes a small localhost API
for the desktop shell and a browser development session, while all process
launches remain behind an allowlisted declarative registry.
"""

from __future__ import annotations

import json
import math
import os
import re
import select
import selectors
import signal
import shutil
import subprocess
import struct
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .artifacts import ArtifactCatalog
from .actions import (
    build_action_command,
    discover_actions,
    get_action,
    is_lab_variant,
)
from .analysis import active_variant, package_evidence, path_ledger
from .eligibility import STAGES, check_policy
from .contracts import (
    JOB_STATES,
    ReportEnvelope,
    RunContext,
    atomic_write_json,
    hash_text,
    utc_now,
    validate_report,
)
from .events import EventBus
from .registry import build_command, discover, get_tool
from .resource_runner import (
    BoundedLog,
    ManagedProcess,
    ResourceExecutor,
    ResourceRunnerError,
)
from .workbench import build_bundle_plan


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parents[2]


def _display_available() -> bool:
    return bool(
        os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("STUDIO_DISPLAY")
    )


def _safe_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{8,100}", value))


_REPORT_STATUSES = frozenset(
    {"PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"}
)


def _report_status_value(value: Any, fallback: str) -> str:
    candidate = str(value or "").upper()
    return candidate if candidate in _REPORT_STATUSES else fallback


_CONTROLLED_REFUSAL_PREFIXES = ("REFUSED:", "PREVIEW_GAP")


def _controlled_refusal_reason(log_tail: str) -> str | None:
    """Extract a bounded, machine-classifiable policy refusal from a log.

    Native wrappers use a short ``REFUSED:``/``PREVIEW_GAP`` line when they
    deliberately decline to run (for example, to protect a finish). That is
    different from a tool crash and must survive in the job/report contract.
    Only the bounded in-memory tail is inspected; full logs remain on disk.
    """

    for line in reversed(log_tail.splitlines()):
        message = line.strip()
        if message.startswith(_CONTROLLED_REFUSAL_PREFIXES):
            return message[:2048]
    return None


_FLOWLAB_STAGE_ACTIONS = {"synth", "floorplan", "place", "cts", "route", "finish"}
# Only actions that recook or otherwise create a new FlowLab checkpoint need
# candidate preparation and finish-lock enforcement. Read-only analyses must
# remain runnable against the selected live checkpoint; treating them as a
# recook made a harmless STA/gridcheck click return the misleading
# "finish is locked" refusal.
_FLOWLAB_CANDIDATE_ACTIONS = _FLOWLAB_STAGE_ACTIONS
_FLOWLAB_ANALYSIS_ACTIONS = {
    "gridcheck",
    "sta_checkpoint",
    "chip_pdn_ir",
    "dynamic_ir",
    "power_grid_em",
}
_FLOWLAB_CANDIDATE_ANALYSIS_FILES = {
    # Candidate analysis must have the same checkpoint closure as the native
    # adapter.  Copy only the files the adapter actually consumes; never
    # overwrite a file that the engineer has already changed in the
    # candidate workspace.
    "synth": ("1_synth.odb", "1_2_yosys.v", "1_synth.sdc"),
    "floorplan": ("2_floorplan.odb", "1_2_yosys.v", "2_floorplan.sdc"),
    "pdn": ("2_4_floorplan_pdn.odb", "1_2_yosys.v", "2_floorplan.sdc"),
    "place": ("3_place.odb", "1_2_yosys.v", "3_place.sdc"),
    "cts": ("4_cts.odb", "1_2_yosys.v", "4_cts.sdc"),
    "route": ("5_2_route.odb", "1_2_yosys.v", "5_route.sdc"),
    "finish": ("6_final.odb", "6_final.v", "6_final.sdc", "6_final.spef"),
}
_LAYOUT_PREVIEW_ODB = {
    "floorplan": "2_4_floorplan_pdn.odb",
    "pdn": "2_4_floorplan_pdn.odb",
    "place": "3_5_place_dp.odb",
    "cts": "4_cts.odb",
    "route": "5_2_route.odb",
    "finish": "6_final.odb",
    "pkg": "6_final.odb",
}
_INSPECT_STAGE_ARTIFACTS = {
    "synth": ("1_synth.odb", "1_2_yosys.v"),
    "floorplan": ("2_floorplan.odb", "1_2_yosys.v"),
    "pdn": ("2_4_floorplan_pdn.odb", "1_2_yosys.v"),
    "place": ("3_place.odb", "1_2_yosys.v"),
    "cts": ("4_cts.odb", None),
    "route": ("5_route.odb", None),
    "finish": ("6_final.odb", "6_final.v"),
}
_FLOWLAB_PARAMETER_KEYS = {
    "coreUtilization": "CORE_UTILIZATION",
    "core_utilization": "CORE_UTILIZATION",
    "placeDensityAddon": "PLACE_DENSITY_LB_ADDON",
    "place_density_addon": "PLACE_DENSITY_LB_ADDON",
    "abcArea": "ABC_AREA",
    "abc_area": "ABC_AREA",
    "sdcPreset": "SDC_FILE",
    "sdc_preset": "SDC_FILE",
    "tnsEndPercent": "TNS_END_PERCENT",
    "tns_end_percent": "TNS_END_PERCENT",
    "checkpoint": "PD_FLOW_CHECKPOINT",
}
_LAB_ASAP7_PARAMETER_KEYS = {
    "variant",
    "design",
    "corner",
    "vt",
    "lib_model",
    "track",
    "clk_ps",
    "cluster_flops",
}
_LAB_ASAP7_DESIGNS = {"gcd", "gcd-ccs", "uart", "minimal", "riscv32i-mock-sram"}
_LAB_ASAP7_CORNERS = {"BC", "TC", "WC"}
_LAB_ASAP7_LIB_MODELS = {"NLDM", "CCS"}
_LAB_ASAP7_TRACKS = {"7p5", "6"}
_ANALYSIS_CHECKPOINTS = {
    "floorplan",
    "pdn",
    "place",
    "cts",
    "route",
    "finish",
}
_ANALYSIS_PARAMETER_KEYS = {
    "gridcheck": {"checkpoint", "net", "require_terminals"},
    "sta_checkpoint": {"checkpoint", "mode", "max_paths"},
    "chip_pdn_ir": {
        "checkpoint",
        "package_resistance",
        "package_inductance",
        "c_decap",
        "peak_factor",
    },
    "dynamic_ir": {
        "checkpoint",
        "package_resistance",
        "package_inductance",
        "c_decap",
        "peak_factor",
        "mode",
        "period_ns",
        "duration_ns",
        "timestep_ps",
    },
    "power_grid_em": {
        "checkpoint",
        "peak_factor",
        "ir_limit_pct",
        "c_decap",
        "switch_t_ns",
        "switch_dur_ns",
        "package_resistance",
    },
}
_SYSTEM_PDN_PARAMETER_RANGES = {
    # UI-facing controls.  Values are deliberately expressed in engineering
    # units instead of raw SPICE SI values so a browser cannot accidentally
    # submit a plausible-looking but six-orders-of-magnitude-wrong deck.
    "die_current_ma": (0.01, 20.0),
    "peak_factor": (1.0, 16.0),
    "board_l_nh": (0.01, 20.0),
    "package_r_mohm": (0.01, 500.0),
    "package_l_nh": (0.001, 20.0),
    "board_bulk_uf": (0.1, 2000.0),
    "package_c_pf": (1.0, 10000.0),
    "target_z_mohm": (0.1, 2000.0),
    "edge_ns": (0.05, 50.0),
    "delay_ns": (0.0, 1000.0),
    "pulse_width_ns": (0.1, 1000.0),
}
_SAFE_REPORT_ENVIRONMENT_KEYS = {
    "FLOW_VARIANT",
    "PYTHONPATH",
    "PD_FLOW_WORK_HOME",
    "PD_FLOW_RTL_FILE",
    "PD_FLOW_CANDIDATE_RUN_ID",
    "RTL_FILE",
    "PD_FLOW_PREVIEW_PHASE",
    "PD_FLOW_PREVIEW_VARIANT",
    "PD_FLOW_PREVIEW_RUN_ID",
    "PD_FLOW_INSPECT_STAGE",
    "PD_FLOW_INSPECT_VARIANT",
    "PD_FLOW_INSPECT_ROOT",
    "PD_FLOW_INSPECT_REPO_ROOT",
    "PD_FLOW_INSPECT_OUTPUT",
    "ECO_MODE",
    "CORE_UTILIZATION",
    "PLACE_DENSITY_LB_ADDON",
    "ABC_AREA",
    "SDC_FILE",
    "TNS_END_PERCENT",
    "PD_FLOW_CHECKPOINT",
    "SYSTEM_PDN_CONFIG",
    "SYSTEM_PDN_REPORT",
    "I_DIE_AVG",
    "PD_FLOW_SYSTEM_PDN_OUTPUT_DIR",
    "PD_FLOW_SYSTEM_PDN_WORK_DIR",
    "PD_FLOW_SYSTEM_PDN_RUN_DIR",
    "PD_FLOW_SYSTEM_PDN_REPORT",
    "PD_FLOW_SYSTEM_PDN_LOG",
    "PD_FLOW_SYSTEM_PDN_RUN_ID",
    "PD_FLOW_GRID_NET",
    "PD_FLOW_GRID_REQUIRE_TERMINALS",
    "STA_MODE",
    "STA_MAX_PATHS",
    "PKG_R",
    "PKG_L",
    "C_DECAP",
    "PEAK_FACTOR",
    "DYNAMIC_IR_MODE",
    "PERIOD_NS",
    "DUR_NS",
    "DT_PS",
    "IR_LIMIT_PCT",
    "SWITCH_T_NS",
    "SWITCH_DUR_NS",
    "LAB_ASAP7_VARIANT",
    "LAB_ASAP7_DESIGN",
    "CORNER",
    "ASAP7_USE_VT",
    "LIB_MODEL",
    "ASAP7_TRACK",
    "LAB_CLK_PS",
    "CLUSTER_FLOPS",
}


class _InotifyWatcher:
    """Small Linux-only inotify adapter with no third-party dependency."""

    IN_ACCESS = 0x00000001
    IN_MODIFY = 0x00000002
    IN_ATTRIB = 0x00000004
    IN_CLOSE_WRITE = 0x00000008
    IN_MOVED_FROM = 0x00000040
    IN_MOVED_TO = 0x00000080
    IN_CREATE = 0x00000100
    IN_DELETE = 0x00000200
    IN_DELETE_SELF = 0x00000400
    IN_MOVE_SELF = 0x00000800
    IN_ISDIR = 0x40000000
    IN_IGNORED = 0x00008000
    MASK = (
        IN_MODIFY
        | IN_ATTRIB
        | IN_CLOSE_WRITE
        | IN_MOVED_FROM
        | IN_MOVED_TO
        | IN_CREATE
        | IN_DELETE
        | IN_DELETE_SELF
        | IN_MOVE_SELF
    )

    def __init__(self, roots: tuple[Path, ...]) -> None:
        if sys.platform != "linux":
            raise OSError("inotify is only available on Linux")
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        self._libc = libc
        libc.inotify_init1.argtypes = [ctypes.c_int]
        libc.inotify_init1.restype = ctypes.c_int
        libc.inotify_add_watch.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        libc.inotify_add_watch.restype = ctypes.c_int
        self._fd = int(libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))
        if self._fd < 0:
            raise OSError("unable to initialize inotify")
        self._watches: dict[int, Path] = {}
        for root in roots:
            if root.is_dir():
                self._add_tree(root)
        if not self._watches:
            self.close()
            raise OSError("no watchable PDflow roots")

    def _add(self, directory: Path) -> None:
        import ctypes

        wd = int(
            self._libc.inotify_add_watch(
                self._fd,
                os.fsencode(str(directory)),
                ctypes.c_uint32(self.MASK),
            )
        )
        if wd >= 0:
            self._watches[wd] = directory

    def _add_tree(self, root: Path) -> None:
        self._add(root)
        try:
            directories = [path for path in root.rglob("*") if path.is_dir()]
        except OSError:
            directories = []
        for directory in directories:
            self._add(directory)

    def wait(self, timeout: float) -> bool:
        readable, _, _ = select.select([self._fd], [], [], timeout)
        if not readable:
            return False
        try:
            data = os.read(self._fd, 1024 * 1024)
        except BlockingIOError:
            return False
        changed = False
        offset = 0
        while offset + 16 <= len(data):
            wd, mask, _, name_length = struct.unpack_from("iIII", data, offset)
            offset += 16
            raw_name = data[offset : offset + name_length]
            offset += name_length
            directory = self._watches.get(wd)
            if mask & self.IN_IGNORED:
                self._watches.pop(wd, None)
            if directory is None:
                continue
            name = raw_name.split(b"\0", 1)[0].decode("utf-8", "ignore")
            path = directory / name if name else directory
            if mask & self.IN_ISDIR and mask & (self.IN_CREATE | self.IN_MOVED_TO):
                if path.is_dir():
                    self._add_tree(path)
            if mask & self.MASK:
                changed = True
        return changed

    def close(self) -> None:
        fd = getattr(self, "_fd", -1)
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
            self._fd = -1


class LocalAgent:
    def __init__(
        self,
        repo_root: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 43219,
        auth_token: str | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self.repo_root = (repo_root or _repo_root_default()).resolve()
        self.host = host
        self.port = int(port)
        self.auth_token = auth_token or os.environ.get("PD_FLOW_AGENT_TOKEN")
        self.poll_seconds = max(0.25, poll_seconds)
        self.catalog = ArtifactCatalog(self.repo_root)
        self.events = EventBus()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._processes: dict[str, ManagedProcess] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._runs: dict[str, dict[str, Any]] = {}
        self._analysis_runs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._server: ThreadingHTTPServer | None = None
        self._watch_state: dict[str, tuple[int, int, str | None, str]] = {}
        self._watch_mode = "polling"
        self._watcher: _InotifyWatcher | None = None
        self._invalidated_reports: dict[str, str] = {}
        self._created_at = utc_now()
        self.resources = ResourceExecutor(self.repo_root)

    @property
    def run_root(self) -> Path:
        return self.repo_root / ".pdflow" / "runs"

    @property
    def agent_root(self) -> Path:
        return self.repo_root / ".pdflow" / "agent"

    def _candidate_workspace(self, run_id: str) -> tuple[Path, Path]:
        """Return the validated run-scoped candidate root and ORFS WORK_HOME."""

        if not _safe_id(run_id):
            raise ValueError("invalid candidate run_id")
        with self._lock:
            record = self._runs.get(run_id)
        if not record or record.get("surface") != "flow" or record.get("profile") != "flowlab-candidate":
            raise ValueError("run_id is not a FlowLab candidate run")
        run_dir = (self.run_root / run_id).resolve()
        try:
            run_dir.relative_to(self.run_root.resolve())
        except ValueError as exc:
            raise ValueError("candidate run escapes the run root") from exc
        candidate_root = run_dir / "candidate"
        work_home = candidate_root / "orfs"
        return candidate_root, work_home

    def _prepare_candidate_analysis_inputs(
        self,
        run_id: str,
        checkpoint: str,
    ) -> list[Any]:
        """Materialize the immutable dependency closure for candidate analysis.

        A candidate may initially contain only the ODB selected by the UI.
        Native STA and PDN adapters also require checkpoint-matched netlist,
        SDC, and sometimes SPEF files.  Preflight must either make that
        closure available in the same candidate tree or fail before the job
        starts.  Existing candidate files are never replaced, so an engineer
        can safely edit a candidate and re-run analysis.
        """

        names = _FLOWLAB_CANDIDATE_ANALYSIS_FILES.get(checkpoint)
        if not names:
            raise ValueError("invalid candidate analysis checkpoint")
        candidate_root, _work_home = self._candidate_workspace(run_id)
        source_root = (
            self.repo_root
            / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab"
        )
        candidate_result_root = candidate_root / "orfs/results/nangate45/gcd/flowlab"
        refs: list[Any] = []
        missing: list[str] = []
        for name in names:
            target = candidate_result_root / name
            if target.is_symlink():
                missing.append(f"candidate input is a symlink: {name}")
                continue
            if not target.is_file():
                source = self.catalog.resolve_path(
                    str((source_root / name).relative_to(self.repo_root))
                )
                if source is None:
                    missing.append(name)
                    continue
                try:
                    self.catalog.create_candidate(source, run_id)
                except FileExistsError:
                    # A concurrent request may have materialized the same
                    # dependency.  Re-read it and continue if it is valid.
                    pass
            ref = self.catalog.resolve_path(
                str(target.relative_to(self.repo_root))
            )
            if ref is None or ref.authority != "candidate" or ref.run_id != run_id:
                missing.append(name)
                continue
            refs.append(ref)
        if missing:
            raise FileNotFoundError(
                "candidate analysis inputs are incomplete: " + ", ".join(missing)
            )
        # Keep the checkpoint ODB first.  It is the primary artifact shown in
        # the job/report contract, while the remaining refs preserve the
        # actual STA/PDN dependency provenance.
        refs.sort(key=lambda item: (0 if item.kind == "odb" else 1, item.relative_path))
        return refs

    @staticmethod
    def _copy_snapshot(source: Path, target: Path) -> None:
        """Copy a candidate input atomically so readers never see a partial file."""

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    @property
    def token_path(self) -> Path:
        return self.agent_root / "agent.token"

    def _write_token(self) -> None:
        if not self.auth_token:
            return
        self.agent_root.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(self.auth_token + "\n", encoding="utf-8")
        try:
            self.token_path.chmod(0o600)
        except OSError:
            pass

    def _job_path(self, job: dict[str, Any]) -> Path:
        run_id = job.get("run_id")
        if isinstance(run_id, str) and _safe_id(run_id):
            return self.run_root / run_id / "jobs" / f"{job['job_id']}.json"
        return self.agent_root / "jobs" / f"{job['job_id']}.json"

    def _persist_job(self, job: dict[str, Any]) -> None:
        try:
            atomic_write_json(self._job_path(job), job)
        except OSError:
            # The runtime state remains authoritative even if a diagnostic
            # copy cannot be written (for example during shutdown).
            self._emit(
                "agent.warning",
                {"message": "job persistence failed", "job_id": job.get("job_id")},
            )

    def _recover_orphan_jobs(self) -> None:
        """Load persisted records and make abandoned processes explicit."""

        paths: list[Path] = []
        if self.run_root.is_dir():
            paths.extend(self.run_root.glob("*/jobs/*.json"))
        if self.agent_root.is_dir():
            paths.extend(self.agent_root.glob("jobs/*.json"))
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict) or not record.get("job_id"):
                continue
            state = str(record.get("state") or "")
            if state in {"QUEUED", "RUNNING"}:
                record["state"] = "ORPHANED"
                record["finished_at"] = utc_now()
                record["reason"] = "agent restarted while the job was active"
                report = ReportEnvelope(
                    report_id=f"report-{uuid.uuid4().hex}",
                    run_id=record.get("run_id"),
                    scope="generated",
                    status="PARTIAL",
                    ok=False,
                    execution_status="FAILED",
                    evidence_status="GAP",
                    requirement_status="NOT_RUN",
                    signoff_status="NOT_RUN",
                    reason=record["reason"],
                    job_id=str(record["job_id"]),
                    operation=str(record.get("operation") or "unknown"),
                ).to_dict()
                record["report"] = report
                self._persist_job(record)
            with self._lock:
                self._jobs[str(record["job_id"])] = record
            self._emit("job.recovered", {"job": dict(record)})

    def _load_persisted_runs(self) -> None:
        if not self.run_root.is_dir():
            return
        for manifest in self.run_root.glob("*/manifest.json"):
            try:
                record = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            run_id = str(record.get("run_id") or manifest.parent.name)
            if not _safe_id(run_id):
                continue
            record.setdefault("run_id", run_id)
            record.setdefault(
                "run_dir",
                str(manifest.parent.relative_to(self.repo_root)),
            )
            with self._lock:
                self._runs[run_id] = record

    def _load_persisted_analysis_runs(self) -> None:
        """Restore analysis plans without reviving or launching their jobs."""

        paths: list[Path] = []
        if self.run_root.is_dir():
            paths.extend(self.run_root.glob("*/analysis-runs/*.json"))
        if self.agent_root.is_dir():
            paths.extend(self.agent_root.glob("analysis-runs/*.json"))
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            analysis_run_id = str(record.get("analysis_run_id") or "")
            if not _safe_id(analysis_run_id):
                continue
            with self._lock:
                self._analysis_runs[analysis_run_id] = record

    def _emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.emit(event_type, payload)

    def health(self) -> dict[str, Any]:
        with self._lock:
            running = sum(
                1
                for job in self._jobs.values()
                if job.get("state") in {"QUEUED", "RUNNING"}
            )
        return {
            "ok": True,
            "service": "pdflow-local-agent",
            "schema_version": 1,
            "host": self.host,
            "port": self.port,
            "pid": os.getpid(),
            "created_at": self._created_at,
            "watcher": {
                "mode": self._watch_mode,
                "interval_seconds": self.poll_seconds,
            },
            "running_jobs": running,
            "display_available": _display_available(),
            "auth": bool(self.auth_token),
            "resources": self.resources.describe(),
        }

    def viewer_status(self) -> dict[str, Any]:
        """Return the agent-owned OpenROAD web session, if one is active."""

        with self._lock:
            sessions = [
                job
                for job in self._jobs.values()
                if job.get("operation") == "web"
                and job.get("state") in {"QUEUED", "RUNNING"}
            ]
        sessions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        if not sessions:
            return {
                "running": False,
                "display": _display_available(),
                "agent_managed": True,
            }
        job = sessions[0]
        artifact = job.get("artifact") or {}
        port = int(job.get("web_port") or 43190)
        return {
            "running": True,
            "state": job.get("state"),
            "job_id": job.get("job_id"),
            "pid": job.get("pid"),
            "port": port,
            "url": f"http://127.0.0.1:{port}/",
            "artifact": artifact.get("relative_path"),
            "stage": job.get("viewer_stage"),
            "run_id": job.get("run_id"),
            "started_at": job.get("started_at") or job.get("created_at"),
            "display": _display_available(),
            "agent_managed": True,
        }

    def start(self) -> ThreadingHTTPServer:
        self._write_token()
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._load_persisted_runs()
        self._load_persisted_analysis_runs()
        self._recover_orphan_jobs()
        self._watch_state = self._snapshot_by_path()
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            name="pdflow-artifact-watcher",
            daemon=True,
        )
        self._watch_thread.start()
        handler = self._handler_class()
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self.port = int(self._server.server_address[1])
        self._emit("agent.started", self.health())
        return self._server

    def serve_forever(self) -> None:
        server = self.start()
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        if self._watcher:
            self._watcher.close()
            self._watcher = None
        with self._lock:
            process_ids = list(self._processes)
        for job_id in process_ids:
            self.cancel_job(job_id)
        if self._server:
            self._server.server_close()
        self._emit("agent.stopped", {})

    def _snapshot_by_path(self) -> dict[str, tuple[int, int, str | None, str]]:
        state: dict[str, tuple[int, int, str | None, str]] = {}
        for ref in self.catalog.list(limit=2000):
            state[ref.relative_path] = (
                ref.size,
                ref.mtime_ns,
                ref.content_hash,
                ref.artifact_id,
            )
        return state

    def _scan_watch_state(self, watcher_name: str) -> None:
        try:
            current = self._snapshot_by_path()
            previous = self._watch_state
            for relative, value in current.items():
                if previous.get(relative) == value:
                    continue
                if relative in previous:
                    self.catalog.bump_revision(relative)
                ref = self.catalog.resolve_path(relative)
                if ref:
                    self._emit(
                        "artifact.changed" if relative in previous else "artifact.added",
                        {
                            "artifact": ref.to_dict(),
                            "previous": previous.get(relative),
                            "watcher": watcher_name,
                        },
                    )
                    if relative in previous:
                        self._invalidate_reports(ref)
                        self._emit(
                            "artifact.stale",
                            {
                                "artifact": ref.to_dict(),
                                "reason": "derived reports need revalidation",
                            },
                        )
            for relative, value in previous.items():
                if relative not in current:
                    self._emit(
                        "artifact.removed",
                        {
                            "relative_path": relative,
                            "previous": value,
                            "watcher": watcher_name,
                        },
                    )
            self._watch_state = current
        except Exception as exc:  # watcher must not kill the agent
            self._emit("watcher.error", {"error": str(exc)})

    def _watch_loop(self) -> None:
        try:
            self._watcher = _InotifyWatcher(self.catalog.allowed_roots)
            self._watch_mode = "inotify"
        except OSError as exc:
            self._watcher = None
            self._watch_mode = "polling"
            self._emit("watcher.fallback", {"reason": str(exc)})
        while not self._stop_event.is_set():
            if self._watcher:
                watcher = self._watcher
                try:
                    changed = watcher.wait(self.poll_seconds)
                    if changed:
                        self._scan_watch_state("inotify")
                except (OSError, ValueError) as exc:
                    if self._stop_event.is_set():
                        break
                    self._emit("watcher.fallback", {"reason": str(exc)})
                    watcher.close()
                    self._watcher = None
                    self._watch_mode = "polling"
            else:
                if self._stop_event.wait(self.poll_seconds):
                    break
                self._scan_watch_state("polling")

    def _invalidate_reports(self, changed: Any) -> None:
        """Notify clients when a report's physical input changed.

        Reports are not rewritten in place: their original provenance remains
        inspectable, while consumers receive an explicit invalidation event
        and must re-read the live report contract before showing it.
        """

        report_roots = [self.run_root]
        sim_reports = self.repo_root / "learn" / "sim" / "reports"
        for root in report_roots:
            if not root.is_dir():
                continue
            for report_path in root.rglob("reports/*.json"):
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(report, dict):
                    continue
                inputs = report.get("input_artifact_refs") or []
                input_ids = report.get("input_artifacts") or []
                matches = any(
                    isinstance(item, dict)
                    and (
                        item.get("artifact_id") == changed.artifact_id
                        or item.get("relative_path") == changed.relative_path
                    )
                    for item in inputs
                ) or changed.artifact_id in input_ids
                if matches:
                    report_id = str(report.get("report_id") or "")
                    if report_id:
                        self._invalidated_reports[report_id] = (
                            "input artifact revision changed"
                        )
                    self._emit(
                        "comparison.invalidated",
                        {
                            "report_id": report_id or None,
                            "report_path": str(report_path.relative_to(self.repo_root)),
                            "artifact": changed.to_dict(),
                            "reason": "input artifact revision changed",
                        },
                    )
        if sim_reports.is_dir():
            self._emit(
                "report.updated",
                {
                    "scope": "live",
                    "artifact": changed.to_dict(),
                    "reason": "live report consumers must revalidate mtime and hashes",
                },
            )

    def registry(self) -> dict[str, Any]:
        result = discover(self.repo_root)
        result["actions"] = discover_actions(self.repo_root, result)
        return result

    def artifacts(
        self,
        limit: int = 200,
        *,
        scope: str | None = None,
        variant: str | None = None,
        authority: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        refs = self.catalog.list(
            limit=limit,
            scope=scope,
            variant=variant,
            authority=authority,
            run_id=run_id,
        )
        return {
            "schema_version": 1,
            "artifacts": [ref.to_dict() for ref in refs],
            "count": len(refs),
        }

    def package(self, variant: str | None = None) -> dict[str, Any]:
        return package_evidence(self.repo_root, self.catalog, variant)

    def path_ledger(self, variant: str | None = None) -> dict[str, Any]:
        return path_ledger(self.repo_root, self.catalog, variant)

    def checks(
        self,
        *,
        stage: str = "finish",
        variant: str | None = None,
        run_id: str | None = None,
        check_id: str | None = None,
    ) -> dict[str, Any]:
        """Return checkpoint-aware check availability without launching work."""

        if stage not in STAGES:
            raise ValueError("invalid analysis checkpoint")
        selected_variant = str(
            variant
            or (
                self._current_asap7_variant()
                if stage == "package"
                else active_variant(self.repo_root)
            )
        )
        if selected_variant not in {"flowlab", "learn", "eco_scratch"} and not is_lab_variant(selected_variant):
            raise ValueError("invalid analysis variant")
        tools = self.registry().get("tools", [])
        candidate_scope = False
        if run_id:
            with self._lock:
                run_record = self._runs.get(run_id)
            candidate_scope = bool(
                isinstance(run_record, dict)
                and run_record.get("profile") == "flowlab-candidate"
            )
        # Capture one scoped artifact snapshot for all checks. A policy can
        # contain nine checks, and rescanning/hashing the full ORFS result
        # tree once per check made a read-only ASAP7 preflight look hung while
        # also wasting CPU and I/O. The snapshot is still fresh per request;
        # the watcher remains responsible for revision/stale propagation.
        artifacts = self.catalog.list(
            limit=2000,
            run_id=run_id if candidate_scope else None,
            variant=None if candidate_scope and run_id else selected_variant,
        )
        return check_policy(
            self.repo_root,
            self.catalog,
            stage=stage,
            variant=selected_variant,
            run_id=run_id,
            check_id=check_id,
            tools=tools if isinstance(tools, list) else [],
            candidate_scope=candidate_scope,
            artifacts=artifacts,
        )

    def evidence(
        self,
        *,
        stage: str = "finish",
        variant: str | None = None,
        run_id: str | None = None,
        check_id: str | None = None,
    ) -> dict[str, Any]:
        """Index structured evidence for one checkpoint without launching work."""

        policy = self.checks(
            stage=stage,
            variant=variant,
            run_id=run_id,
            check_id=check_id,
        )
        records: list[dict[str, Any]] = []
        for check in policy.get("checks", []):
            if not isinstance(check, dict):
                continue
            report_file = check.get("report_file")
            if not isinstance(report_file, str) or not report_file:
                continue
            path = (self.repo_root / report_file).resolve()
            try:
                path.relative_to(self.repo_root.resolve())
                raw = json.loads(path.read_text(encoding="utf-8"))
                report_stat = path.stat()
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            digest = hash_text(
                report_file,
                str(report_stat.st_size),
                str(report_stat.st_mtime_ns),
            )[:24]
            report_id = str(raw.get("report_id") or f"evidence-{digest}")
            input_refs = raw.get("input_artifact_refs")
            if not isinstance(input_refs, list):
                input_refs = raw.get("input_artifacts")
            if not isinstance(input_refs, list):
                input_refs = []
            hashes = [
                str(item.get("content_hash"))
                for item in input_refs
                if isinstance(item, dict) and item.get("content_hash")
            ]
            output_refs = raw.get("output_artifact_refs")
            if not isinstance(output_refs, list):
                output_refs = raw.get("output_artifacts")
            if not isinstance(output_refs, list):
                output_refs = []
            limitations = list(check.get("warnings") or [])
            raw_limitations = raw.get("limitations")
            if isinstance(raw_limitations, list):
                limitations.extend(str(item) for item in raw_limitations)
            artifact = check.get("artifact")
            records.append(
                {
                    "schema_version": 1,
                    "report_id": report_id,
                    "check_id": check.get("check_id"),
                    "stage": stage,
                    "variant": policy.get("variant"),
                    "checkpoint_id": artifact.get("artifact_id") if isinstance(artifact, dict) else None,
                    "analysis_run_id": raw.get("analysis_run_id") or run_id,
                    "input_artifacts": input_refs,
                    "input_artifact_hashes": hashes,
                    "configuration_hash": raw.get("configuration_hash"),
                    "tool_versions": raw.get("tool_versions") or {},
                    "units": raw.get("units") or {},
                    "corner": raw.get("corner"),
                    "mode": raw.get("mode"),
                    "mesh_id": raw.get("mesh_id"),
                    "activity_source": raw.get("activity_source"),
                    "execution_status": check.get("execution_status", "COMPLETED"),
                    "evidence_status": check.get("evidence_status", "GAP"),
                    "requirement_status": check.get("requirement_status", "NOT_RUN"),
                    "signoff_status": check.get("signoff_status", "NOT_RUN"),
                    "status": check.get("status", "GAP"),
                    "ok": bool(
                        check.get("status") == "PASS"
                        and check.get("evidence_status") == "PASS"
                        and check.get("signoff_status") == "PASS"
                    ),
                    "stale": bool(check.get("stale")),
                    "limitations": limitations,
                    "metrics": check.get("metrics") or {},
                    "artifacts": output_refs,
                    "report_paths": [report_file],
                    "reason": check.get("report_reason"),
                }
            )
        return {
            "schema_version": 1,
            "stage": policy.get("stage", stage),
            "variant": policy.get("variant", variant),
            "run_id": policy.get("run_id", run_id),
            "evidence": records,
            "count": len(records),
            "principle": "evidence is read-only and scoped to the selected checkpoint; selecting this endpoint never launches a job",
        }

    def artifact_detail(self, artifact_id: str) -> dict[str, Any] | None:
        ref = self.catalog.resolve(artifact_id)
        if ref is None:
            return None
        return {
            "schema_version": 1,
            "artifact": ref.to_dict(),
            "resolved": True,
            "read_only": not ref.mutable,
        }

    def report_detail(self, report_id: str) -> dict[str, Any] | None:
        with self._lock:
            for job in self._jobs.values():
                report = job.get("report")
                if isinstance(report, dict) and report.get("report_id") == report_id:
                    value = dict(report)
                    break
            else:
                value = None
        if value is None:
            for report_path in self.run_root.rglob("reports/*.json"):
                try:
                    candidate = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(candidate, dict) and candidate.get("report_id") == report_id:
                    value = candidate
                    break
        if value is None:
            return None
        reason = self._invalidated_reports.get(report_id)
        if reason:
            value["stale"] = True
            value["status"] = "GAP"
            value["ok"] = False
            value["reason"] = reason
        return value

    def compare_reports(self, payload: dict[str, Any]) -> dict[str, Any]:
        left_id = str(payload.get("left_report_id") or "")
        right_id = str(payload.get("right_report_id") or "")
        left = self.report_detail(left_id) if left_id else payload.get("left")
        right = self.report_detail(right_id) if right_id else payload.get("right")
        base = {
            "schema_version": 1,
            "scope": "generated",
            "status": "GAP",
            "ok": False,
            "comparison_scope": "not-comparable",
            "relative": [],
        }
        if not isinstance(left, dict) or not isinstance(right, dict):
            return {**base, "reason": "both reports are required"}
        if left.get("stale") or right.get("stale"):
            return {**base, "reason": "stale reports cannot be compared"}
        if not left.get("run_id") or left.get("run_id") != right.get("run_id"):
            return {**base, "reason": "reports must belong to the same run"}
        if not left.get("mesh_id") or left.get("mesh_id") != right.get("mesh_id"):
            return {**base, "reason": "mesh_id mismatch"}
        if left.get("oracle") != right.get("oracle"):
            return {**base, "reason": "oracle mismatch"}

        def fingerprints(report: dict[str, Any]) -> dict[str, tuple[Any, Any, Any]]:
            result = {}
            for item in report.get("input_artifact_refs") or []:
                if not isinstance(item, dict) or not item.get("artifact_id"):
                    continue
                result[str(item["artifact_id"])] = (
                    item.get("content_hash"),
                    item.get("revision"),
                    item.get("relative_path"),
                )
            return result

        left_inputs = fingerprints(left)
        right_inputs = fingerprints(right)
        if not left_inputs or left_inputs != right_inputs:
            return {**base, "reason": "input artifact hashes or revisions mismatch"}
        left_metrics = left.get("metrics")
        right_metrics = right.get("metrics")
        if not isinstance(left_metrics, dict) or not isinstance(right_metrics, dict):
            return {**base, "reason": "both reports need numeric metrics"}
        relative = []
        for name in sorted(set(left_metrics) & set(right_metrics)):
            left_value = left_metrics[name]
            right_value = right_metrics[name]
            if (
                isinstance(left_value, bool)
                or isinstance(right_value, bool)
                or not isinstance(left_value, (int, float))
                or not isinstance(right_value, (int, float))
            ):
                continue
            delta = right_value - left_value
            relative.append(
                {
                    "metric": name,
                    "left": left_value,
                    "right": right_value,
                    "delta": delta,
                    "relative": delta / left_value if left_value else None,
                }
            )
        if not relative:
            return {**base, "reason": "no shared numeric metrics"}
        return {
            **base,
            "status": "PROXY",
            "run_id": left.get("run_id"),
            "mesh_id": left.get("mesh_id"),
            "oracle": left.get("oracle"),
            "comparison_scope": "same-live-invocation",
            "relative": relative,
            "reason": "comparison is descriptive and cannot close Product signoff",
        }

    def context(self, surface: str = "flow") -> dict[str, Any]:
        if surface not in {"product", "flow", "package", "lab", "tools"}:
            surface = "flow"
        refs = self.catalog.list(limit=2000)

        # Package and Lab are intentionally ASAP7-first surfaces. Keep their
        # runtime context independent from the course's Nangate45 finish so a
        # valid lab artifact can never be mistaken for Product signoff.
        if surface in {"package", "lab"}:
            lab_variant = self._current_asap7_variant()
            finish = [
                ref.to_dict()
                for ref in refs
                if ref.authority == "finish"
                and ref.variant == lab_variant
                and "/results/asap7/" in f"/{ref.relative_path}"
            ]
            return {
                "schema_version": 1,
                "surface": surface,
                "design_id": "gcd",
                "pdk_id": "asap7",
                "profile": "asap7-lab",
                "run_id": None,
                "finish": finish[:80],
                "candidates": [],
                "tool_versions": self.registry().get("tool_versions", {}),
                "finish_mutable": False,
                "comparison_scope": "same-live-invocation",
                "generated_at": utc_now(),
            }

        active_variant = os.environ.get("FLOW_VARIANT")
        if active_variant not in {"flowlab", "learn"}:
            flowlab_finish = (
                self.repo_root
                / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
            )
            learn_finish = (
                self.repo_root
                / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.odb"
            )
            active_variant = (
                "flowlab"
                if flowlab_finish.is_file()
                else "learn"
                if learn_finish.is_file()
                else "flowlab"
            )
        finish = [
            ref.to_dict()
            for ref in refs
            if ref.authority == "finish"
            and ref.variant == active_variant
            and "/results/nangate45/gcd/" in f"/{ref.relative_path}"
        ]
        candidates = [
            ref.to_dict()
            for ref in refs
            if ref.authority == "candidate"
        ]
        with self._lock:
            latest_run = max(
                self._runs.values(),
                key=lambda item: item.get("created_at", ""),
                default=None,
            )
        return {
            "schema_version": 1,
            "surface": surface,
            "design_id": "gcd",
            "pdk_id": "nangate45",
            "profile": "live",
            "run_id": latest_run.get("run_id") if latest_run else None,
            "finish": finish[:80],
            "candidates": candidates[:80],
            "tool_versions": self.registry().get("tool_versions", {}),
            "finish_mutable": False,
            "comparison_scope": "same-live-invocation",
            "generated_at": utc_now(),
        }

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        surface = str(payload.get("surface") or "flow")
        if surface not in {"product", "flow", "package", "lab"}:
            raise ValueError("invalid surface")
        run_id = str(payload.get("run_id") or f"run-{uuid.uuid4().hex}")
        if not _safe_id(run_id):
            raise ValueError("invalid run_id")
        profile = str(payload.get("profile") or "live")
        if profile == "flowlab-candidate" and surface != "flow":
            raise ValueError("FlowLab candidate runs require surface=flow")
        input_ids = [str(item) for item in payload.get("input_artifacts", [])]
        for artifact_id in input_ids:
            if not self.catalog.resolve(artifact_id):
                raise ValueError(f"unknown input artifact: {artifact_id}")
        candidate_metadata: dict[str, Any] = {}
        if profile == "flowlab-candidate":
            finish_refs = [
                ref
                for ref in self.catalog.list(
                    limit=2000,
                    variant="flowlab",
                    authority="finish",
                )
                if "/results/nangate45/gcd/" in f"/{ref.relative_path}"
            ]
            input_ids.extend(
                ref.artifact_id for ref in finish_refs if ref.artifact_id not in input_ids
            )
        else:
            finish_refs = []
        context = RunContext(
            run_id=run_id,
            surface=surface,
            design_id=str(payload.get("design_id") or "gcd"),
            pdk_id=str(payload.get("pdk_id") or "nangate45"),
            profile=profile,
            created_at=utc_now(),
            input_artifacts=input_ids,
            tool_versions=self.registry().get("tool_versions", {}),
            environment={
                key: value
                for key, value in os.environ.items()
                if key in {"PATH", "DISPLAY", "WAYLAND_DISPLAY", "PD_FLOW_VARIANT"}
            },
        )
        run_dir = self.run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        try:
            record = {
                **context.to_dict(),
                "run_dir": str(run_dir.relative_to(self.repo_root)),
            }
            if profile == "flowlab-candidate":
                candidate_root = run_dir / "candidate"
                candidate_rtl = candidate_root / "inputs" / "gcd.v"
                candidate_params = candidate_root / "inputs" / "params.json"
                source_rtl = self.repo_root / "learn" / "flowlab" / "gcd.v"
                source_params = self.repo_root / "learn" / "flowlab" / "params.json"
                if not source_rtl.is_file():
                    raise FileNotFoundError("FlowLab RTL source is missing")
                self._copy_snapshot(source_rtl, candidate_rtl)
                if source_params.is_file():
                    self._copy_snapshot(source_params, candidate_params)
                candidate_metadata = {
                    "workspace": "candidate",
                    "candidate_root": str(candidate_root.relative_to(self.repo_root)),
                    "candidate_work_home": str(
                        (candidate_root / "orfs").relative_to(self.repo_root)
                    ),
                    "candidate_rtl": str(candidate_rtl.relative_to(self.repo_root)),
                    "base_finish": [ref.to_dict() for ref in finish_refs],
                }
                record.update(candidate_metadata)
            atomic_write_json(run_dir / "manifest.json", record)
        except Exception:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise
        with self._lock:
            self._runs[run_id] = record
        self._emit("run.created", {"run": record})
        return record

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            active = list(self._runs.values())
        return active

    def _analysis_run_path(self, record: dict[str, Any]) -> Path:
        analysis_run_id = str(record.get("analysis_run_id") or "")
        if not _safe_id(analysis_run_id):
            raise ValueError("invalid analysis_run_id")
        run_id = record.get("run_id")
        if isinstance(run_id, str) and _safe_id(run_id):
            return self.run_root / run_id / "analysis-runs" / f"{analysis_run_id}.json"
        return self.agent_root / "analysis-runs" / f"{analysis_run_id}.json"

    def _persist_analysis_run(self, record: dict[str, Any]) -> None:
        atomic_write_json(self._analysis_run_path(record), record)

    @staticmethod
    def _analysis_payload(
        payload: dict[str, Any],
    ) -> tuple[str, str, str | None, str, list[str] | None, dict[str, Any]]:
        stage = str(payload.get("stage") or payload.get("checkpoint") or "finish")
        variant = str(payload.get("variant") or "")
        run_id = payload.get("run_id")
        run_id = str(run_id) if run_id else None
        bundle_id = str(payload.get("bundle_id") or "recommended")
        raw_check_ids = payload.get("check_ids")
        if raw_check_ids is not None:
            if not isinstance(raw_check_ids, list) or len(raw_check_ids) > 32:
                raise ValueError("check_ids must be an array with at most 32 entries")
            check_ids = [str(item) for item in raw_check_ids]
            if any(not re.fullmatch(r"[a-z0-9_]{2,80}", item) for item in check_ids):
                raise ValueError("invalid analysis check id")
        else:
            check_ids = None
        raw_parameters = payload.get("parameters", {})
        if raw_parameters is None:
            raw_parameters = {}
        if not isinstance(raw_parameters, dict):
            raise ValueError("analysis parameters must be an object")
        return stage, variant, run_id, bundle_id, check_ids, raw_parameters

    def _analysis_policy(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], str, str, str | None, str, list[str] | None, dict[str, Any]]:
        stage, variant, run_id, bundle_id, check_ids, parameters = self._analysis_payload(payload)
        policy = self.checks(stage=stage, variant=variant or None, run_id=run_id)
        registry = self.registry()
        actions = registry.get("actions", [])
        plan = build_bundle_plan(
            bundle_id=bundle_id,
            policy=policy,
            action_registry=actions if isinstance(actions, list) else [],
            requested_check_ids=check_ids,
            parameters=parameters,
        )
        try:
            resource = self.resources.preflight()
        except ResourceRunnerError as exc:
            resource = {"available": False, "reason": str(exc)}
        plan["resource_preflight"] = resource
        if not resource.get("available"):
            plan["ready"] = False
            plan["resource_blocking_reason"] = (
                "resource isolation unavailable: "
                + str(resource.get("reason") or "unknown reason")
            )
        return policy, plan, stage, str(plan.get("variant") or variant), run_id, bundle_id, check_ids, parameters

    def preview_analysis_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a read-only bundle preflight; no run or job is created."""

        _policy, plan, *_ = self._analysis_policy(payload)
        return plan

    def create_analysis_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist an explicit analysis plan and its immutable context."""

        policy, plan, stage, variant, run_id, bundle_id, check_ids, parameters = self._analysis_policy(payload)
        if run_id is not None and not _safe_id(run_id):
            raise ValueError("invalid run_id")
        if run_id is None:
            surface = "package" if stage == "package" else "lab" if variant.startswith("lab_asap7_") else "flow"
            context = self.create_run(
                {
                    "surface": surface,
                    "profile": "analysis-workbench",
                    "design_id": "gcd",
                    "pdk_id": "asap7" if variant.startswith("lab_asap7_") else "nangate45",
                }
            )
            run_id = str(context["run_id"])
            # Re-evaluate the plan with the newly created context so its
            # provenance and candidate-aware eligibility are explicit.
            next_payload = dict(payload)
            next_payload["run_id"] = run_id
            policy, plan, stage, variant, run_id, bundle_id, check_ids, parameters = self._analysis_policy(next_payload)
        elif run_id not in self._runs:
            raise ValueError("analysis run references an unknown PDflow run")
        analysis_run_id = str(payload.get("analysis_run_id") or f"analysis-{uuid.uuid4().hex}")
        if not _safe_id(analysis_run_id):
            raise ValueError("invalid analysis_run_id")
        record = {
            "schema_version": 1,
            "analysis_run_id": analysis_run_id,
            "run_id": run_id,
            "stage": stage,
            "variant": variant,
            "bundle_id": bundle_id,
            "check_ids": plan.get("check_ids", check_ids or []),
            "parameters": parameters,
            "state": "PLANNED",
            "created_at": utc_now(),
            "jobs": [],
            "plan": plan,
            "policy_snapshot": {
                "stage": policy.get("stage"),
                "variant": policy.get("variant"),
                "run_id": policy.get("run_id"),
            },
        }
        self._persist_analysis_run(record)
        with self._lock:
            self._analysis_runs[analysis_run_id] = record
        self._emit("analysis-run.created", {"analysis_run": dict(record)})
        return record

    def get_analysis_run(self, analysis_run_id: str) -> dict[str, Any] | None:
        if not _safe_id(analysis_run_id):
            return None
        with self._lock:
            record = self._analysis_runs.get(analysis_run_id)
            if record is None:
                return None
            snapshot = dict(record)
        jobs = []
        for job_id in snapshot.get("jobs", []):
            if isinstance(job_id, str):
                job = self.get_job(job_id)
                if job is not None:
                    jobs.append(job)
        snapshot["job_records"] = jobs
        if jobs:
            states = {str(job.get("state")) for job in jobs}
            if states & {"QUEUED", "RUNNING"}:
                snapshot["state"] = "RUNNING" if "RUNNING" in states else "QUEUED"
            elif states <= {"COMPLETED"}:
                snapshot["state"] = "COMPLETED"
            elif "CANCELLED" in states and not (states - {"CANCELLED", "COMPLETED"}):
                snapshot["state"] = "CANCELLED"
            else:
                snapshot["state"] = "FAILED"
        return snapshot

    def list_analysis_runs(self, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._analysis_runs)
        records = [self.get_analysis_run(item) for item in ids]
        records = [item for item in records if item is not None]
        records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return records[: max(1, min(int(limit), 200))]

    def execute_analysis_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Queue a confirmed bundle through the normal single-slot agent."""

        analysis_run_id = str(payload.get("analysis_run_id") or "")
        if analysis_run_id:
            record = self.get_analysis_run(analysis_run_id)
            if record is None:
                raise ValueError("analysis_run_id not found")
        else:
            record = self.create_analysis_run(payload)
        existing_job_ids = [
            item for item in record.get("jobs", []) if isinstance(item, str) and _safe_id(item)
        ]
        if existing_job_ids:
            current = self.get_analysis_run(str(record.get("analysis_run_id"))) or record
            current_state = str(current.get("state") or "")
            if current_state in {"QUEUED", "RUNNING", "COMPLETED"}:
                return {
                    "status": current_state,
                    "ok": current_state == "COMPLETED" or current_state in {"QUEUED", "RUNNING"},
                    "reused": True,
                    "analysis_run": current,
                    "plan": current.get("plan", {}),
                    "jobs": current.get("job_records", []),
                    "principle": "an analysis run is single-use; an active or completed run is never queued twice",
                }
            raise ValueError(
                "analysis run already executed; create a new analysis_run for a retry"
            )
        if payload.get("confirm") is not True:
            return {
                "status": "PREVIEW",
                "ok": False,
                "requires_confirmation": True,
                "analysis_run": record,
                "plan": record.get("plan", {}),
                "principle": "analysis bundles require explicit confirmation before any job is queued",
            }
        plan = record.get("plan")
        if not isinstance(plan, dict):
            raise ValueError("analysis run has no preflight plan")
        if not plan.get("ready"):
            return {
                "status": "GAP",
                "ok": False,
                "analysis_run": record,
                "plan": plan,
                "reason": plan.get("resource_blocking_reason") or "analysis bundle is not runnable",
            }
        run_id = str(record.get("run_id") or "")
        variant = str(record.get("variant") or "")
        candidate_run_id = None
        run_record = self._runs.get(run_id)
        if isinstance(run_record, dict) and run_record.get("profile") == "flowlab-candidate":
            candidate_run_id = run_id
        job_ids: list[str] = []
        submissions: list[dict[str, Any]] = []
        for item in plan.get("jobs", []):
            if not isinstance(item, dict) or not item.get("runnable"):
                continue
            parameters = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
            job_payload = {
                "action": item.get("action"),
                "operation": "action",
                "variant": variant,
                "mode": "view",
                "run_id": run_id,
                "candidate_run_id": candidate_run_id,
                # The persisted run checkpoint is authoritative.  A caller
                # must not smuggle a different checkpoint through the
                # per-check parameter map after preflight.
                "parameters": {**parameters, "checkpoint": record.get("stage")},
            }
            submitted = self.submit_job(job_payload)
            submissions.append(submitted)
            if submitted.get("state") in {"QUEUED", "RUNNING"}:
                job_ids.append(str(submitted["job_id"]))
            else:
                # A race with a changed artifact/dependency must not cause the
                # rest of a bundle to run under a different precondition.
                break
        record["jobs"] = job_ids
        record["state"] = "QUEUED" if job_ids else "GAP"
        record["submissions"] = submissions
        self._persist_analysis_run(record)
        with self._lock:
            self._analysis_runs[str(record["analysis_run_id"])] = record
        self._emit("analysis-run.queued", {"analysis_run": dict(record)})
        return {
            "status": "QUEUED" if job_ids else "GAP",
            "ok": bool(job_ids),
            "analysis_run": self.get_analysis_run(str(record["analysis_run_id"])),
            "plan": plan,
            "jobs": submissions,
        }

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def job_log_path(self, job_id: str) -> Path | None:
        """Resolve a job log without allowing paths outside agent-owned storage."""

        if not _safe_id(job_id):
            return None
        job = self.get_job(job_id)
        if not job:
            return None
        relative = job.get("log_path")
        if not isinstance(relative, str) or not relative:
            return None
        try:
            candidate = (self.repo_root / relative).resolve()
            allowed_roots = (self.agent_root.resolve(), self.run_root.resolve())
            if not any(
                candidate == root or root in candidate.parents
                for root in allowed_roots
            ):
                return None
            return candidate if candidate.is_file() else None
        except OSError:
            return None

    def list_jobs(self, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return [dict(job) for job in jobs[: max(1, min(limit, 200))]]

    def _job_gap(
        self,
        *,
        job_id: str,
        tool_id: str,
        operation: str,
        reason: str,
        run_id: str | None,
        artifact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report = ReportEnvelope.gap(
            report_id=f"report-{uuid.uuid4().hex}",
            reason=reason,
            run_id=run_id,
            scope="generated",
        ).to_dict()
        report["job_id"] = job_id
        report["operation"] = operation
        if artifact:
            report["input_artifacts"] = [str(artifact.get("artifact_id"))]
            report["input_artifact_refs"] = [artifact]
        report_path = self._persist_report(report, run_id, job_id)
        if report_path:
            report["report_paths"] = [report_path]
        job = {
            "job_id": job_id,
            "tool_id": tool_id,
            "operation": operation,
            "state": "GAP",
            "created_at": utc_now(),
            "finished_at": utc_now(),
            "run_id": run_id,
            "artifact": artifact,
            "reason": reason,
            "report": report,
            "log_tail": "",
        }
        job["resource"] = self.resources.describe()
        report["resource"] = job["resource"]
        with self._lock:
            self._jobs[job_id] = job
        self._persist_job(job)
        self._emit("dependency.gap", {"job": job})
        return dict(job)

    def _persist_report(
        self,
        report: dict[str, Any],
        run_id: str | None,
        job_id: str,
    ) -> str | None:
        if not run_id:
            return None
        if not _safe_id(run_id):
            return None
        errors = validate_report(report)
        if errors:
            self._emit(
                "agent.warning",
                {"message": "report rejected by contract", "errors": errors},
            )
            return None
        report_dir = self.run_root / run_id / "reports"
        report_path = report_dir / f"{job_id}.json"
        try:
            atomic_write_json(report_path, report)
            return str(report_path.relative_to(self.repo_root))
        except OSError:
            return None

    def _active_batch_job(self) -> dict[str, Any] | None:
        for job in self._jobs.values():
            if (
                job.get("state") in {"QUEUED", "RUNNING"}
                and job.get("operation") != "gui"
            ):
                return job
        return None

    def _active_artifact_job(self, artifact: Any) -> dict[str, Any] | None:
        if artifact is None:
            return None
        for job in self._jobs.values():
            if job.get("state") not in {"QUEUED", "RUNNING"}:
                continue
            current = job.get("artifact") or {}
            if current.get("relative_path") == artifact.relative_path:
                return job
        return None

    def _artifact_snapshot(self) -> dict[str, tuple[int, int, str | None]]:
        return {
            ref.relative_path: (ref.size, ref.mtime_ns, ref.content_hash)
            for ref in self.catalog.list(limit=2000)
        }

    def _changed_artifacts(
        self,
        before: dict[str, tuple[int, int, str | None]],
    ) -> list[Any]:
        changed = []
        for ref in self.catalog.list(limit=2000):
            current = (ref.size, ref.mtime_ns, ref.content_hash)
            if before.get(ref.relative_path) != current:
                changed.append(ref)
        return changed

    @staticmethod
    def _flowlab_stage_environment(payload: dict[str, Any]) -> dict[str, str]:
        """Convert typed FlowLab controls into a small allowlisted env map."""

        raw = payload.get("parameters", payload.get("params", {}))
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("FlowLab parameters must be a JSON object")
        unknown = sorted(set(str(key) for key in raw) - set(_FLOWLAB_PARAMETER_KEYS))
        if unknown:
            raise ValueError("unsupported FlowLab parameter: " + unknown[0])

        result: dict[str, str] = {}
        for key, env_name in _FLOWLAB_PARAMETER_KEYS.items():
            if key not in raw:
                continue
            value = raw[key]
            if env_name == "PD_FLOW_CHECKPOINT":
                allowed = {"floorplan", "pdn", "place", "cts", "route", "finish"}
                if not isinstance(value, str) or value not in allowed:
                    raise ValueError("checkpoint must be a physical FlowLab stage")
                result[env_name] = value
                continue
            if env_name == "SDC_FILE":
                presets = {
                    "default": "./designs/nangate45/gcd-tutorial/constraint.sdc",
                    "relaxed": "./designs/nangate45/gcd-tutorial/constraint_relaxed.sdc",
                    "tight": "./designs/nangate45/gcd-tutorial/constraint_tight.sdc",
                }
                if not isinstance(value, str) or value not in presets:
                    raise ValueError("sdcPreset must be default, relaxed or tight")
                result[env_name] = presets[str(value)]
                continue
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
            if not math.isfinite(number):
                raise ValueError(f"{key} must be finite")
            if env_name == "CORE_UTILIZATION" and not 20 <= number <= 60:
                raise ValueError("coreUtilization must be between 20 and 60")
            if env_name == "PLACE_DENSITY_LB_ADDON" and not 0.05 <= number <= 0.45:
                raise ValueError("placeDensityAddon must be between 0.05 and 0.45")
            if env_name == "ABC_AREA" and number not in {0, 1}:
                raise ValueError("abcArea must be 0 or 1")
            if env_name == "TNS_END_PERCENT" and not 0 <= number <= 100:
                raise ValueError("tnsEndPercent must be between 0 and 100")
            result[env_name] = str(int(number) if number.is_integer() else number)
        return result

    def _system_pdn_environment(
        self,
        payload: dict[str, Any],
        variant: str,
        run_id: str | None,
    ) -> dict[str, str]:
        """Materialize a safe, run-scoped System PDN experiment.

        The browser only supplies engineering-unit knobs.  The agent owns the
        source configuration, converts those knobs to SI values, and places
        the resulting deck/report workspace below the already-created PDflow
        run.  This keeps an experiment reproducible without allowing a UI
        request to overwrite the canonical Package report.
        """

        raw = payload.get("parameters", payload.get("params", {}))
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("System PDN parameters must be a JSON object")
        allowed = set(_SYSTEM_PDN_PARAMETER_RANGES) | {"checkpoint"}
        unknown = sorted(set(str(key) for key in raw) - allowed)
        if unknown:
            raise ValueError("unsupported System PDN parameter: " + unknown[0])
        if not raw:
            return {}
        if not run_id or not _safe_id(run_id):
            raise ValueError("System PDN experiments require a valid run_id")
        with self._lock:
            known_run = run_id in self._runs
        if not known_run:
            raise ValueError("System PDN experiment references an unknown run")

        checkpoint = raw.get("checkpoint")
        if checkpoint is not None and str(checkpoint) != "package":
            raise ValueError("System PDN checkpoint must be package")

        controls: dict[str, float] = {}
        for key, (minimum, maximum) in _SYSTEM_PDN_PARAMETER_RANGES.items():
            if key not in raw:
                continue
            value = raw[key]
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
            if not math.isfinite(number) or not minimum <= number <= maximum:
                raise ValueError(
                    f"{key} must be finite and between {minimum:g} and {maximum:g}"
                )
            controls[key] = number

        run_dir = (self.run_root / run_id).resolve()
        try:
            run_dir.relative_to(self.run_root.resolve())
        except ValueError as exc:
            raise ValueError("System PDN run escaped the run root") from exc
        scenario_dir = run_dir / "system-pdn"
        scenario_dir.mkdir(parents=True, exist_ok=True)

        source_relative = (
            "learn/lab/asap7/pkg/asap7_system_pdn.json"
            if variant.startswith("lab_asap7_")
            else "learn/system_pdn/default.json"
        )
        source_path = (self.repo_root / source_relative).resolve()
        try:
            source_path.relative_to(self.repo_root.resolve())
            config = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"System PDN config is unavailable for variant {variant}"
            ) from exc
        if not isinstance(config, dict):
            raise ValueError("canonical System PDN config must be an object")

        def section(name: str) -> dict[str, Any]:
            value = config.get(name)
            if not isinstance(value, dict):
                raise ValueError(f"canonical System PDN config section is invalid: {name}")
            return value

        board = section("board")
        package = section("package")
        ac = section("ac")
        tran = section("tran")
        if "board_l_nh" in controls:
            board["l_plane"] = controls["board_l_nh"] * 1e-9
        if "package_r_mohm" in controls:
            package["r_pkg"] = controls["package_r_mohm"] * 1e-3
        if "package_l_nh" in controls:
            package["l_pkg"] = controls["package_l_nh"] * 1e-9
        if "board_bulk_uf" in controls:
            board["c_bulk"] = controls["board_bulk_uf"] * 1e-6
        if "package_c_pf" in controls:
            package["c_pkg"] = controls["package_c_pf"] * 1e-12
        if "target_z_mohm" in controls:
            ac["z_target_mohm"] = controls["target_z_mohm"]
        if "peak_factor" in controls:
            tran["i_peak_factor"] = controls["peak_factor"]
        for key in ("edge_ns", "delay_ns", "pulse_width_ns"):
            if key in controls:
                tran[key] = controls[key]

        config["pdflow_scenario"] = {
            "source_config": source_relative,
            "variant": variant,
            "run_id": run_id,
            "checkpoint": "package",
            "controls": {
                key: int(value) if value.is_integer() else value
                for key, value in controls.items()
            },
            "created_at": utc_now(),
        }
        config_path = scenario_dir / "config.json"
        atomic_write_json(config_path, config)

        solver_dir = scenario_dir / "solver"
        compatibility_dir = scenario_dir / "compatibility"
        report_path = scenario_dir / "report.json"
        log_path = scenario_dir / "system_pdn.log"
        environment = {
            "SYSTEM_PDN_CONFIG": str(config_path),
            "PD_FLOW_SYSTEM_PDN_OUTPUT_DIR": str(compatibility_dir),
            "PD_FLOW_SYSTEM_PDN_WORK_DIR": str(scenario_dir / "work"),
            "PD_FLOW_SYSTEM_PDN_RUN_DIR": str(solver_dir),
            "PD_FLOW_SYSTEM_PDN_REPORT": str(report_path),
            "PD_FLOW_SYSTEM_PDN_LOG": str(log_path),
            "PD_FLOW_SYSTEM_PDN_RUN_ID": run_id,
        }
        if "die_current_ma" in controls:
            environment["I_DIE_AVG"] = f"{controls['die_current_ma'] * 1e-3:.12g}"
        return environment

    @staticmethod
    def _analysis_checkpoint_environment(
        payload: dict[str, Any], action_id: str | None = None
    ) -> dict[str, str]:
        """Validate typed overrides for a checkpoint analysis action.

        Analysis jobs deliberately receive a smaller parameter surface than
        FlowLab recooks.  This prevents a UI form from accidentally leaking
        synthesis/placement settings into a read-only report job and keeps
        every environment variable mapped to an adapter-owned control.
        """

        raw = payload.get("parameters", payload.get("params", {}))
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("analysis parameters must be a JSON object")
        allowed = _ANALYSIS_PARAMETER_KEYS.get(action_id or "", {"checkpoint"})
        unknown = sorted(set(str(key) for key in raw) - allowed)
        if unknown:
            raise ValueError("unsupported analysis parameter: " + unknown[0])

        def number(key: str, *, minimum: float, maximum: float) -> str:
            value = raw.get(key)
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                parsed = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
            if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
                raise ValueError(
                    f"{key} must be finite and between {minimum:g} and {maximum:g}"
                )
            return str(int(parsed) if parsed.is_integer() else parsed)

        checkpoint = raw.get("checkpoint")
        result: dict[str, str] = {}
        if checkpoint is not None and (
            not isinstance(checkpoint, str) or checkpoint not in _ANALYSIS_CHECKPOINTS
        ):
            raise ValueError("checkpoint must be a physical analysis stage")
        if checkpoint is not None:
            result["PD_FLOW_CHECKPOINT"] = checkpoint

        if action_id == "gridcheck":
            net = raw.get("net")
            if net is not None:
                normalized = str(net).upper()
                if normalized not in {"VDD", "VSS", "BOTH"}:
                    raise ValueError("net must be VDD, VSS or BOTH")
                result["PD_FLOW_GRID_NET"] = normalized
            require_terminals = raw.get("require_terminals")
            if require_terminals is not None:
                if not isinstance(require_terminals, bool):
                    raise ValueError("require_terminals must be boolean")
                result["PD_FLOW_GRID_REQUIRE_TERMINALS"] = (
                    "1" if require_terminals else "0"
                )

        if action_id == "sta_checkpoint":
            mode = raw.get("mode")
            if mode is not None:
                normalized = str(mode).lower()
                if normalized not in {"setup", "hold"}:
                    raise ValueError("mode must be setup or hold")
                result["STA_MODE"] = normalized
            max_paths = raw.get("max_paths")
            if max_paths is not None:
                result["STA_MAX_PATHS"] = number(
                    "max_paths", minimum=1, maximum=1000
                )

        if action_id in {"chip_pdn_ir", "dynamic_ir", "power_grid_em"}:
            numeric_limits = {
                "package_resistance": (0.0, 1000.0, "PKG_R"),
                "package_inductance": (0.0, 1.0, "PKG_L"),
                "c_decap": (0.0, 1e-6, "C_DECAP"),
                "peak_factor": (1.0, 32.0, "PEAK_FACTOR"),
            }
            if action_id == "power_grid_em":
                numeric_limits.update(
                    {
                        "ir_limit_pct": (0.01, 100.0, "IR_LIMIT_PCT"),
                        "switch_t_ns": (0.0, 10000.0, "SWITCH_T_NS"),
                        "switch_dur_ns": (0.001, 1000.0, "SWITCH_DUR_NS"),
                    }
                )
            for key, (minimum, maximum, env_name) in numeric_limits.items():
                if key in raw:
                    result[env_name] = number(
                        key, minimum=minimum, maximum=maximum
                    )
            if action_id == "dynamic_ir":
                mode = raw.get("mode")
                if mode is not None:
                    normalized = str(mode).lower()
                    if normalized not in {"clock", "spatial", "simultaneous"}:
                        raise ValueError(
                            "mode must be clock, spatial or simultaneous"
                        )
                    result["DYNAMIC_IR_MODE"] = normalized
                for key, minimum, maximum, env_name in (
                    ("period_ns", 0.001, 100000.0, "PERIOD_NS"),
                    ("duration_ns", 0.001, 100000.0, "DUR_NS"),
                    ("timestep_ps", 0.001, 100000.0, "DT_PS"),
                ):
                    if key in raw:
                        result[env_name] = number(
                            key, minimum=minimum, maximum=maximum
                        )
        return result

    def _current_asap7_variant(self) -> str:
        """Resolve the latest known ASAP7 variant without trusting a path input."""

        preferred = "lab_asap7_gcd_tc_rvt_nldm_7p5"
        report = self.repo_root / "learn" / "sim" / "reports" / "lab_asap7.json"
        try:
            raw = json.loads(report.read_text(encoding="utf-8"))
            candidate = str(raw.get("variant") or "")
            if is_lab_variant(candidate):
                return candidate
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
        root = (
            self.repo_root
            / "tools"
            / "OpenROAD-flow-scripts"
            / "flow"
            / "results"
            / "asap7"
            / "gcd"
        )
        if (root / preferred / "6_final.odb").is_file():
            return preferred
        variants = sorted(
            item.name
            for item in root.iterdir()
            if item.is_dir()
            and is_lab_variant(item.name)
            and (item / "6_final.odb").is_file()
        ) if root.is_dir() else []
        return variants[-1] if variants else preferred

    @staticmethod
    def _asap7_lab_environment(payload: dict[str, Any]) -> dict[str, str]:
        """Validate the small, typed ASAP7 profile accepted by lab adapters."""

        raw = payload.get("parameters", payload.get("params", {}))
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("ASAP7 parameters must be a JSON object")
        unknown = sorted(set(str(key) for key in raw) - _LAB_ASAP7_PARAMETER_KEYS)
        if unknown:
            raise ValueError("unsupported ASAP7 parameter: " + unknown[0])

        result: dict[str, str] = {}
        requested_variant = raw.get("variant")
        if requested_variant is not None:
            value = str(requested_variant)
            if not is_lab_variant(value):
                raise ValueError("ASAP7 variant is invalid")
            result["LAB_ASAP7_VARIANT"] = value

        design = raw.get("design")
        if design is not None:
            value = str(design)
            if value not in _LAB_ASAP7_DESIGNS:
                raise ValueError("ASAP7 design is not in the supported lab allowlist")
            result["LAB_ASAP7_DESIGN"] = value

        corner = raw.get("corner")
        if corner is not None:
            value = str(corner).upper()
            if value not in _LAB_ASAP7_CORNERS:
                raise ValueError("ASAP7 corner must be BC, TC or WC")
            result["CORNER"] = value

        vt = raw.get("vt")
        if vt is not None:
            values = vt if isinstance(vt, list) else re.split(r"[+,\\s]+", str(vt))
            normalized = [str(item).upper() for item in values if str(item).strip()]
            allowed = {"RVT", "LVT", "SLVT", "SRAM"}
            if not normalized or any(item not in allowed for item in normalized):
                raise ValueError("ASAP7 vt contains an unsupported library")
            result["ASAP7_USE_VT"] = " ".join(dict.fromkeys(normalized))

        lib_model = raw.get("lib_model")
        if lib_model is not None:
            value = str(lib_model).upper()
            if value not in _LAB_ASAP7_LIB_MODELS:
                raise ValueError("ASAP7 lib_model must be NLDM or CCS")
            result["LIB_MODEL"] = value

        track = raw.get("track")
        if track is not None:
            value = str(track)
            if value not in _LAB_ASAP7_TRACKS:
                raise ValueError("ASAP7 track must be 7p5 or 6")
            result["ASAP7_TRACK"] = value

        clk_ps = raw.get("clk_ps")
        if clk_ps is not None:
            if isinstance(clk_ps, bool):
                raise ValueError("ASAP7 clk_ps must be numeric")
            try:
                value = int(clk_ps)
            except (TypeError, ValueError) as exc:
                raise ValueError("ASAP7 clk_ps must be an integer") from exc
            if not 100 <= value <= 5000:
                raise ValueError("ASAP7 clk_ps must be between 100 and 5000")
            result["LAB_CLK_PS"] = str(value)

        cluster = raw.get("cluster_flops")
        if cluster is not None:
            if isinstance(cluster, bool):
                value = cluster
            elif str(cluster).lower() in {"1", "true", "yes"}:
                value = True
            elif str(cluster).lower() in {"0", "false", "no"}:
                value = False
            else:
                raise ValueError("ASAP7 cluster_flops must be boolean")
            result["CLUSTER_FLOPS"] = "1" if value else "0"
        return result

    def _layout_preview_environment(
        self,
        payload: dict[str, Any],
        variant: str,
    ) -> tuple[dict[str, str], Any]:
        """Resolve a preview input without allowing the web server to spawn tools.

        Preview rendering is a generated artifact, but its input still needs
        the same provenance and candidate isolation as every other agent job.
        Return the catalog reference so the resulting report records the ODB
        hash instead of treating the render as an anonymous side effect.
        """

        phase = str(payload.get("preview_phase") or "")
        if phase not in _LAYOUT_PREVIEW_ODB:
            raise ValueError("invalid layout preview phase")
        if variant not in {"flowlab", "learn", "eco_scratch"} and not is_lab_variant(variant):
            raise ValueError("invalid layout preview variant")
        raw_run_id = payload.get("run_id")
        run_id = str(raw_run_id) if raw_run_id else ""
        if run_id:
            candidate_root, _ = self._candidate_workspace(run_id)
            if variant != "flowlab":
                raise ValueError("candidate previews require the FlowLab variant")
            relative = (
                Path(".pdflow")
                / "runs"
                / run_id
                / "candidate"
                / "orfs"
                / "results/nangate45/gcd/flowlab"
                / _LAYOUT_PREVIEW_ODB[phase]
            ).as_posix()
            output_root = candidate_root / "orfs" / "previews" / "flowlab"
        else:
            result_tree = "asap7/gcd" if is_lab_variant(variant) else "nangate45/gcd"
            relative = (
                Path("tools/OpenROAD-flow-scripts/flow/results")
                / result_tree
                / variant
                / _LAYOUT_PREVIEW_ODB[phase]
            ).as_posix()
            output_root = self.repo_root / "learn" / "sim" / "previews" / variant
        artifact = self.catalog.resolve_path(relative)
        if artifact is None:
            raise FileNotFoundError(f"layout preview input ODB is missing: {relative}")
        environment = {
            "PD_FLOW_PREVIEW_PHASE": phase,
            "PD_FLOW_PREVIEW_VARIANT": variant,
        }
        if run_id:
            environment["PD_FLOW_PREVIEW_RUN_ID"] = run_id
        # Keep the resolved output in the method as an assertion: the shell
        # adapter derives the same path and may not write anywhere else.
        expected_output = output_root / f"{phase}.png"
        try:
            expected_output.parent.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            raise ValueError("layout preview output escaped repository root")
        return environment, artifact

    def _inspect_environment(
        self,
        payload: dict[str, Any],
        variant: str,
        run_id: str | None,
        job_id: str,
    ) -> tuple[dict[str, str], Any]:
        """Resolve the bounded native-inspection workspace and input artifact."""

        raw = payload.get("parameters", payload.get("params", {}))
        if not isinstance(raw, dict):
            raise ValueError("inspection parameters must be a JSON object")
        unknown = sorted(set(str(key) for key in raw) - {"stage"})
        if unknown:
            raise ValueError("unsupported inspection parameter: " + unknown[0])
        stage = str(raw.get("stage") or "")
        if stage not in _INSPECT_STAGE_ARTIFACTS:
            raise ValueError("invalid inspection stage")
        if variant not in {"flowlab", "learn", "eco_scratch"} and not is_lab_variant(variant):
            raise ValueError("invalid inspection variant")

        if run_id:
            candidate_root, _ = self._candidate_workspace(run_id)
            if variant != "flowlab":
                raise ValueError("candidate inspection requires the FlowLab variant")
            root = candidate_root / "orfs" / "results" / "nangate45" / "gcd" / "flowlab"
        else:
            result_tree = "asap7" if is_lab_variant(variant) else "nangate45"
            root = (
                self.repo_root
                / "tools"
                / "OpenROAD-flow-scripts"
                / "flow"
                / "results"
                / result_tree
                / "gcd"
                / variant
            )
        root = root.resolve()
        try:
            root.relative_to(self.repo_root.resolve())
        except ValueError as exc:
            raise ValueError("inspection root escaped repository") from exc
        odb_name, _ = _INSPECT_STAGE_ARTIFACTS[stage]
        relative = root.joinpath(odb_name).relative_to(self.repo_root).as_posix()
        artifact = self.catalog.resolve_path(relative)
        if artifact is None:
            raise FileNotFoundError(f"missing inspection ODB artifact: {relative}")
        output = (self.agent_root / "inspect" / f"{job_id}.json").resolve()
        try:
            output.relative_to(self.agent_root.resolve())
        except ValueError as exc:
            raise ValueError("inspection output escaped agent root") from exc
        return (
            {
                "PD_FLOW_INSPECT_STAGE": stage,
                "PD_FLOW_INSPECT_VARIANT": variant,
                "PD_FLOW_INSPECT_ROOT": str(root),
                "PD_FLOW_INSPECT_REPO_ROOT": str(self.repo_root),
                "PD_FLOW_INSPECT_OUTPUT": str(output),
            },
            artifact,
        )

    def _normalize_outputs(self, output_refs: list[Any]) -> dict[str, Any]:
        """Normalize action-generated JSON without trusting process exit alone."""

        status_rank = {
            "PASS": 0,
            "WARN": 1,
            "PROXY": 2,
            "PARTIAL": 3,
            "GAP": 4,
            "FAIL": 5,
            "NOT_RUN": 6,
        }
        statuses: list[str] = []
        reasons: list[str] = []
        metadata: dict[str, Any] = {}
        for ref in output_refs:
            if ref.kind != "json":
                continue
            try:
                value = json.loads(self.catalog.path_for(ref).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            raw = str(value.get("status") or "").upper()
            if raw not in status_rank:
                if value.get("ok") is False:
                    raw = "FAIL"
                else:
                    continue
            elif raw == "PASS" and value.get("ok") is False:
                raw = "FAIL"
            statuses.append(raw)
            reason = value.get("reason") or value.get("summary")
            if reason and raw != "PASS":
                reasons.append(str(reason))
            for key in (
                "mesh_id",
                "oracle",
                "metrics",
                "relative",
                "required_checks",
                "comparison_scope",
                "execution_status",
                "evidence_status",
                "requirement_status",
                "signoff_status",
                "product_signoff",
                "checkpoint_id",
                "configuration_hash",
                "tool_versions",
                "units",
                "corner",
                "mode",
                "activity_source",
                "limitations",
            ):
                if key not in metadata and key in value:
                    metadata[key] = value[key]
        if not statuses:
            return {}
        status = max(statuses, key=lambda item: status_rank[item])
        metadata["status"] = status
        metadata["ok"] = status == "PASS"
        if reasons:
            metadata["reason"] = reasons[0]
        return metadata

    def submit_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = str(payload.get("job_id") or f"job-{uuid.uuid4().hex}")
        if not _safe_id(job_id):
            raise ValueError("invalid job_id")
        action_id = str(payload.get("action") or "")
        tool_id = str(payload.get("tool_id") or "")
        operation = str(payload.get("operation") or ("action" if action_id else "gui"))
        run_id = payload.get("run_id")
        run_id = str(run_id) if run_id else None
        candidate_run_id = payload.get("candidate_run_id")
        candidate_run_id = str(candidate_run_id) if candidate_run_id else None
        if candidate_run_id and candidate_run_id != run_id:
            raise ValueError("candidate_run_id must match run_id")
        mode = str(payload.get("mode") or "view")
        if mode not in {"view", "edit"}:
            raise ValueError("mode must be view or edit")
        raw_args = payload.get("args", [])
        if raw_args is None:
            raw_args = []
        if not isinstance(raw_args, list):
            raise ValueError("job args must be an array")
        artifact: Any = None
        candidate_analysis_inputs: list[Any] = []
        if payload.get("artifact_id"):
            artifact = self.catalog.resolve(str(payload["artifact_id"]))
        elif payload.get("artifact_path"):
            artifact = self.catalog.resolve_path(str(payload["artifact_path"]))
        if payload.get("artifact_id") or payload.get("artifact_path"):
            if artifact is None:
                return self._job_gap(
                    job_id=job_id,
                    tool_id=tool_id,
                    operation=operation,
                    reason="artifact missing or outside the allowlist",
                    run_id=run_id,
                )

        # An editable native session must always be tied to a registered
        # candidate run.  Intermediate ORFS checkpoints are canonical inputs
        # too; they are copied before launch just like the final GDS/ODB. A
        # mutable artifact from another run can never be edited through this
        # request, preventing cross-run writes and accidental finish changes.
        if mode == "edit":
            if not run_id or not _safe_id(run_id):
                raise ValueError("edit mode requires a valid candidate run_id")
            if artifact is None:
                raise ValueError("edit mode requires an artifact")
            if artifact.authority == "candidate":
                if artifact.run_id != run_id:
                    raise ValueError("candidate artifact belongs to another run")
            elif artifact.authority != "finish":
                raise ValueError("edit mode accepts only canonical or candidate artifacts")
        elif (
            artifact is not None
            and artifact.authority == "candidate"
            and run_id
            and artifact.run_id != run_id
        ):
            raise ValueError("candidate artifact belongs to another run")

        action_spec = None
        env_overrides: dict[str, str] = {}
        report_scope = "generated"
        report_versions: dict[str, str | None] = {}
        action_variant = active_variant(self.repo_root)
        report_mesh_id: str | None = None
        report_oracle: str | None = None
        report_comparison_scope = "none"
        web_port: int | None = None
        if action_id:
            action_spec = get_action(self.repo_root, action_id)
            if operation != "action":
                raise ValueError("registry actions must use operation=action")
            if action_spec.mutates and mode != "edit":
                raise ValueError("mutating action requires mode=edit and a candidate")
            if action_spec.mutates and not run_id:
                raise ValueError("mutating action requires run_id")
            registry = self.registry()
            by_tool = {
                item.get("tool_id"): item
                for item in registry.get("tools", [])
                if isinstance(item, dict)
            }
            action_variant = str(
                payload.get("variant")
                or os.environ.get("FLOW_VARIANT")
                or active_variant(self.repo_root)
            )
            if action_id.startswith("lab_asap7_") and not is_lab_variant(action_variant):
                action_variant = self._current_asap7_variant()
            flowlab_candidate_action = (
                action_id in _FLOWLAB_CANDIDATE_ACTIONS
                and action_variant == "flowlab"
            )
            flowlab_candidate_analysis = (
                action_id in _FLOWLAB_ANALYSIS_ACTIONS
                and action_variant == "flowlab"
                and candidate_run_id is not None
            )
            if action_id in _FLOWLAB_CANDIDATE_ACTIONS and not flowlab_candidate_action:
                if not is_lab_variant(action_variant):
                    raise ValueError("FlowLab stage actions require variant=flowlab")
            if flowlab_candidate_action or flowlab_candidate_analysis:
                if candidate_run_id:
                    candidate_root, work_home = self._candidate_workspace(candidate_run_id)
                    candidate_rtl = candidate_root / "inputs" / "gcd.v"
                    if not candidate_rtl.is_file():
                        raise ValueError("FlowLab candidate RTL snapshot is missing")
                    if flowlab_candidate_analysis:
                        raw_parameters = payload.get("parameters", {})
                        if not isinstance(raw_parameters, dict):
                            raise ValueError("analysis parameters must be a JSON object")
                        checkpoint = str(
                            raw_parameters.get("checkpoint")
                            or payload.get("checkpoint")
                            or "finish"
                        )
                        candidate_analysis_inputs = self._prepare_candidate_analysis_inputs(
                            candidate_run_id,
                            checkpoint,
                        )
                        if not candidate_analysis_inputs:
                            raise FileNotFoundError(
                                "candidate analysis has no registered input artifacts"
                            )
                        artifact = candidate_analysis_inputs[0]
                else:
                    candidate_root = None
                    work_home = None
                    candidate_rtl = None
                current_finish = (
                    self.repo_root
                    / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
                )
                if action_id in _FLOWLAB_STAGE_ACTIONS and current_finish.is_file() and not candidate_run_id:
                    return self._job_gap(
                        job_id=job_id,
                        tool_id=f"action:{action_id}",
                        operation=operation,
                        reason=(
                            "protected flowlab finish exists; recook is refused, "
                            "use an isolated candidate/ECO run"
                        ),
                        run_id=run_id,
                    )
            command, env_overrides = build_action_command(
                action_spec,
                self.repo_root,
                variant=action_variant,
                extra_args=[str(value) for value in raw_args],
            )
            if action_id == "system_pdn":
                env_overrides.update(
                    self._system_pdn_environment(payload, action_variant, run_id)
                )
            if action_id.startswith("lab_asap7_"):
                asap7_environment = self._asap7_lab_environment(payload)
                requested_variant = asap7_environment.get("LAB_ASAP7_VARIANT")
                if requested_variant and requested_variant != action_variant:
                    raise ValueError(
                        "ASAP7 parameters.variant must match the job variant"
                    )
                # The action variant is the single path identity used by the
                # catalog and by the package/chip-PDN sidecars. Never let a
                # free-form parameter silently select a second output tree.
                asap7_environment["LAB_ASAP7_VARIANT"] = action_variant
                env_overrides.update(asap7_environment)
            if action_id == "inspect_stage":
                try:
                    inspect_environment, inspect_artifact = self._inspect_environment(
                        payload,
                        action_variant,
                        run_id,
                        job_id,
                    )
                except FileNotFoundError as exc:
                    return self._job_gap(
                        job_id=job_id,
                        tool_id=f"action:{action_id}",
                        operation=operation,
                        reason=str(exc),
                        run_id=run_id,
                    )
                env_overrides.update(inspect_environment)
                artifact = inspect_artifact
            if action_id == "layout_preview":
                try:
                    preview_environment, preview_artifact = self._layout_preview_environment(
                        payload,
                        action_variant,
                    )
                except FileNotFoundError as exc:
                    return self._job_gap(
                        job_id=job_id,
                        tool_id=f"action:{action_id}",
                        operation=operation,
                        reason=str(exc),
                        run_id=run_id,
                    )
                env_overrides.update(preview_environment)
                if artifact is None:
                    artifact = preview_artifact
            if flowlab_candidate_action:
                env_overrides.update(self._flowlab_stage_environment(payload))
            elif action_id in _FLOWLAB_ANALYSIS_ACTIONS:
                env_overrides.update(
                    self._analysis_checkpoint_environment(payload, action_id)
                )
            if (flowlab_candidate_action or flowlab_candidate_analysis) and candidate_run_id:
                assert work_home is not None and candidate_rtl is not None
                env_overrides.update(
                    {
                        "PD_FLOW_WORK_HOME": str(work_home),
                        "PD_FLOW_RTL_FILE": str(candidate_rtl),
                        "PD_FLOW_CANDIDATE_RUN_ID": candidate_run_id,
                    }
                )
            if action_id == "rtl_sim":
                # The RTL simulator is also exposed by the legacy stream
                # facade.  Resolve its input here so the Next process never
                # guesses from its working directory and candidate runs can
                # only read their immutable RTL snapshot.
                if action_variant == "flowlab":
                    if candidate_run_id:
                        candidate_root, _ = self._candidate_workspace(candidate_run_id)
                        rtl_file = candidate_root / "inputs" / "gcd.v"
                        if not rtl_file.is_file():
                            raise ValueError("FlowLab candidate RTL snapshot is missing")
                    else:
                        rtl_file = self.repo_root / "learn" / "flowlab" / "gcd.v"
                    env_overrides["RTL_FILE"] = str(rtl_file)
            missing = [
                tool
                for tool in action_spec.required_tools
                if by_tool.get(tool, {}).get("availability") != "READY"
            ]
            if missing:
                return self._job_gap(
                    job_id=job_id,
                    tool_id=f"action:{action_id}",
                    operation=operation,
                    reason="missing action dependencies: " + ", ".join(missing),
                    run_id=run_id,
                    artifact=artifact.to_dict() if artifact else None,
                )
            report_scope = (
                action_spec.surface
                if action_spec.surface in {"product", "flow", "package", "lab"}
                else "generated"
            )
            report_versions = {
                tool: by_tool.get(tool, {}).get("version")
                for tool in action_spec.required_tools
            }
            tool_id = f"action:{action_id}"
        else:
            if not tool_id:
                raise ValueError("tool_id or action is required")
            try:
                tool, executable = get_tool(self.repo_root, tool_id)
            except (KeyError, ValueError) as exc:
                return self._job_gap(
                    job_id=job_id,
                    tool_id=tool_id,
                    operation=operation,
                    reason=str(exc),
                    run_id=run_id,
                    artifact=artifact.to_dict() if artifact else None,
                )
            if executable is None:
                return self._job_gap(
                    job_id=job_id,
                    tool_id=tool_id,
                    operation=operation,
                    reason=f"{tool.display_name} is not available on this host",
                    run_id=run_id,
                    artifact=artifact.to_dict() if artifact else None,
                )
            report_versions = {
                tool_id: self.registry().get("tool_versions", {}).get(tool_id)
            }
            if operation not in {"gui", "web"}:
                return self._job_gap(
                    job_id=job_id,
                    tool_id=tool_id,
                    operation=operation,
                    reason="batch work must use an allowlisted PDflow action",
                    run_id=run_id,
                    artifact=artifact.to_dict() if artifact else None,
                )
            if operation == "web":
                if tool_id != "openroad":
                    return self._job_gap(
                        job_id=job_id,
                        tool_id=tool_id,
                        operation=operation,
                        reason="web viewer is only available through OpenROAD",
                        run_id=run_id,
                        artifact=artifact.to_dict() if artifact else None,
                    )
                if artifact is None:
                    raise ValueError("web viewer requires an artifact")
                if raw_args:
                    raise ValueError("web viewer does not accept arbitrary arguments")
                try:
                    web_port = int(payload.get("web_port") or 43190)
                except (TypeError, ValueError) as exc:
                    raise ValueError("web_port must be numeric") from exc
                if not 43000 <= web_port <= 43999:
                    raise ValueError("web_port must be between 43000 and 43999")
            if not _display_available():
                return self._job_gap(
                    job_id=job_id,
                    tool_id=tool_id,
                    operation=operation,
                    reason="no DISPLAY or WAYLAND_DISPLAY is available for a native GUI",
                    run_id=run_id,
                    artifact=artifact.to_dict() if artifact else None,
                )
        try:
            resource_status = self.resources.preflight()
        except ResourceRunnerError as exc:
            resource_status = {"available": False, "reason": str(exc)}
        if not resource_status.get("available"):
            return self._job_gap(
                job_id=job_id,
                tool_id=tool_id or f"action:{action_id}",
                operation=operation,
                reason=(
                    "heavy job refused: resource isolation unavailable: "
                    + str(resource_status.get("reason") or "unknown reason")
                ),
                run_id=run_id,
                artifact=artifact.to_dict() if artifact else None,
            )

        source_artifact = artifact
        if mode == "edit" and artifact and not artifact.mutable:
            if not run_id:
                raise ValueError("edit mode requires run_id for a candidate")
            artifact = self.catalog.create_candidate(artifact, run_id)
        with self._lock:
            artifact_active = self._active_artifact_job(artifact)
        if artifact_active:
            raise RuntimeError(
                "artifact already has an active job: "
                + str(artifact_active.get("job_id"))
            )

        input_refs = [source_artifact.to_dict()] if source_artifact else []
        if candidate_analysis_inputs:
            input_refs = [ref.to_dict() for ref in candidate_analysis_inputs]
        if artifact is not None and artifact is not source_artifact:
            input_refs.append(artifact.to_dict())
        if action_id and not input_refs and report_scope != "generated":
            effective_variant = env_overrides.get("FLOW_VARIANT", action_variant)
            result_prefix = (
                "/results/asap7/gcd/"
                if is_lab_variant(effective_variant)
                else "/results/nangate45/gcd/"
            )
            input_refs = [
                ref.to_dict()
                for ref in self.catalog.list(
                    limit=2000,
                    variant=effective_variant,
                    authority="finish",
                )
                if result_prefix in f"/{ref.relative_path}"
            ]
        if input_refs:
            effective_variant = env_overrides.get("FLOW_VARIANT", action_variant)
            report_mesh_id = hash_text(
                "variant=" + effective_variant,
                *sorted(str(item.get("content_hash") or "") for item in input_refs),
            )[:24]
            report_oracle = "current-finish-snapshot"
            report_comparison_scope = "same-live-invocation" if run_id else "none"
        before_artifacts = self._artifact_snapshot()
        if not action_id:
            artifact_path = self.catalog.path_for(artifact) if artifact else None
            command = build_command(
                tool=tool,
                executable=executable,
                operation=operation,
                artifact=artifact_path,
                script=None,
                args=[str(value) for value in raw_args],
                web_port=web_port,
            )
            timeout_default = tool.timeout_seconds
        else:
            timeout_default = action_spec.timeout_seconds if action_spec else 600
        timeout_seconds = int(payload.get("timeout_seconds") or timeout_default or 600)
        timeout_seconds = max(1, min(timeout_seconds, 3600))
        log_dir = (
            self.run_root / run_id / "logs"
            if run_id
            else self.agent_root / "logs"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}.log"
        job = {
            "job_id": job_id,
            "tool_id": tool_id,
            "operation": operation,
            "state": "QUEUED",
            "created_at": utc_now(),
            "run_id": run_id,
            "artifact": artifact.to_dict() if artifact else None,
            "mode": mode,
            "web_port": web_port,
            "viewer_stage": str(payload.get("viewer_stage") or "") or None,
            "command": command,
            "timeout_seconds": timeout_seconds,
            "log_path": str(log_path.relative_to(self.repo_root)),
            "log_tail": "",
            "action": action_id or None,
            "input_artifacts": input_refs,
            "resource": self.resources.describe(),
        }
        with self._lock:
            self._jobs[job_id] = job
            cancel_event = threading.Event()
            self._cancel_events[job_id] = cancel_event
        self._persist_job(job)
        self._emit("job.created", {"job": dict(job)})
        thread = threading.Thread(
            target=self._run_job,
            args=(
                job_id,
                command,
                timeout_seconds,
                log_path,
                run_id,
                env_overrides,
                input_refs,
                report_scope,
                report_versions,
                before_artifacts,
                operation,
                report_mesh_id,
                report_oracle,
                report_comparison_scope,
            ),
            name=f"pdflow-job-{job_id[:12]}",
            daemon=True,
        )
        thread.start()
        return dict(job)

    def _update_job(self, job_id: str, **updates: Any) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.update(updates)
            snapshot = dict(job)
        self._persist_job(snapshot)
        self._emit("job.updated", {"job": snapshot})
        return snapshot

    def _update_run_status(self, run_id: str | None, status: str) -> None:
        if not run_id or not _safe_id(run_id):
            return
        with self._lock:
            record = self._runs.get(run_id)
            if record is not None:
                record["status"] = status
                record["updated_at"] = utc_now()
                record_copy = dict(record)
            else:
                record_copy = None
        manifest = self.run_root / run_id / "manifest.json"
        if manifest.is_file():
            try:
                current = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(current, dict):
                    current["status"] = status
                    current["updated_at"] = utc_now()
                    atomic_write_json(manifest, current)
            except (OSError, json.JSONDecodeError):
                pass
        if record_copy:
            self._emit("run.updated", {"run": record_copy})

    def _terminate(self, process: ManagedProcess, reason: str = "cancelled by user") -> None:
        """Terminate the complete systemd cgroup, including descendants."""

        process.terminate(reason)

    def _run_job(
        self,
        job_id: str,
        command: list[str],
        timeout_seconds: int,
        log_path: Path,
        run_id: str | None,
        env_overrides: dict[str, str],
        input_refs: list[dict[str, Any]],
        report_scope: str,
        report_versions: dict[str, str | None],
        before_artifacts: dict[str, tuple[int, int, str | None]],
        operation: str,
        report_mesh_id: str | None,
        report_oracle: str | None,
        report_comparison_scope: str,
    ) -> None:
        env = os.environ.copy()
        if run_id:
            env["PD_FLOW_RUN_DIR"] = str(self.run_root / run_id)
        env.update(env_overrides)
        process: ManagedProcess | None = None
        log_tail = ""
        code: int | None = None
        reason: str | None = None
        termination_cause: str | None = None
        resource_result: dict[str, Any] = self.resources.describe()
        log_bytes = 0
        log_bytes_seen = 0
        log_truncated = False
        cancel_event: threading.Event | None = None
        controlled_refusal: str | None = None
        try:
            with self._lock:
                cancel_event = self._cancel_events.get(job_id)

            last_wait_update = 0.0

            def on_wait(update: dict[str, Any]) -> None:
                nonlocal last_wait_update
                now = time.monotonic()
                if now - last_wait_update >= 0.9:
                    self._update_job(job_id, resource=update)
                    last_wait_update = now

            process = self.resources.start(
                command,
                cwd=self.repo_root,
                env=env,
                unit_name=f"pdflow-job-{job_id}",
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
                on_wait=on_wait,
            )
            if process is None:
                reason = "cancelled by user"
                termination_cause = "cancelled"
            else:
                resource_result = process.resource_metadata()
                with self._lock:
                    self._processes[job_id] = process
                self._update_job(
                    job_id,
                    state="RUNNING",
                    started_at=utc_now(),
                    pid=process.pid,
                    resource=resource_result,
                )

                deadline = time.monotonic() + timeout_seconds
                selector = selectors.DefaultSelector()
                stdout = process.stdout
                if stdout is not None:
                    try:
                        os.set_blocking(stdout.fileno(), False)
                        selector.register(stdout, selectors.EVENT_READ)
                    except (OSError, ValueError):
                        stdout = None
                done_reading = not bool(selector.get_map())
                pending_event = bytearray()
                last_event = time.monotonic()
                last_resource_update = last_event
                with BoundedLog(
                    log_path,
                    max_bytes=self.resources.limits.log_max_bytes,
                    tail_bytes=self.resources.limits.log_tail_bytes,
                ) as log:
                    while True:
                        if not done_reading:
                            for key, _ in selector.select(timeout=0.2):
                                try:
                                    chunk = os.read(key.fileobj.fileno(), 65536)
                                except (BlockingIOError, OSError):
                                    chunk = b""
                                if chunk:
                                    log.append(chunk)
                                    pending_event.extend(chunk)
                                    if len(pending_event) > 8192:
                                        del pending_event[:-8192]
                                else:
                                    done_reading = True
                                    try:
                                        selector.unregister(key.fileobj)
                                    except (KeyError, ValueError):
                                        pass

                        now = time.monotonic()
                        if now - last_resource_update >= 1.0:
                            resource_result = process.resource_metadata()
                            self._update_job(job_id, resource=resource_result)
                            last_resource_update = now
                        if cancel_event is not None and cancel_event.is_set() and termination_cause is None:
                            reason = "cancelled by user"
                            termination_cause = "cancelled"
                            self._terminate(process, reason)
                        elif now >= deadline and termination_cause is None:
                            reason = f"timeout after {timeout_seconds}s"
                            termination_cause = "timeout"
                            self._terminate(process, reason)

                        if pending_event and (
                            len(pending_event) >= 4096 or now - last_event >= 0.25
                        ):
                            event_chunk = bytes(pending_event)
                            pending_event.clear()
                            log_tail = log.tail_text()
                            self._update_job(job_id, log_tail=log_tail)
                            self._emit(
                                "tool.log",
                                {
                                    "job_id": job_id,
                                    "chunk": event_chunk.decode("utf-8", errors="replace")[-4000:],
                                },
                            )
                            last_event = now

                        if process.poll() is not None and done_reading:
                            break

                    if pending_event:
                        log_tail = log.tail_text()
                        self._update_job(job_id, log_tail=log_tail)
                        self._emit(
                            "tool.log",
                            {
                                "job_id": job_id,
                                "chunk": bytes(pending_event).decode("utf-8", errors="replace")[-4000:],
                            },
                        )
                    log_bytes = log.bytes_written
                    log_bytes_seen = log.bytes_seen
                    log_truncated = log.truncated
                selector.close()
                code = process.wait(timeout=5)
                resource_result = process.finish()
        except (OSError, subprocess.SubprocessError, TimeoutError, ResourceRunnerError) as exc:
            reason = str(exc)
            termination_cause = "resource_isolation" if isinstance(exc, ResourceRunnerError) else "crash"
            if process is not None and process.poll() is None:
                self._terminate(process, "agent cleanup after execution error")
        finally:
            if process is not None and not process.finished:
                if process.poll() is None:
                    self._terminate(process, "agent cleanup")
                try:
                    code = process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    code = -1
                resource_result = process.finish()
            with self._lock:
                self._processes.pop(job_id, None)
                persisted_cancel = self._cancel_events.pop(job_id, None)
            # A user cancellation can make systemd report `Result=timeout`
            # when the GUI process ignores TERM until TimeoutStopSec expires.
            # The request that caused termination is the authoritative cause;
            # do not relabel an intentional cancel as a resource timeout.
            cancel_requested = bool(
                (persisted_cancel and persisted_cancel.is_set())
                or (process and process.termination_requested == "cancelled by user")
            )
            controlled_refusal = _controlled_refusal_reason(log_tail)
            if resource_result.get("resource_exhausted"):
                reason = "resource limit exceeded: memory cgroup OOM kill"
                termination_cause = "memory"
            elif cancel_requested:
                # systemd can expose Result=timeout when a GUI process needs
                # the stop grace period after an intentional cancellation.
                # That is not a job timeout, so keep the resource-level cause
                # aligned with the user-visible termination cause while
                # retaining the raw systemd result for diagnostics.
                resource_result["resource_cause"] = None
                reason = "cancelled by user"
                termination_cause = "cancelled"
            elif resource_result.get("resource_cause") == "timeout":
                reason = reason or f"resource executor timeout after {timeout_seconds}s"
                termination_cause = "timeout"
            elif controlled_refusal and termination_cause in {None, "crash"}:
                reason = controlled_refusal
                termination_cause = "refused"
            elif reason and termination_cause is None:
                termination_cause = "crash"
            if termination_cause == "cancelled":
                state = "CANCELLED"
            elif termination_cause == "refused":
                state = "GAP"
            elif reason or code not in (0, None) or resource_result.get("resource_exhausted"):
                state = "FAILED"
            else:
                state = "COMPLETED"
            if code is None and state == "FAILED":
                code = -1
            if state == "FAILED" and not reason:
                reason = f"process exited with code {code}"
                termination_cause = termination_cause or "crash"
            if state == "COMPLETED":
                termination_cause = None
            output_refs = [
                ref
                for ref in self._changed_artifacts(before_artifacts)
                if ref.relative_path != str(log_path.relative_to(self.repo_root))
                and ref.relative_path
                not in {item.get("relative_path") for item in input_refs}
            ]
            report_status = (
                "PASS"
                if state == "COMPLETED"
                else "PARTIAL"
                if state == "CANCELLED"
                else "GAP"
                if state == "GAP"
                else "FAIL"
            )
            normalized = self._normalize_outputs(output_refs)
            inspect_details: dict[str, Any] | None = None
            inspect_output = env_overrides.get("PD_FLOW_INSPECT_OUTPUT")
            if inspect_output:
                try:
                    inspect_path = Path(inspect_output).resolve()
                    inspect_path.relative_to(self.agent_root.resolve())
                    raw_inspect = json.loads(inspect_path.read_text(encoding="utf-8"))
                    if isinstance(raw_inspect, dict):
                        inspect_details = raw_inspect
                    try:
                        inspect_path.unlink()
                    except OSError:
                        pass
                except (OSError, ValueError, json.JSONDecodeError):
                    inspect_details = None
            if state == "COMPLETED" and normalized:
                report_status = str(normalized.get("status") or report_status)
                report_ok = report_status == "PASS"
                if normalized.get("reason"):
                    reason = str(normalized["reason"])
            else:
                report_ok = state == "COMPLETED"
            if inspect_details is not None and state == "COMPLETED":
                inspected_status = str(inspect_details.get("status") or "").upper()
                if inspected_status in {
                    "PASS",
                    "FAIL",
                    "WARN",
                    "PARTIAL",
                    "PROXY",
                    "GAP",
                    "NOT_RUN",
                }:
                    report_status = inspected_status
                    report_ok = (
                        inspected_status == "PASS"
                        and inspect_details.get("ok") is True
                    )
                    if inspect_details.get("reason") and inspected_status != "PASS":
                        reason = str(inspect_details["reason"])
            execution_status = (
                "COMPLETED"
                if state == "COMPLETED"
                else "CANCELLED"
                if state == "CANCELLED"
                else "NOT_RUN"
                if state == "GAP"
                else "FAILED"
            )
            if state != "COMPLETED":
                evidence_status = "GAP"
                requirement_status = "GAP" if state == "GAP" else "NOT_RUN"
                signoff_status = "GAP"
            elif normalized:
                normalized_status = str(normalized.get("status") or report_status)
                evidence_status = _report_status_value(
                    normalized.get("evidence_status"),
                    "PASS"
                    if normalized_status in {"PASS", "FAIL", "WARN"}
                    else normalized_status,
                )
                requirement_status = _report_status_value(
                    normalized.get("requirement_status"),
                    normalized_status,
                )
                signoff_status = _report_status_value(
                    normalized.get("signoff_status"),
                    "PASS"
                    if report_scope == "product" and normalized_status == "PASS"
                    else "NOT_RUN",
                )
            else:
                evidence_status = "PASS"
                requirement_status = "NOT_RUN"
                signoff_status = "NOT_RUN"
            report = ReportEnvelope(
                report_id=f"report-{uuid.uuid4().hex}",
                run_id=run_id,
                scope=report_scope,
                status=report_status,
                ok=report_ok,
                execution_status=execution_status,
                evidence_status=evidence_status,
                requirement_status=requirement_status,
                signoff_status=signoff_status,
                product_signoff=bool(
                    normalized.get("product_signoff") is True
                    and report_status == "PASS"
                    and report_ok is True
                    and signoff_status == "PASS"
                ),
                input_artifacts=[
                    str(item.get("artifact_id"))
                    for item in input_refs
                    if item.get("artifact_id")
                ],
                input_artifact_refs=input_refs,
                output_artifacts=[ref.artifact_id for ref in output_refs],
                output_artifact_refs=[ref.to_dict() for ref in output_refs],
                required_checks=normalized.get("required_checks", []),
                checkpoint_id=(
                    normalized.get("checkpoint_id")
                    or (input_refs[0].get("artifact_id") if input_refs else None)
                ),
                configuration_hash=normalized.get("configuration_hash"),
                units=normalized.get("units", {}),
                corner=normalized.get("corner"),
                mode=normalized.get("mode"),
                activity_source=normalized.get("activity_source"),
                limitations=normalized.get("limitations", []),
                mesh_id=normalized.get("mesh_id") or report_mesh_id,
                oracle=normalized.get("oracle") or report_oracle,
                metrics=normalized.get("metrics", {}),
                relative=normalized.get("relative", []),
                comparison_scope=(
                    normalized.get("comparison_scope")
                    if normalized.get("comparison_scope")
                    in {"same-live-invocation", "not-comparable", "none"}
                    else report_comparison_scope
                ),
                reason=reason,
                tool_versions=normalized.get("tool_versions", report_versions),
                environment={
                    key: value
                    for key, value in env_overrides.items()
                    if key in _SAFE_REPORT_ENVIRONMENT_KEYS
                },
                job_id=job_id,
                operation=operation,
                resource=resource_result,
                termination_cause=termination_cause,
                report_paths=[
                    str(log_path.relative_to(self.repo_root)),
                ]
                + [
                    ref.relative_path
                    for ref in output_refs
                    if ref.kind == "json"
                ],
            ).to_dict()
            if inspect_details is not None:
                report["details"] = inspect_details
            report_path = self._persist_report(report, run_id, job_id)
            if report_path:
                report["report_paths"] = [report_path] + [
                    path
                    for path in report["report_paths"]
                    if path != report_path
                ]
                try:
                    atomic_write_json(self.repo_root / report_path, report)
                except OSError:
                    pass
            finished = utc_now()
            self._update_job(
                job_id,
                state=state,
                finished_at=finished,
                code=code,
                reason=reason,
                log_tail=log_tail,
                resource=resource_result,
                termination_cause=termination_cause,
                log_bytes=log_bytes,
                log_bytes_seen=log_bytes_seen,
                log_truncated=log_truncated,
                report=report,
            )
            self._update_run_status(
                run_id,
                "COMPLETED"
                if state == "COMPLETED"
                else "CANCELLED"
                if state == "CANCELLED"
                else "FAILED",
            )
            self._emit(
                "tool.completed"
                if state == "COMPLETED"
                else "tool.cancelled"
                if state == "CANCELLED"
                else "tool.failed",
                {"job_id": job_id, "state": state, "code": code, "reason": reason},
            )

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            event = self._cancel_events.get(job_id)
            process = self._processes.get(job_id)
        if not job:
            return None
        if event:
            event.set()
        if process and process.poll() is None:
            self._terminate(process)
        if job.get("state") == "QUEUED":
            return self._update_job(
                job_id,
                state="CANCELLED",
                finished_at=utc_now(),
                reason="cancelled by user",
            )
        return self.get_job(job_id)

    def create_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or "")
        artifact_id = str(payload.get("artifact_id") or "")
        if not _safe_id(run_id):
            raise ValueError("valid run_id is required")
        # A candidate is a child of a persisted PDflow run, not an arbitrary
        # directory selected by the caller.  Without this guard a typo (or a
        # replayed request after a run was removed) could create an apparently
        # valid candidate outside the run registry and make its provenance
        # impossible to resolve.  Persisted manifests are loaded at agent
        # startup, so restart/recovery remains supported.
        with self._lock:
            known_run = run_id in self._runs
        if not known_run:
            raise ValueError("candidate references an unknown PDflow run")
        source = self.catalog.resolve(artifact_id)
        if source is None:
            raise ValueError("source artifact not found")
        candidate = self.catalog.create_candidate(source, run_id)
        self._emit(
            "candidate.created",
            {"source": source.to_dict(), "candidate": candidate.to_dict()},
        )
        return {
            "ok": True,
            "source": source.to_dict(),
            "candidate": candidate.to_dict(),
        }

    def _handler_class(self):
        agent = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "PDflowAgent/1.0"

            def log_message(self, _format: str, *args: Any) -> None:
                return

            def _authorized(self) -> bool:
                if not agent.auth_token:
                    return True
                return self.headers.get("X-PDFlow-Token") == agent.auth_token

            def _json(self, status: int, payload: Any) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    # A cancelled browser fetch is a normal client disconnect.
                    return

            def _download_file(self, path: Path, filename: str) -> None:
                try:
                    handle = path.open("rb")
                    size = os.fstat(handle.fileno()).st_size
                except OSError:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "log not found"})
                    return
                try:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(size))
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{filename}"',
                    )
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    remaining = size
                    while remaining > 0:
                        chunk = handle.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    handle.close()

            def _read_payload(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 1024 * 1024:
                    raise ValueError("request body too large")
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("JSON object required")
                return data

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if path in {"/health", "/v1/health"}:
                    self._json(HTTPStatus.OK, agent.health())
                    return
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                    return
                query = parse_qs(parsed.query)
                if path == "/v1/registry":
                    self._json(HTTPStatus.OK, agent.registry())
                elif path == "/v1/context":
                    self._json(
                        HTTPStatus.OK,
                        agent.context(query.get("surface", ["flow"])[0]),
                    )
                elif path == "/v1/artifacts":
                    self._json(
                        HTTPStatus.OK,
                        agent.artifacts(
                            int(query.get("limit", ["200"])[0]),
                            scope=query.get("scope", [None])[0],
                            variant=query.get("variant", [None])[0],
                            authority=query.get("authority", [None])[0],
                            run_id=query.get("run_id", [None])[0],
                        ),
                    )
                elif path.startswith("/v1/artifacts/"):
                    artifact_id = path.split("/", 3)[-1]
                    if not _safe_id(artifact_id):
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid artifact id"})
                    else:
                        detail = agent.artifact_detail(artifact_id)
                        if detail is None:
                            self._json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"})
                        else:
                            self._json(HTTPStatus.OK, detail)
                elif path.startswith("/v1/reports/"):
                    report_id = path.split("/", 3)[-1]
                    if not _safe_id(report_id):
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid report id"})
                    else:
                        report = agent.report_detail(report_id)
                        if report is None:
                            self._json(HTTPStatus.NOT_FOUND, {"error": "report not found"})
                        else:
                            self._json(HTTPStatus.OK, report)
                elif path == "/v1/package":
                    self._json(
                        HTTPStatus.OK,
                        agent.package(query.get("variant", [None])[0]),
                    )
                elif path == "/v1/path-ledger":
                    self._json(
                        HTTPStatus.OK,
                        agent.path_ledger(query.get("variant", [None])[0]),
                    )
                elif path == "/v1/checks":
                    self._json(
                        HTTPStatus.OK,
                        agent.checks(
                            stage=query.get("stage", ["finish"])[0],
                            variant=query.get("variant", [None])[0],
                            run_id=query.get("run_id", [None])[0],
                            check_id=query.get("check_id", [None])[0],
                        ),
                    )
                elif path == "/v1/evidence":
                    self._json(
                        HTTPStatus.OK,
                        agent.evidence(
                            stage=query.get("stage", ["finish"])[0],
                            variant=query.get("variant", [None])[0],
                            run_id=query.get("run_id", [None])[0],
                            check_id=query.get("check_id", [None])[0],
                        ),
                    )
                elif path.startswith("/v1/checks/") and path.endswith("/eligibility"):
                    check_id = path.split("/")[-2]
                    if not re.fullmatch(r"[a-z0-9_]{2,80}", check_id):
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid check id"})
                    else:
                        self._json(
                            HTTPStatus.OK,
                            agent.checks(
                                stage=query.get("stage", ["finish"])[0],
                                variant=query.get("variant", [None])[0],
                                run_id=query.get("run_id", [None])[0],
                                check_id=check_id,
                            ),
                        )
                elif path == "/v1/runs":
                    self._json(HTTPStatus.OK, {"runs": agent.list_runs()})
                elif path == "/v1/analysis-runs":
                    try:
                        limit = int(query.get("limit", ["40"])[0])
                    except (TypeError, ValueError):
                        limit = 40
                    self._json(
                        HTTPStatus.OK,
                        {"analysis_runs": agent.list_analysis_runs(limit)},
                    )
                elif path.startswith("/v1/analysis-runs/"):
                    analysis_run_id = path.split("/", 3)[-1]
                    if not _safe_id(analysis_run_id):
                        self._json(
                            HTTPStatus.BAD_REQUEST,
                            {"error": "invalid analysis_run_id"},
                        )
                    else:
                        record = agent.get_analysis_run(analysis_run_id)
                        if record is None:
                            self._json(
                                HTTPStatus.NOT_FOUND,
                                {"error": "analysis run not found"},
                            )
                        else:
                            self._json(HTTPStatus.OK, {"analysis_run": record})
                elif path == "/v1/viewer":
                    self._json(HTTPStatus.OK, agent.viewer_status())
                elif path == "/v1/jobs":
                    job_id = query.get("id", [None])[0]
                    if job_id:
                        job = agent.get_job(job_id)
                        if job is None:
                            self._json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                        else:
                            self._json(HTTPStatus.OK, job)
                    else:
                        self._json(
                            HTTPStatus.OK,
                            {"jobs": agent.list_jobs(int(query.get("limit", ["40"])[0]))},
                        )
                elif path.startswith("/v1/jobs/") and path.endswith("/log"):
                    job_id = path.split("/")[-2]
                    if not _safe_id(job_id):
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid job id"})
                    else:
                        log_path = agent.job_log_path(job_id)
                        if log_path is None:
                            self._json(HTTPStatus.NOT_FOUND, {"error": "log not found"})
                        else:
                            self._download_file(log_path, f"pdflow-{job_id}.log")
                elif path == "/v1/events":
                    self._events(query)
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

            def _events(self, query: dict[str, list[str]]) -> None:
                requested_since = query.get("since", [None])[0]
                if requested_since is None or requested_since.strip().lower() == "latest":
                    cursor = agent.events.latest_id()
                    replay_note = None
                else:
                    try:
                        cursor = max(0, int(requested_since))
                    except (TypeError, ValueError):
                        cursor = agent.events.latest_id()
                    # A zero cursor means "start a live stream".  Treating it
                    # as a request for the entire in-memory history allowed an
                    # old browser tab to replay megabytes of log events.
                    if cursor == 0:
                        cursor = agent.events.latest_id()
                    oldest = agent.events.oldest_id()
                    replay_note = None
                    if oldest is not None and cursor < oldest - 1:
                        replay_note = {
                            "requested": cursor,
                            "oldest_available": oldest,
                            "latest": agent.events.latest_id(),
                        }
                        cursor = oldest - 1
                try:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("X-PDFlow-Event-Cursor", str(cursor))
                    self.end_headers()
                    self.wfile.write(b": pdflow event stream\n\n")
                    if replay_note is not None:
                        self.wfile.write(
                            (": replay window truncated "
                             + json.dumps(replay_note, sort_keys=True)
                             + "\n\n").encode("utf-8")
                        )
                    self.wfile.flush()
                    # Keep the stream open with SSE comments when idle. A
                    # one-shot 25 s poll made every healthy browser look like
                    # it had fallen back to polling as soon as the stream
                    # closed without an event.
                    while True:
                        events = agent.events.wait_since(cursor, timeout=15, limit=64)
                        if not events:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                            continue
                        for event in events:
                            payload = json.dumps(event, sort_keys=True, default=str)
                            self.wfile.write(
                                f"id: {event['event_id']}\ndata: {payload}\n\n".encode(
                                    "utf-8"
                                )
                            )
                            cursor = max(cursor, int(event["event_id"]))
                            self.wfile.flush()
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    # EventSource reconnects whenever a tab is closed or refreshed.
                    return

            def do_POST(self) -> None:
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                    return
                path = urlparse(self.path).path.rstrip("/") or "/"
                try:
                    payload = self._read_payload()
                    if path == "/v1/runs":
                        self._json(HTTPStatus.CREATED, {"run": agent.create_run(payload)})
                    elif path == "/v1/analysis-runs":
                        self._json(
                            HTTPStatus.CREATED,
                            {"analysis_run": agent.create_analysis_run(payload)},
                        )
                    elif path == "/v1/analysis-bundles/preview":
                        self._json(
                            HTTPStatus.OK,
                            agent.preview_analysis_bundle(payload),
                        )
                    elif path == "/v1/analysis-bundles":
                        result = agent.execute_analysis_bundle(payload)
                        status = (
                            HTTPStatus.ACCEPTED
                            if result.get("status") == "QUEUED"
                            else HTTPStatus.CONFLICT
                            if result.get("status") in {"PREVIEW", "GAP"}
                            else HTTPStatus.OK
                        )
                        self._json(status, result)
                    elif path == "/v1/jobs":
                        self._json(HTTPStatus.ACCEPTED, agent.submit_job(payload))
                    elif path.startswith("/v1/jobs/") and path.endswith("/cancel"):
                        job_id = path.split("/")[-2]
                        job = agent.cancel_job(job_id)
                        if job is None:
                            self._json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                        else:
                            self._json(HTTPStatus.OK, job)
                    elif path == "/v1/candidates":
                        self._json(HTTPStatus.CREATED, agent.create_candidate(payload))
                    elif path == "/v1/compare":
                        self._json(HTTPStatus.OK, agent.compare_reports(payload))
                    elif path == "/v1/refresh":
                        agent._watch_state = agent._snapshot_by_path()
                        agent._emit("context.refreshed", {})
                        self._json(HTTPStatus.OK, {"ok": True})
                    else:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                except FileExistsError as exc:
                    self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
                except RuntimeError as exc:
                    self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
                except (ValueError, KeyError, FileNotFoundError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                except Exception as exc:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        return Handler
