#!/usr/bin/env python3
"""DSE files must not invoke signoff_all. Ingest is current_run, not gold."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))
from dse.flow_role import SIGNOFF_ORCHESTRATOR, dse_mentions_signoff_all  # noqa: E402
from dse.fidelity import dynamic_ir_current_path, ingest_pdn, ingest_physical  # noqa: E402
from dse.memory import DesignMemory  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    hits = dse_mentions_signoff_all(ROOT)
    check(hits == [], f"DSE does not call signoff_all (hits={hits})")
    check((ROOT / SIGNOFF_ORCHESTRATOR).is_file(), "signoff orchestrator exists")
    ctrl = (ROOT / "learn/dse/controller.py").read_text()
    check("signoff" in ctrl.lower(), "controller mentions signoff in the 'not' list")
    check("dynamic_ir_current_path" in ctrl, "controller attributes current_run, not gold")
    fid = (ROOT / "learn/dse/fidelity.py").read_text()
    check("dynamic_ir_current_path" in fid, "fidelity names the current_run helper")
    path = dynamic_ir_current_path("flowlab")
    check(path.name == "dynamic_ir_flowlab_direct.json", f"current path is _direct.json, got {path.name}")
    helper = fid.split("def dynamic_ir_current_path")[1].split("def ")[0]
    check('dynamic_ir_{variant}.json' not in helper, "current path never falls back to the gold sentinel")
    check("_current_run_ir" in fid, "ingest refuses gold:true as current_run")
    check('ir.get("gold") is True' in fid.split("def _current_run_ir")[1].split("def ")[0], "gold payload is dropped")
    tmp = Path(tempfile.mkdtemp(prefix="dse-ingest-")) / "m.jsonl"
    mem = DesignMemory(tmp)
    phys = ingest_physical("flowlab", mem, "gcd")
    check(phys is not None, "ingest_physical returns a candidate")
    dmv = float(phys.qor.dynamic_ir_mv or 0)
    check(abs(dmv - 5.173) < 0.02, f"ingest_physical uses current_run ~5.173, got {dmv}")
    check(abs(dmv - 45.298) > 1.0, "ingest_physical does not ingest gold 45.298 as the layout")
    check("current_run" in (phys.qor.note or ""), "ingest_physical note names current_run")
    pdn = ingest_pdn("flowlab", DesignMemory(tmp.parent / "p.jsonl"), "gcd")
    check(pdn is not None, "ingest_pdn returns a candidate")
    pdn_mv = float(pdn.qor.dynamic_ir_mv or 0)
    check(abs(pdn_mv - 5.173) < 0.02, f"ingest_pdn uses current_run ~5.173, got {pdn_mv}")
    print("ALL test_dse_role PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
