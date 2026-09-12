#!/usr/bin/env python3
"""Exercise the production shell at the supported desktop and narrow widths.

The test intentionally uses a real Chromium page instead of snapshotting CSS
files.  It catches implicit grid tracks, page-level horizontal overflow and
workspaces that render inside a centered legacy document container.

Usage:
    STUDIO_URL=http://127.0.0.1:43227 python3 learn/scripts/test_ui_layout_matrix.py

The local Python Playwright package and a Chromium executable are required.
No job is launched by this test; it only reads the rendered application.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from playwright._impl import _driver, _transport
from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("STUDIO_URL", "http://127.0.0.1:43227").rstrip("/")
CHROMIUM = os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium")
REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT_NODE = os.environ.get(
    "PLAYWRIGHT_NODEJS_PATH", str(REPO_ROOT / "studio/node-runtime/node")
)
PLAYWRIGHT_CLI = os.environ.get(
    "PLAYWRIGHT_CLI_PATH",
    "/usr/lib/chatgpt/resources/cua_node/lib/node_modules/playwright/cli.js",
)


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int


ROUTES = (
    "/",
    "/flow?platform=asap7&phase=finish&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps",
    "/lab",
    "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps",
    "/product",
    "/tools?tab=registry",
    "/lab?tab=bench",
    "/lab?tab=dse",
    "/lab?tab=provenance",
    "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps&tab=geometry",
    "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps&tab=connectivity",
    "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps&tab=layout",
    "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps&tab=docs",
    "/product?tab=checks",
    "/product?tab=layout",
    "/tools?tab=ops",
    "/tools?tab=run&action=check",
    "/tools?tab=results&stage=finish&action=finish",
    "/lessons",
    "/lessons/00-intro",
    "/materials",
)
VIEWPORTS = (
    Viewport(980, 680),
    Viewport(1280, 720),
    Viewport(1920, 1080),
    Viewport(768, 1024),
    Viewport(390, 844),
)

WORKSPACE_SELECTORS = (
    ".overview-page",
    ".asap7-workbench",
    ".package-workspace",
    ".fl-pro",
    ".product-page",
    ".studio-pro-page",
    ".lesson-grid",
    ".wizard",
    ".material-list",
    "main",
)


def wait_for_workspace(page) -> None:
    """Wait for the client surface, not only the server-rendered app shell.

    Next development mode can render the shell before a client-only surface
    has committed.  A fixed delay made the geometry test sample a legitimate
    loading placeholder as a zero-sized workspace.  The bounded condition
    below still fails a permanently blank page, while measuring the same
    rendered state that an engineer can actually interact with.
    """

    selectors = json.dumps(WORKSPACE_SELECTORS)
    page.wait_for_function(
        f"""() => {{
          const selectors = {selectors};
          const node = selectors.map((selector) => document.querySelector(selector)).find(Boolean);
          if (!node) return false;
          const box = node.getBoundingClientRect();
          return box.width > 0 && box.height > 0;
        }}""",
        timeout=30_000,
    )


def measure(page):
    return page.evaluate(
        """() => {
          const rect = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const box = node.getBoundingClientRect();
            return {
              x: Math.round(box.x),
              y: Math.round(box.y),
              width: Math.round(box.width),
              height: Math.round(box.height),
            };
          };
          return {
            inner: { width: window.innerWidth, height: window.innerHeight },
            body_scroll_width: document.body.scrollWidth,
            document_scroll_width: document.documentElement.scrollWidth,
            app: rect('.app-shell'),
            main: rect('.app-main'),
            workspace: rect('.overview-page') || rect('.asap7-workbench') || rect('.package-workspace') || rect('.fl-pro') || rect('.product-page') || rect('.studio-pro-page') || rect('.lesson-grid') || rect('.wizard') || rect('.material-list') || rect('main'),
            canvas: rect('.asap7-viewer-column') || rect('.asap7-package-canvas') || rect('.pkg-layout-view .fl-layout-stage') || rect('.fl-main-panel'),
            light_surfaces: [
              '.cmd-trigger',
              '.gallery-tile',
              '.search-bar input',
              '.wizard-step',
              '.suite-hooks li',
              '.pkg-report-card',
              '.pkg-live-strip',
              '.pkg-ledger-card',
            ].flatMap((selector) => Array.from(document.querySelectorAll(selector)).map((node) => {
              const background = getComputedStyle(node).backgroundColor;
              const match = background.match(/rgba?\\(([^)]+)\\)/);
              if (!match) return null;
              const channels = match[1].split(',').map((part) => Number.parseFloat(part.trim()));
              const alpha = channels.length === 4 ? channels[3] : 1;
              return channels.length >= 3 && channels[0] > 180 && channels[1] > 180 && channels[2] > 180 && alpha > 0.5
                ? selector
                : null;
            })).filter(Boolean),
          };
        }"""
    )


def run() -> int:
    failures = []
    # The host intentionally has no system Node installation. Playwright's
    # Python driver supports an explicit runtime path and must use the same
    # embedded Node binary as the production build in this repository. Debian's
    # Python package also hardcodes a system CLI path, so replace that one
    # implementation hook when the bundled CLI is selected.
    os.environ.setdefault("PLAYWRIGHT_NODEJS_PATH", PLAYWRIGHT_NODE)
    def compute_driver_executable():
        return PLAYWRIGHT_NODE, PLAYWRIGHT_CLI

    _driver.compute_driver_executable = compute_driver_executable
    _transport.compute_driver_executable = compute_driver_executable
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROMIUM,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for viewport in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": viewport.width, "height": viewport.height}
                )
                try:
                    page = context.new_page()
                    for route in ROUTES:
                        page.goto(
                            BASE_URL + route,
                            wait_until="domcontentloaded",
                            timeout=60_000,
                        )
                        page.wait_for_selector(".app-shell", timeout=30_000)
                        wait_for_workspace(page)
                        page.wait_for_timeout(100)
                        result = measure(page)
                        checks = {
                            "body_no_horizontal_overflow": result["body_scroll_width"]
                            <= viewport.width,
                            "document_no_horizontal_overflow": result[
                                "document_scroll_width"
                            ]
                            <= viewport.width,
                            "app_full_width": result["app"] is not None
                            and result["app"]["width"] == viewport.width,
                            "app_full_height": result["app"] is not None
                            and result["app"]["height"] == viewport.height,
                            "main_present": result["main"] is not None
                            and result["main"]["width"] > 0,
                            "workspace_present": result["workspace"] is not None
                            and result["workspace"]["width"] > 0,
                            "theme_surfaces_are_dark": not result["light_surfaces"],
                        }
                        needs_canvas = route.startswith("/flow") or route.startswith("/lab?tab=bench") or route.startswith("/pkg?") and ("tab=" not in route or "tab=layout" in route)
                        if needs_canvas:
                            checks["design_canvas_present"] = result["canvas"] is not None and result["canvas"]["width"] > 0 and result["canvas"]["height"] > 0
                        failed_checks = [
                            name for name, passed in checks.items() if not passed
                        ]
                        status = "PASS" if not failed_checks else "FAIL"
                        print(
                            f"{status} {viewport.width}x{viewport.height} {route} "
                            f"{json.dumps(result, separators=(',', ':'))}"
                        )
                        if failed_checks:
                            failures.append(
                                {
                                    "viewport": [viewport.width, viewport.height],
                                    "route": route,
                                    "checks": failed_checks,
                                    "result": result,
                                }
                            )
                finally:
                    context.close()
        finally:
            browser.close()

    if failures:
        print(json.dumps({"failures": failures}, indent=2))
        return 1
    print("UI VIEWPORT MATRIX PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
