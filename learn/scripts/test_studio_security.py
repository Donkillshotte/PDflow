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
        "src/app/api/layout-preview/image/route.ts",
    ):
        check(
            "authorizeStudioMutation" in (STUDIO / rel).read_text(),
            f"{rel} guards process-capable GET",
        )
    stream = (STUDIO / "src/app/api/run/stream/route.ts").read_text()
    check("authorizeRunRequest" in stream, "run stream keeps its authorization guard")

    guard = (STUDIO / "src/lib/pathGuard.ts").read_text()
    check("normalizeResultsVariant" in guard, "variants use an allowlist")
    check("normalizeRelativeArtifact" in guard, "artifacts reject path components")
    check("assertUnder" in guard, "results paths have containment checks")
    check('value.includes("..")' in guard, "dot-dot traversal is refused")

    jobs = (STUDIO / "src/lib/jobs.ts").read_text()
    run = (STUDIO / "src/lib/run.ts").read_text()
    check('"wx"' in jobs, "job lock creation is atomic")
    check("updateLock" in jobs and "renameSync" in jobs, "child PID persistence is atomic")
    check("childPid" in run, "cancellation persists the child PID")
    check("fs.rmSync(dest, { recursive: true" not in run, "tutorial link never recursively deletes")

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

    cmake = (ROOT / "engine/CMakeLists.txt").read_text()
    check("add_test(NAME dpn_native" in cmake, "native engine is registered with CTest")
    check("DPN_ENABLE_SANITIZERS" in cmake, "native sanitizer build is opt-in")
    print("ALL test_studio_security PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
