"""Local runtime for the PDflow desktop bridge.

The package intentionally uses only the Python standard library so it can run
next to the existing OpenROAD/ORFS checkout without adding a second dependency
manager.
"""

from .agent import LocalAgent
from .contracts import (
    JOB_STATES,
    REPORT_STATUSES,
    TERMINATION_CAUSES,
    ArtifactRef,
    ReportEnvelope,
    RunContext,
    validate_artifact,
    validate_report,
    validate_run,
)

__all__ = [
    "ArtifactRef",
    "JOB_STATES",
    "LocalAgent",
    "REPORT_STATUSES",
    "TERMINATION_CAUSES",
    "ReportEnvelope",
    "RunContext",
    "validate_artifact",
    "validate_report",
    "validate_run",
]
