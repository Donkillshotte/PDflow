"""Acceptance tests for bounded native-tool registry discovery."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))

from pdflow_agent.registry import discover  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pdflow-registry-") as raw:
        repo = Path(raw)
        config = repo / "config/pdflow"
        config.mkdir(parents=True)
        counter = repo / "probe-count"
        fake = repo / "fake-tool"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, time\n"
            "counter = pathlib.Path(__file__).with_name('probe-count')\n"
            "try: value = int(counter.read_text())\n"
            "except (FileNotFoundError, ValueError): value = 0\n"
            "time.sleep(0.1)\n"
            "counter.write_text(str(value + 1))\n"
            "print('fake-tool 1.0')\n",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        help_fake = repo / "help-tool"
        help_fake.write_text(
            "#!/usr/bin/env python3\n"
            "print('help-tool usage')\n"
            "raise SystemExit(3)\n",
            encoding="utf-8",
        )
        help_fake.chmod(help_fake.stat().st_mode | stat.S_IXUSR)
        (config / "tool_registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "platform": "linux",
                    "default_timeout_seconds": 600,
                    "tools": [
                        {
                            "tool_id": "fake",
                            "display_name": "Fake tool",
                            "required": True,
                            "version_probe": ["--version"],
                            "executable_candidates": ["{repo}/fake-tool"],
                            "capabilities": ["inspect"],
                            "input_kinds": [],
                            "output_kinds": [],
                            "launch_profiles": ["batch"],
                            "report_parsers": [],
                            "status_mapping": {"exit_0": "PASS"},
                            "required_dependencies": [],
                            "commands": {},
                        },
                        {
                            "tool_id": "help",
                            "display_name": "Help-probed tool",
                            "required": False,
                            "version_probe": ["--help"],
                            "version_probe_exit_codes": [3],
                            "version_label": "help-tool 2.0",
                            "executable_candidates": ["{repo}/help-tool"],
                            "capabilities": ["inspect"],
                            "input_kinds": [],
                            "output_kinds": [],
                            "launch_profiles": ["batch"],
                            "report_parsers": [],
                            "status_mapping": {"exit_3": "READY"},
                            "required_dependencies": [],
                            "commands": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        results: list[dict] = []
        lock = threading.Lock()

        def run_discovery() -> None:
            result = discover(repo)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=run_discovery) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert len(results) == len(threads), results
        assert all(
            result["tools"][0]["availability"] == "READY"
            and result["tools"][1]["availability"] == "READY"
            and result["tools"][1]["version"] == "help-tool 2.0"
            for result in results
        )
        assert counter.read_text(encoding="utf-8") == "1"

        discover(repo)
        assert counter.read_text(encoding="utf-8") == "1"
        discover(repo, force=True)
        assert counter.read_text(encoding="utf-8") == "2"

    print("OK test_registry")


if __name__ == "__main__":
    main()
