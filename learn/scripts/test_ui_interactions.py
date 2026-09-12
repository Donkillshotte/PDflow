#!/usr/bin/env python3
"""Exercise the high-value PDflow workbench interactions and one safe scenario.

This is intentionally a browser-level contract test.  It checks that navigation,
phase selection, profile menus, viewer controls, panel toggles, focus mode and
long-job confirmation behave as UI actions.  The System PDN visual test also
executes one bounded, isolated scenario through the local agent so the
waveform/report path is covered end to end.

Usage:
    STUDIO_URL=http://127.0.0.1:43227 python3 learn/scripts/test_ui_interactions.py

The test requires the local agent used by ``scripts/run_studio.sh``.  The
scenario writes only its agent-owned ``.pdflow/runs`` directory; canonical
finish artifacts are not changed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright._impl import _driver, _transport
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright


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
FLOW_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5_320ps"
FLOW_URL = (
    f"/flow?platform=asap7&phase=finish&variant={FLOW_VARIANT}"
)
PKG_URL = f"/pkg?platform=asap7&variant={FLOW_VARIANT}"


class InteractionFailure(RuntimeError):
    """A browser interaction contract was violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InteractionFailure(message)


def goto_ready(page: Page, route: str) -> None:
    page.goto(BASE_URL + route, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_selector(".app-shell", timeout=30_000)
    # SSR makes the shell visible before client hydration.  Do not click
    # controls in that interval: a successful locator click would otherwise
    # dispatch to an inert server-rendered button and create false failures.
    page.wait_for_timeout(250)
    if page.locator(".runtime-status-bar").count():
        page.wait_for_function(
            """() => {
              const node = document.querySelector('.runtime-status-bar');
              return Boolean(node && !node.textContent?.includes('CONTEXT LOADING'));
            }""",
            timeout=30_000,
        )
    else:
        page.wait_for_timeout(2_000)


def wait_for_url_contains(page: Page, token: str) -> None:
    for _ in range(100):
        if token in page.url:
            return
        page.wait_for_timeout(100)
    raise InteractionFailure(f"URL did not contain {token!r}; current URL: {page.url}")


def wait_for_visible(page: Page, selector: str, marker: str) -> None:
    """Wait for a React/router commit instead of sampling during a transition."""

    try:
        page.wait_for_selector(selector, state="visible", timeout=5_000)
    except PlaywrightError as error:
        raise InteractionFailure(f"{marker}: {selector} did not become visible") from error


def assert_no_job_posts(requests: list[tuple[str, str]], marker: str) -> None:
    job_posts = [
        url
        for method, url in requests
        if method == "POST" and ("/api/jobs" in url or "/api/run" in url)
    ]
    require(not job_posts, f"{marker}: unexpected job request(s): {job_posts}")


def assert_no_page_errors(errors: list[str], marker: str) -> None:
    require(not errors, f"{marker}: browser page error(s): {errors}")


def test_flow_controls(page: Page) -> None:
    requests: list[tuple[str, str]] = []
    errors: list[str] = []
    page.on("request", lambda request: requests.append((request.method, request.url)))
    page.on("pageerror", lambda error: errors.append(str(error)))
    goto_ready(page, FLOW_URL)

    require(page.locator(".asap7-workbench").is_visible(), "FlowLab workbench is missing")
    require(page.locator(".fl-layout-canvas").is_visible(), "design canvas is missing")
    assert_no_job_posts(requests, "initial FlowLab load")

    phase_ids = ["synth", "floorplan", "pdn", "place", "cts", "route", "finish"]
    for phase_id in phase_ids:
        page.locator(f".asap7-phase-tab").filter(has_text=phase_id.capitalize() if phase_id != "pdn" else "Chip PDN").click()
        wait_for_url_contains(page, f"phase={phase_id}")
        require(
            page.locator(f".asap7-phase-tab[aria-current='step']").count() == 1,
            f"phase {phase_id} did not become active",
        )
    assert_no_job_posts(requests, "phase navigation")

    # The finish profile is loaded before exercising viewer controls, so the
    # real ODB-backed image enables the zoom/fit actions.
    page.locator(".asap7-phase-tab").filter(has_text="Finish").click()
    page.wait_for_function(
        """() => {
          const image = document.querySelector('.fl-vp img');
          return Boolean(image && image.naturalWidth > 0);
        }""",
        timeout=30_000,
    )
    for title in ("Zoom +", "Zoom −", "Fit (0)"):
        button = page.locator(f"button[title='{title}']")
        require(button.count() == 1 and button.is_enabled(), f"viewer control unavailable: {title}")
        button.click()
    layout_button = page.locator(".fl-layout-actions button").filter(has_text="Layout")
    require(layout_button.count() == 1, "Layout viewer mode button missing")
    layout_button.click()
    fullscreen_button = page.locator("button[title^='Fullscreen']")
    require(fullscreen_button.count() == 1, "viewer fullscreen button missing")
    try:
        fullscreen_button.click()
    except PlaywrightError as error:
        raise InteractionFailure(f"viewer fullscreen action failed: {error}") from error
    page.wait_for_timeout(150)
    if page.evaluate("document.fullscreenElement !== null"):
        fullscreen_button.click()
        page.wait_for_timeout(150)
    require(
        not page.evaluate("document.fullscreenElement !== null"),
        "viewer fullscreen did not return to the workbench",
    )

    layer_close = page.locator(".fl-layer-close")
    if layer_close.count() > 0 and layer_close.is_visible():
        layer_close.click()
        require(page.locator(".fl-layer-reopen").is_visible(), "layer HUD did not collapse")
        page.locator(".fl-layer-reopen").click()
        require(page.locator(".fl-layer-close").is_visible(), "layer HUD did not reopen")

    # Profile controls update only the isolated URL/profile context.  They do
    # not run a cook implicitly.
    # Analysis Workbench contains additional Corner controls for the selected
    # analysis mode.  Scope profile assertions to the native-cook form rather
    # than assuming the page has only one label with that text.
    profile_controls = page.locator(".asap7-form-grid")
    corner = profile_controls.locator("label").filter(has_text="Corner").locator("select")
    require(corner.count() == 1, "Corner profile selector missing")
    corner.select_option("WC")
    wait_for_url_contains(page, "_wc_")
    page.wait_for_timeout(300)
    clock = profile_controls.locator("label").filter(has_text="Clock period").locator("input")
    require(clock.count() == 1, "clock profile input missing")
    clock.fill("330")
    wait_for_url_contains(page, "_330ps")
    mbff = page.get_by_role("checkbox", name="Enable MBFF clustering")
    require(mbff.count() == 1, "MBFF checkbox missing")
    mbff.check()
    wait_for_url_contains(page, "_mbff")
    mbff.uncheck()
    page.wait_for_timeout(250)
    assert_no_job_posts(requests, "profile changes")

    # Analysis Workbench preflight is an explicit, read-only planning step.
    # It may POST the typed preview request, but it must never enqueue a native
    # job until the engineer presses the separate confirmation action.
    launcher = page.locator(".analysis-bundle-launcher")
    require(launcher.count() == 1, "Analysis Workbench launcher is missing")
    preview = launcher.get_by_role("button", name="Preview", exact=True)
    require(preview.count() == 1 and preview.is_enabled(), "analysis preflight button unavailable")
    preview.click()
    for _ in range(300):
        if launcher.locator(".analysis-bundle-plan").count() > 0 or launcher.get_by_role("status").count() > 0:
            break
        page.wait_for_timeout(100)
    if launcher.locator(".analysis-bundle-plan").count() != 1:
        raise InteractionFailure(
            "analysis preflight did not return a displayable plan"
            f" (url={page.url}; text={launcher.inner_text()[:240]!r})"
        )
    require(
        launcher.get_by_role("button", name="Confirm & queue", exact=True).count() == 1,
        "analysis plan did not expose an explicit queue boundary",
    )
    assert_no_job_posts(requests, "analysis preflight")

    # Long ASAP7 actions must stop at a confirmation dialog.  Cancelling is a
    # real user path and must leave the agent untouched.
    action = page.locator("#run-action")
    require(action.count() == 1, "ASAP7 action selector missing")
    action.select_option("lab_asap7_chip_pdn")
    page.locator(".asap7-action-section").get_by_role("button", name="Run", exact=True).click()
    dialog = page.get_by_role("alertdialog")
    require(dialog.is_visible(), "long ASAP7 action did not require confirmation")
    require(dialog.get_by_role("button", name="Start anyway").is_visible(), "confirmation action missing")
    dialog.get_by_role("button", name="Cancel").click()
    require(not dialog.is_visible(), "confirmation dialog did not close")
    assert_no_job_posts(requests, "cancelled confirmation")

    # Shared shell controls are independent of the surface content.
    inspector = page.get_by_role("button", name="Inspector", exact=True)
    inspector.click()
    require(page.locator(".workspace-inspector").is_visible(), "inspector did not open")
    page.get_by_role("button", name="Close inspector").click()
    require(not page.locator(".workspace-inspector").is_visible(), "inspector did not close")

    runtime = page.get_by_role("button", name="Runtime", exact=True)
    runtime.click()
    require(page.locator(".workspace-dock").is_visible(), "runtime dock did not open")
    page.get_by_role("button", name="Close runtime dock").click()
    require(not page.locator(".workspace-dock").is_visible(), "runtime dock did not close")

    focus = page.locator(".workspace-focus-button")
    focus.click()
    require(page.locator(".app-shell.is-focus-mode").count() == 1, "focus mode did not activate")
    page.keyboard.press("Escape")
    require(page.locator(".app-shell.is-focus-mode").count() == 0, "Escape did not exit focus mode")

    palette_trigger = page.locator("button[aria-label='Open command palette']")
    palette_trigger.click()
    palette = page.locator(".cmd-palette")
    require(palette.is_visible(), "command palette did not open")
    palette.locator("input[aria-label='Search command']").fill("Package")
    for _ in range(50):
        if palette.get_by_role("option").count() > 0:
            break
        page.wait_for_timeout(100)
    require(palette.get_by_role("option").count() > 0, "command palette search returned no Package target")
    package_target = palette.get_by_role("option").filter(has_text="Package / PKG")
    require(package_target.count() == 1, "command palette did not expose the Package navigation target")
    package_target.click()
    wait_for_url_contains(page, "/pkg")
    require(not palette.is_visible(), "command palette did not close after navigation")
    page.locator("button[aria-label='Open command palette']").click()
    require(page.locator(".cmd-palette").is_visible(), "command palette did not reopen after navigation")
    page.keyboard.press("Escape")
    require(not page.locator(".cmd-palette").is_visible(), "command palette did not close")
    assert_no_page_errors(errors, "FlowLab controls")


def test_surface_navigation(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    goto_ready(page, "/lab")
    require(page.locator(".asap7-workbench").is_visible(), "default Lab did not open ASAP7 workbench")
    flow_link = page.locator("a[href='/flow?platform=asap7']")
    require(flow_link.count() == 1, "Lab sidebar lost ASAP7 FlowLab context")
    flow_link.click()
    wait_for_url_contains(page, "platform=asap7")
    page.wait_for_selector(".asap7-workbench", timeout=30_000)
    require(page.locator(".asap7-workbench").is_visible(), "ASAP7 FlowLab navigation did not resolve")

    goto_ready(page, PKG_URL)
    require(page.locator(".asap7-package-panel").is_visible(), "Package panel is missing")
    require(page.locator(".asap7-package-canvas").is_visible(), "Package design canvas is missing")
    require(page.locator("a").filter(has_text="Finish").count() > 0, "Package Finish deep link is missing")
    action = page.locator("#run-action")
    require(action.count() == 1, "Package action selector missing")
    page.locator(".asap7-package-runner").get_by_role("button", name="Run", exact=True).click()
    dialog = page.get_by_role("alertdialog")
    require(dialog.is_visible(), "Package action did not require confirmation")
    dialog.get_by_role("button", name="Cancel").click()

    goto_ready(page, "/tools?tab=registry")
    require(page.locator(".app-main").is_visible(), "Tools surface did not render")
    require(page.locator("#tools-panel-suite").is_visible(), "Registry deep-link did not select the Registry view")
    assert_no_page_errors(errors, "surface navigation")


def test_system_pdn_visual(page: Page) -> None:
    """Exercise the real Package -> System PDN visual and one isolated run."""

    requests: list[tuple[str, str]] = []
    errors: list[str] = []
    page.on("request", lambda request: requests.append((request.method, request.url)))
    page.on("pageerror", lambda error: errors.append(str(error)))
    goto_ready(
        page,
        "/pkg?platform=asap7&variant=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps",
    )

    visual = page.locator("section[aria-label='System PDN visual analysis']")
    require(visual.count() == 1 and visual.is_visible(), "System PDN visual is missing")
    baseline_wave = visual.locator("svg[aria-label*='transient voltage waveform']")
    require(baseline_wave.count() == 1, "baseline TRAN waveform is missing")
    require(
        visual.locator("svg[aria-label*='AC impedance curve']").count() == 0,
        "AC plot should not be active before selecting its tab",
    )
    for lane in ("VRM", "Board", "Package", "Die"):
        button = visual.get_by_role("button", name=lane, exact=True)
        require(button.count() == 1 and button.is_enabled(), f"waveform lane toggle missing: {lane}")

    die = visual.get_by_role("button", name="Die", exact=True)
    die.click()
    require(die.get_attribute("aria-pressed") == "false", "Die lane did not hide")
    die.click()
    require(die.get_attribute("aria-pressed") == "true", "Die lane did not restore")

    # The chart is interactive, not a static image: moving across it exposes a
    # sampled voltage tooltip and keeps the plotted node values inspectable.
    box = baseline_wave.bounding_box()
    require(box is not None and box["width"] > 0, "TRAN waveform has no rendered geometry")
    page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.48)
    page.wait_for_function(
        """() => {
          const node = document.querySelector("svg[aria-label*='transient voltage waveform']");
          return Boolean(node && node.textContent?.includes('t ='));
        }""",
        timeout=5_000,
    )

    visual.get_by_role("tab", name="AC · Z(f)", exact=True).click()
    require(
        visual.locator("svg[aria-label*='AC impedance curve']").count() == 1,
        "AC impedance plot did not activate",
    )
    require(visual.get_by_text("configured Ztarget", exact=False).count() > 0, "AC target legend is missing")
    visual.get_by_role("tab", name="TRAN · waveform", exact=True).click()

    control = visual.locator("#system-pdn-package_r_mohm")
    require(control.count() == 1 and control.is_enabled(), "System PDN R control is missing")
    control.fill("44")
    require(control.input_value() == "44", "System PDN control did not accept the scenario value")

    visual.get_by_role("button", name="Run ngspice scenario", exact=True).click()
    page.wait_for_function(
        """() => {
          const node = document.querySelector("section[aria-label='System PDN ngspice simulator']");
          return Boolean(node && node.textContent?.includes('Scenario ready'));
        }""",
        timeout=120_000,
    )
    require(visual.get_by_role("button", name="View scenario", exact=True).count() == 1, "scenario view action is missing")
    require(visual.get_by_text("READY", exact=True).count() > 0, "scenario did not reach READY")
    require(
        any(method == "POST" and "/api/runs" in url for method, url in requests),
        "scenario did not create an isolated run through the API",
    )
    require(
        any(method == "POST" and "/api/jobs" in url for method, url in requests),
        "scenario did not submit through the local-agent jobs API",
    )
    require(
        not any(method == "GET" and "/api/run/stream" in url for method, url in requests),
        "System PDN scenario fell back to the legacy stream path",
    )
    visual.get_by_role("button", name="View baseline", exact=True).click()
    require(baseline_wave.count() == 1, "baseline view did not return after scenario")
    assert_no_page_errors(errors, "System PDN visual and scenario")


def test_workspace_tabs(page: Page) -> None:
    requests: list[tuple[str, str]] = []
    errors: list[str] = []
    page.on("request", lambda request: requests.append((request.method, request.url)))
    page.on("pageerror", lambda error: errors.append(str(error)))

    goto_ready(page, PKG_URL)
    for tab_id, label in (
        ("system", "System PDN"),
        ("layout", "Layout"),
        ("geometry", "Geometry"),
        ("connectivity", "Connectivity"),
        ("docs", "References"),
    ):
        page.get_by_role("tab", name=label).click()
        wait_for_visible(page, f"#package-panel-{tab_id}", f"Package tab {tab_id}")
        require(
            page.locator(f"#package-panel-{tab_id}").is_visible(),
            f"Package tab {tab_id} did not reveal its panel",
        )

    goto_ready(page, PKG_URL + "&tab=connectivity")
    require(
        page.locator("#package-panel-connectivity").is_visible(),
        "Package connectivity deep-link did not select the requested view",
    )
    goto_ready(page, PKG_URL + "&tab=layout")
    require(
        page.locator("#package-panel-layout").is_visible(),
        "Package layout deep-link did not select the requested view",
    )

    goto_ready(page, "/lab?tab=bench")
    for tab_id, label in (
        ("dse", "DSE compare"),
        ("provenance", "Provenance"),
        ("bench", "Bench"),
    ):
        page.get_by_role("tab", name=label).click()
        wait_for_url_contains(page, f"tab={tab_id}")
        require(
            page.locator(f"#lab-panel-{tab_id}").is_visible(),
            f"Lab tab {tab_id} did not reveal its panel",
        )

    goto_ready(page, "/product")
    for tab_id, label in (
        ("checks", "Checks"),
        ("layout", "Layout"),
        ("summary", "Summary"),
    ):
        page.get_by_role("tab", name=label).click()
        wait_for_visible(page, f"#product-panel-{tab_id}", f"Product tab {tab_id}")
        require(
            page.locator(f"#product-panel-{tab_id}").is_visible(),
            f"Product tab {tab_id} did not reveal its panel",
        )

    goto_ready(page, "/product?tab=layout")
    require(
        page.locator("#product-panel-layout").is_visible(),
        "Product layout deep-link did not select the requested view",
    )

    goto_ready(page, "/tools?tab=registry")
    for tab_id, label in (
        ("ops", "Operations"),
        ("run", "Run"),
        ("results", "Results"),
        ("suite", "Registry"),
    ):
        page.get_by_role("tab", name=label).click()
        wait_for_visible(page, f"#tools-panel-{tab_id}", f"Tools tab {tab_id}")
        require(
            page.locator(f"#tools-panel-{tab_id}").is_visible(),
            f"Tools tab {tab_id} did not reveal its panel",
        )
    page.locator(".stage-jump button").filter(has_text="route").click()
    wait_for_url_contains(page, "stage=route")
    require("tab=results" in page.url and "action=route" in page.url, "Tools phase deep-link was not preserved")
    page.get_by_role("tab", name="Run").click()
    action = page.locator("#run-action")
    require(action.count() == 1, "Tools Run action selector missing")
    action.select_option("check")
    for action_id in ("power_signoff", "signoff_all", "eco_apply", "export_spice_lab"):
        goto_ready(page, f"/tools?tab=run&action={action_id}")
        require(
            page.locator("#run-action").input_value() == action_id,
            f"Tools action deep-link lost {action_id}",
        )
    assert_no_job_posts(requests, "workspace tab navigation")
    assert_no_page_errors(errors, "workspace tabs")


def test_mobile_shell(page: Page) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    goto_ready(page, FLOW_URL)
    require(page.locator(".app-shell").evaluate("node => node.getBoundingClientRect().width") == 390, "mobile shell is not full width")
    require(
        page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"),
        "mobile shell has global horizontal overflow",
    )
    nav_button = page.locator("button[aria-label='Expand application navigation']")
    visible_nav_buttons = []
    for _ in range(100):
        visible_nav_buttons = [
            nav_button.nth(index)
            for index in range(nav_button.count())
            if nav_button.nth(index).is_visible()
        ]
        if visible_nav_buttons:
            break
        page.wait_for_timeout(100)
    require(visible_nav_buttons, "mobile navigation drawer trigger missing")
    visible_nav_buttons[0].click()
    page.wait_for_timeout(200)
    require(page.locator(".site-nav:not(.is-collapsed)").is_visible(), "mobile navigation drawer did not open")
    nav_button = page.locator("button[aria-label='Collapse application navigation']")
    require(nav_button.count() == 1, "mobile navigation close control missing")
    nav_button.click()
    page.wait_for_timeout(200)
    require(page.locator(".site-nav.is-collapsed").count() == 1, "mobile navigation drawer did not close")
    assert_no_page_errors(errors, "mobile shell")


def run() -> int:
    # The host intentionally has no system Node.  Use the repository's native
    # runtime and the bundled Playwright CLI, matching the layout matrix test.
    _driver.compute_driver_executable = lambda: (PLAYWRIGHT_NODE, PLAYWRIGHT_CLI)
    _transport.compute_driver_executable = lambda: (PLAYWRIGHT_NODE, PLAYWRIGHT_CLI)
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROMIUM,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 960})
            try:
                page = context.new_page()
                for name, test in (
                    ("flow-controls", test_flow_controls),
                    ("surface-navigation", test_surface_navigation),
                    ("system-pdn-visual", test_system_pdn_visual),
                    ("workspace-tabs", test_workspace_tabs),
                ):
                    try:
                        test(page)
                        print(f"PASS {name}")
                    except Exception as error:  # noqa: BLE001 - report every UI gate
                        failures.append(f"{name}: {error}")
                        print(f"FAIL {name}: {error}")
            finally:
                context.close()

            mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
            try:
                test_mobile_shell(mobile_context.new_page())
                print("PASS mobile-shell")
            except Exception as error:  # noqa: BLE001 - report the UI gate
                failures.append(f"mobile-shell: {error}")
                print(f"FAIL mobile-shell: {error}")
            finally:
                mobile_context.close()
        finally:
            browser.close()

    if failures:
        print("UI INTERACTION TESTS FAILED")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("UI INTERACTION TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
