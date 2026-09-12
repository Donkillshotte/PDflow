#!/usr/bin/env python3
"""Verify one real, non-mutating Run action through the Studio UI.

This gate exercises the visible Tools -> Run control and the complete browser
facade/local-agent path with the allowlisted ``check`` action.  It deliberately
does not start synthesis, placement, routing, or any other flow operation.

Usage::

    STUDIO_URL=http://127.0.0.1:43227 python3 learn/scripts/test_ui_safe_action.py

The script uses the repository's native Node runtime and the bundled
Playwright driver when the host has no system-wide Node.js installation.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from urllib.request import urlopen

from playwright._impl import _driver, _transport
from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("STUDIO_URL", "http://127.0.0.1:43227").rstrip("/")
REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT_NODE = os.environ.get(
    "PLAYWRIGHT_NODEJS_PATH", str(REPO_ROOT / "studio/node-runtime/node")
)
PLAYWRIGHT_CLI = os.environ.get(
    "PLAYWRIGHT_CLI_PATH",
    "/usr/lib/chatgpt/resources/cua_node/lib/node_modules/playwright/cli.js",
)
CHROMIUM = os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium")

FINISH_ARTIFACTS = (
    REPO_ROOT
    / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb",
    REPO_ROOT
    / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds",
)


class SafeActionFailure(RuntimeError):
    """A safe UI action contract was violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SafeActionFailure(message)


def hashes() -> dict[Path, str]:
    values: dict[Path, str] = {}
    for path in FINISH_ARTIFACTS:
        require(path.is_file(), f"finish artifact missing: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        values[path] = digest.hexdigest()
    return values


def agent_health() -> dict[str, object]:
    with urlopen("http://127.0.0.1:43219/health", timeout=5) as response:  # noqa: S310 - fixed local endpoint
        import json

        return json.loads(response.read().decode("utf-8"))


def run() -> int:
    before = hashes()
    _driver.compute_driver_executable = lambda: (PLAYWRIGHT_NODE, PLAYWRIGHT_CLI)
    _transport.compute_driver_executable = lambda: (PLAYWRIGHT_NODE, PLAYWRIGHT_CLI)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROMIUM,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            errors: list[str] = []
            requests: list[tuple[str, str]] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: requests.append((request.method, request.url)),
            )
            page.goto(
                f"{BASE_URL}/tools?tab=run&action=check",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            page.wait_for_selector(".app-shell", timeout=30_000)
            page.wait_for_timeout(1_200)
            action = page.locator("#run-action")
            require(action.count() == 1, "Tools Run action selector is missing")
            require(action.input_value() == "check", "check deep link was not selected")

            page.get_by_role("button", name="Run", exact=True).click()
            log = page.locator(".run-log")
            for _ in range(240):
                if log.count() and "done" in log.inner_text().lower():
                    break
                page.wait_for_timeout(500)
            require(log.count() == 1, "safe action did not render its log")
            text = log.inner_text()
            require("COMPLETED" in text, f"safe action did not complete: {text[-600:]}")
            require("exit 0" in text, f"safe action exited unsuccessfully: {text[-600:]}")
            for tool in ("openroad", "yosys", "sta", "klayout"):
                require(tool in text, f"toolchain check did not report {tool}")
            require(
                any(method == "POST" and "/api/jobs" in url for method, url in requests),
                "Run control did not submit through the local-agent jobs API",
            )
            require(not errors, f"browser page error(s): {errors}")
        finally:
            browser.close()

    after = hashes()
    require(before == after, "safe UI action changed a protected finish artifact")
    health = agent_health()
    require(health.get("ok") is True, "local agent is not healthy after safe action")
    require(health.get("running_jobs") == 0, "safe action left a running job")
    print("UI_SAFE_ACTION=OK")
    print("UI_SAFE_ACTION_FINISH_HASHES=UNCHANGED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as error:  # noqa: BLE001 - report one actionable gate failure
        print(f"UI_SAFE_ACTION=FAIL: {error}")
        sys.exit(1)
