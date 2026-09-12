#!/usr/bin/env python3
"""Static contracts for Studio's process, path, and dependency hardening."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "studio"


def check(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def main() -> int:
    protected = {
        "src/app/api/run/route.ts": ("POST", True),
        "src/app/api/run/cancel/route.ts": ("POST", True),
        "src/app/api/jobs/route.ts": ("DELETE", True),
        "src/app/api/flowlab/route.ts": ("PUT", True),
        "src/app/api/progress/route.ts": ("POST", True),
        "src/app/api/open/route.ts": ("POST", True),
        "src/app/api/viewer/route.ts": ("POST", True),
        "src/app/api/layout-preview/route.ts": ("POST", True),
    }
    for rel, (method, body_limit) in protected.items():
        source = (STUDIO / rel).read_text()
        check(f"export async function {method}" in source, f"{rel} exposes {method}")
        check("authorizeStudioMutation" in source, f"{rel} authorizes mutation")
        if body_limit:
            check("rejectOversizedBody" in source, f"{rel} caps declared body size")

    for rel in (
        "src/app/api/inspect/route.ts",
        "src/app/api/layout-preview/route.ts",
    ):
        check(
            "authorizeStudioMutation" in (STUDIO / rel).read_text(),
            f"{rel} guards process-capable GET",
        )
    stream = (STUDIO / "src/app/api/run/stream/route.ts").read_text()
    check("authorizeRunRequest" in stream, "run stream keeps its authorization guard")
    check("submitAgentAction" in stream, "run stream delegates to the local agent")
    check("streamCourseAction" not in stream, "run stream has no direct process fallback")
    run_route = (STUDIO / "src/app/api/run/route.ts").read_text()
    check("submitAgentAction" in run_route, "run POST delegates to the local agent")
    check("runCourseAction" not in run_route, "run POST has no direct process fallback")
    cancel_route = (STUDIO / "src/app/api/run/cancel/route.ts").read_text()
    check("cancelAgentJob" in cancel_route, "run cancellation delegates to the local agent")
    check("cancelJob" not in cancel_route, "run cancellation has no direct process fallback")
    facade = (STUDIO / "src/lib/agentRun.ts").read_text()
    check("waitForAgentJob" in facade, "agent facade observes typed job state")
    check("MAX_MISSED_POLLS" in facade, "agent facade bounds status outages")

    guard = (STUDIO / "src/lib/pathGuard.ts").read_text()
    check("normalizeResultsVariant" in guard, "variants use an allowlist")
    check("normalizeRelativeArtifact" in guard, "artifacts reject path components")
    check("assertUnder" in guard, "results paths have containment checks")
    check('value.includes("..")' in guard, "dot-dot traversal is refused")

    jobs = (STUDIO / "src/lib/jobs.ts").read_text()
    run = (STUDIO / "src/lib/run.ts").read_text()
    check('"wx"' in jobs, "job lock creation is atomic")
    check("updateLock" in jobs and "renameSync" in jobs, "child PID persistence is atomic")
    check("cancelAgentJob" in run, "compatibility cancellation delegates to the agent")
    check("spawn(" not in run and "execFile" not in run, "run helpers never spawn host processes")
    for rel in (
        "src/lib/open.ts",
        "src/lib/webviewer.ts",
        "src/lib/inspect.ts",
        "src/lib/jobs.ts",
    ):
        source = (STUDIO / rel).read_text()
        check("child_process" not in source, f"{rel} has no direct child-process import")
        check("spawnSync(" not in source and "spawn(" not in source, f"{rel} has no direct process launch")
    inspect = (STUDIO / "src/app/api/inspect/route.ts").read_text()
    check("inspect_stage" in inspect and "submitAgentAction" in inspect, "inspection delegates to the local agent")
    image_route = (STUDIO / "src/app/api/layout-preview/image/route.ts").read_text()
    check("READ_ONLY_NO_PROCESS" in image_route, "preview image route is explicitly read-only")

    csp = (STUDIO / "next.config.ts").read_text()
    check('NODE_ENV !== "production"' in csp, "unsafe-eval is development-only")
    check("scriptSrc.join" in csp, "CSP script source is assembled explicitly")

    package = json.loads((STUDIO / "package.json").read_text())
    lock = json.loads((STUDIO / "package-lock.json").read_text())
    root_lock = lock["packages"][""]
    check(
        package["devDependencies"]["eslint-config-next"]
        == root_lock["devDependencies"]["eslint-config-next"],
        "package.json and lockfile agree on eslint-config-next",
    )
    check(
        lock["packages"]["node_modules/eslint-config-next"]["version"] == "16.3.3",
        "eslint-config-next matches Next 16",
    )

    tauri = (STUDIO / "src-tauri/src/main.rs").read_text()
    check("read_exact" in tauri, "desktop token reads a bounded urandom buffer")
    check(
        'env_remove("PYTHONHOME")' in tauri,
        "desktop agent clears AppImage PYTHONHOME",
    )
    check("split_paths" in tauri, "desktop environment preserves PATH components")
    check(
        "launch_local_agent(&app.state::<AgentProcess>()" in tauri,
        "release desktop starts the local agent",
    )
    check("DESKTOP_LOG_MAX_BYTES" in tauri, "desktop logs declare a hard size cap")
    check("attach_process_logs" in tauri, "desktop child output uses bounded pumps")
    check("Stdio::piped()" in tauri, "desktop child output cannot block on an unconsumed pipe")
    check("setpgid" in tauri, "desktop children receive dedicated process groups")
    check("PR_SET_PDEATHSIG" in tauri, "desktop children cannot outlive a crashed shell")
    check("SIGKILL" in tauri and "try_wait" in tauri, "desktop cleanup escalates safely")
    events = (ROOT / "learn/pdflow_agent/agent.py").read_text()
    check(": heartbeat" in events, "SSE stays open with bounded idle heartbeats")
    check("while True:" in events, "SSE endpoint does not close after an idle poll")
    check("latest_id()" in events and "limit=64" in events, "SSE replay starts live and batches events")
    event_bus = (ROOT / "learn/pdflow_agent/events.py").read_text()
    check("DEFAULT_MAX_BYTES" in event_bus and "max_event_bytes" in event_bus, "event history has byte caps")
    runtime_bar = (STUDIO / "src/components/RuntimeStatusBar.tsx").read_text()
    check('"latest"' in runtime_bar and "scheduleRefresh" in runtime_bar, "runtime status coalesces SSE refreshes")
    build_script = (STUDIO / "scripts/build_tauri_frontend.sh").read_text()
    check("PD_FLOW_NEXT_HEAP_MB" in build_script, "desktop build declares a Node heap cap")
    check(
        "PD_FLOW_RESOURCE_ALLOW_INCREASE" in build_script,
        "desktop heap increases require acknowledgement",
    )
    eslint = (STUDIO / "eslint.config.mjs").read_text()
    check('"src-tauri/target/**"' in eslint, "lint excludes generated desktop bundles")
    studio_launcher = (ROOT / "scripts/run_studio.sh").read_text()
    check(
        "node_modules/next/dist/bin/next dev" in studio_launcher,
        "Studio launcher uses the configured native Node runtime",
    )
    check("npx next" not in studio_launcher, "Studio launcher does not require npx")
    check("kill -KILL" in studio_launcher, "Studio launcher bounds agent cleanup")

    cmake = (ROOT / "engine/CMakeLists.txt").read_text()
    check("add_test(NAME dpn_native" in cmake, "native engine is registered with CTest")
    check("DPN_ENABLE_SANITIZERS" in cmake, "native sanitizer build is opt-in")
    print("ALL test_studio_security PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
