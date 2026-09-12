#!/usr/bin/env python3
"""I2 Studio contract: ASAP7/BSPDN is lab-only and PROXY-first.

T5-T9 exercise the comparison firewall, T15 guards the suite hub boundary,
and T25 proves that an explicit thermal GAP is not by itself a lab-admit
failure. The semantic checks execute the real TypeScript helpers after a
side-effect-free transpile; no report or result tree is modified.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "studio"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def run_contract_helpers() -> dict[str, bool]:
    node = STUDIO / "node-runtime" / "node"
    typescript = STUDIO / "node_modules" / "typescript"
    check(node.is_file(), "bundled Node runtime exists")
    check(typescript.is_dir(), "Studio TypeScript runtime exists")
    script = r'''
const fs = require("fs");
const ts = require(process.argv[1]);
const source = fs.readFileSync(process.argv[2], "utf8");
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
const moduleValue = { exports: {} };
new Function("require", "module", "exports", js)(require, moduleValue, moduleValue.exports);
const api = moduleValue.exports;
const mesh = (id, fp, topology, extra = {}) => ({
  mesh_id: id,
  mesh_fingerprint: fp,
  platform: "asap7",
  design: "gcd",
  nickname: "gcd",
  topology,
  ...extra,
});
const proxy = {
  ok: true,
  status: "pass",
  surface: "lab_asap7",
  platform: "asap7",
  mesh_id: "asap7_bspdn_proxy_m89",
  mesh_fingerprint: "m89-fp-1",
  topology: "bspdn_proxy",
  design: "gcd",
  nickname: "gcd",
  tool_id: "pdnsim_proxy",
  license_class: "educational_proxy",
  honesty: "PROXY",
  honesty_reason: "external proxy mesh; no foundry correlation",
  leftovers: [{ id: "thermal_gap", message: "HotSpot not run" }],
  ok_claim: false,
  product_signoff: false,
  lab_admit: { ok: true, reason: "proxy schema/provenance" },
  product_win: false,
  productWin: false,
  win_eligible: false,
  winEligible: false,
  comparable_to_gold_ir: false,
  comparableToGoldIr: false,
  thermal: { status: "blocked", honesty: "GAP", model_id: null },
};
const result = {
  T5: api.isSameMeshCompatible(mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn"), mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn")),
  T6: !api.isSameMeshCompatible(mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn"), mesh("asap7_bspdn_proxy_m89", null, "bspdn")) &&
      !api.isSameMeshCompatible(mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn"), mesh("asap7_bspdn_proxy_m89", "fp-2", "bspdn")),
  T7: !api.isLabComparisonCompatible(mesh("asap7_chip_tier_b", "fp-1", "chip_fs"), mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn_proxy"), true),
  T8: !api.isLabComparisonCompatible(mesh("asap7_candidate_bspdn_m89", "fp-1", "bspdn_proxy"), mesh("asap7_chip_tier_b", "fp-1", "chip_fs"), true),
  T9: !api.isLabComparisonCompatible(mesh("asap7_bspdn_proxy_m89", "fp-1", "bspdn_proxy"), { mesh_id: "nangate_chip_tier_b", mesh_fingerprint: "fp-1", platform: "nangate45", design: "gcd", nickname: "gcd", topology: "chip_fs" }, true),
  T25: api.evaluateLabAdmit(proxy).ok && api.evaluateLabAdmit(proxy).thermalGapAllowed && api.evaluateLabAdmit(proxy).thermal.honesty === "GAP" && api.evaluateLabAdmit(proxy).ir.honesty === "PROXY",
};
process.stdout.write(JSON.stringify(result));
'''
    result = subprocess.run(
        [str(node), "-e", script, str(typescript), str(STUDIO / "src/lib/labHonesty.ts")],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    honesty = (STUDIO / "src/lib/labHonesty.ts").read_text()
    lab = (STUDIO / "src/lib/lab.ts").read_text()
    bench = (STUDIO / "src/components/LabBench.tsx").read_text()
    signoff = (STUDIO / "src/lib/signoff.ts").read_text()
    suite = (STUDIO / "src/lib/suite.ts").read_text()
    suite_hub = (STUDIO / "src/components/SuiteHub.tsx").read_text()
    route = (STUDIO / "src/app/api/lab/route.ts").read_text()

    check('"pass", "fail", "blocked", "not_run"' in honesty, "dual-axis status enum is closed")
    check('"GAP", "PROXY", "PARTIAL"' in honesty, "honesty enum is closed")
    check("PROXY is never a" in honesty and "never emitted as a status" in honesty, "PROXY/status firewall is documented")
    check("thermal" in honesty and "never inherits" in honesty, "thermal honesty is isolated")
    check("isSameMeshCompatible" in honesty and "meshFingerprint" in honesty, "same_mesh needs a fingerprint")
    check("isAsap7BspdnProxyMesh" in honesty and "tool_id" in honesty and "license_class" in honesty, "proxy row requirements are encoded")

    check("readAsap7ProxyReport" in lab, "Lab snapshot discovers the proxy report family")
    check("isCurrentAsap7Artifact" in lab, "proxy report freshness is guarded")
    check('"lab_asap7_thermal.json"' in lab, "thermal report is read as its own artifact")
    check("evaluateLabAdmit" in lab and "labAdmitReason" in lab, "lab-admit result reaches /api/lab")
    check("getLabSnapshot" in route and "NextResponse.json" in route, "/api/lab remains the lab surface")

    check('id="bspdn"' in bench, "BSPDN deep-link stays inside LabBench")
    check("IR claim class" in bench and "Thermal claim class" in bench, "UI shows both honesty pillars")
    check("Named leftovers" in bench and "lb-evidence-leftovers" in bench, "UI shows named leftovers")
    check("PROXY-FIRST OK" in bench and "status" in bench, "UI makes honesty primary and status secondary")

    check("evaluateLabAdmit" in signoff and "honesty?: LabHonesty" in signoff, "signoff boundary exposes lab dual-axis")
    hook_literals = re.findall(r'\b(?:id|label):\s*["\']([^"\']+)["\']', suite)
    check(not any(re.search(r"asap7|bspdn", value, re.IGNORECASE) for value in hook_literals), "T15 suite hub has no ASAP7/BSPDN readiness hook")
    check("system_pdn" in suite, "T15 leaves the existing System PDN hook intact")
    check("asap7" not in suite_hub.lower() and "bspdn" not in suite_hub.lower(), "T15 SuiteHub has no ASAP7/BSPDN hook copy")

    results = run_contract_helpers()
    for test_id in ("T5", "T6", "T7", "T8", "T9", "T25"):
        check(results.get(test_id) is True, f"{test_id} semantic contract")

    print("ALL test_studio_i2 PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
