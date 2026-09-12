#!/usr/bin/env python3
"""Contract tests for the repository-owned Symphony workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_symphony_workflow import validate


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "WORKFLOW.md"


class SymphonyWorkflowTests(unittest.TestCase):
    def test_repository_workflow_is_valid(self) -> None:
        self.assertEqual(validate(WORKFLOW), [])

    def test_label_gate_is_required(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8").replace(
            "    - symphony\n", "    - manually-reviewed\n", 1
        )
        with tempfile.TemporaryDirectory(prefix="pdflow-symphony-test-") as directory:
            path = Path(directory) / "WORKFLOW.md"
            path.write_text(content, encoding="utf-8")
            errors = validate(path)
        self.assertTrue(any("required_labels" in error for error in errors))

    def test_workspace_must_be_explicitly_isolated(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8").replace(
            "  root: $PD_FLOW_SYMPHONY_WORKSPACE_ROOT\n",
            "  root: /tmp/shared-workspace\n",
            1,
        )
        with tempfile.TemporaryDirectory(prefix="pdflow-symphony-test-") as directory:
            path = Path(directory) / "WORKFLOW.md"
            path.write_text(content, encoding="utf-8")
            errors = validate(path)
        self.assertTrue(any("workspace.root" in error for error in errors))

    def test_hooks_cannot_introduce_unbounded_execution(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8").replace(
            "    true\nagent:\n", "    docker run pdflow\nagent:\n", 1
        )
        with tempfile.TemporaryDirectory(prefix="pdflow-symphony-test-") as directory:
            path = Path(directory) / "WORKFLOW.md"
            path.write_text(content, encoding="utf-8")
            errors = validate(path)
        self.assertTrue(any("forbidden operation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
