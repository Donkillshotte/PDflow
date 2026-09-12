#!/usr/bin/env python3
"""Agent-owned native inspection for the Studio stage inspector.

The local agent supplies every path and scalar after validating the request.
This adapter invokes only the native binaries inherited from that agent and
writes one bounded JSON result to the agent-provided output path. It never
touches canonical ORFS results.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


STAGES: dict[str, dict[str, str | None]] = {
    "synth": {"odb": "1_synth.odb", "netlist": "1_2_yosys.v"},
    "floorplan": {"odb": "2_floorplan.odb", "netlist": "1_2_yosys.v"},
    "pdn": {"odb": "2_4_floorplan_pdn.odb", "netlist": "1_2_yosys.v"},
    "place": {"odb": "3_place.odb", "netlist": "1_2_yosys.v"},
    "cts": {"odb": "4_cts.odb", "netlist": None},
    "route": {"odb": "5_route.odb", "netlist": None},
    "finish": {"odb": "6_final.odb", "netlist": "6_final.v"},
}

LAB_VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")


def fail(message: str, status: str = "FAIL", code: int = 1) -> int:
    result = {
        "schema_version": 1,
        "kind": "inspect_stage",
        "status": status,
        "ok": False,
        "reason": message,
        "stage": os.environ.get("PD_FLOW_INSPECT_STAGE", ""),
        "variant": os.environ.get("PD_FLOW_INSPECT_VARIANT", ""),
    }
    write_result(result)
    print(f"INSPECT_{status} {message}", file=sys.stderr)
    return code


def output_path() -> Path:
    raw = os.environ.get("PD_FLOW_INSPECT_OUTPUT", "")
    if not raw:
        raise RuntimeError("PD_FLOW_INSPECT_OUTPUT is required")
    return Path(raw).resolve()


def write_result(result: dict[str, Any]) -> None:
    target = output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def run_native(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    stdin: str | None = None,
    timeout: int,
) -> tuple[int, str, str, bool]:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [executable, *args],
            cwd=str(cwd),
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=os.environ.copy(),
        )
        stdout, stderr = process.communicate(input=stdin, timeout=timeout)
        return process.returncode, stdout or "", stderr or "", False
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.SubprocessError:
                stdout, stderr = exc.output or "", exc.stderr or ""
        else:
            stdout, stderr = "", ""
        return 124, stdout or "", stderr or "", True
    except OSError as exc:
        return 127, "", str(exc), False


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def input_ref(path: Path, repo_root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "relative_path": path.relative_to(repo_root).as_posix(),
        "content_hash": digest(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def inspect_odb(path: Path, flow: Path) -> tuple[dict[str, Any] | None, str | None]:
    tcl = f"""
read_db {{{path}}}
set block [ord::get_db_block]
puts "DESIGN [$block getName]"
puts "INSTS [llength [$block getInsts]]"
puts "NETS [llength [$block getNets]]"
set die [$block getDieArea]
puts "DIE [$die dx] [$die dy]"
"""
    code, stdout, stderr, timed_out = run_native(
        "openroad",
        ["-no_init", "-no_splash", "-exit"],
        cwd=flow,
        stdin=tcl,
        timeout=90,
    )
    output = f"{stdout}\n{stderr}"
    if timed_out:
        return None, "OpenROAD inspection timed out"
    if code != 0:
        return None, f"OpenROAD inspection failed with exit code {code}"
    design = next((line.split(None, 1)[1] for line in output.splitlines() if line.startswith("DESIGN ")), None)
    insts = next((line.split(None, 1)[1] for line in output.splitlines() if line.startswith("INSTS ")), None)
    nets = next((line.split(None, 1)[1] for line in output.splitlines() if line.startswith("NETS ")), None)
    die = next((line.split(None, 1)[1].split() for line in output.splitlines() if line.startswith("DIE ")), None)
    if not design or insts is None:
        return None, "OpenROAD returned no valid ODB statistics"
    try:
        die_values = [int(value) for value in (die or ["0", "0"])]
        return {
            "design": design,
            "instances": int(insts),
            "nets": int(nets or 0),
            "dieDbu": {"dx": die_values[0], "dy": die_values[1]},
            "artifact": path.name,
        }, None
    except (ValueError, IndexError):
        return None, "OpenROAD returned malformed ODB statistics"


def inspect_sta(
    verilog: Path,
    spef: Path | None,
    flow: Path,
    label: str,
    liberty: Path | list[Path],
    sdc: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    liberty_files = [liberty] if isinstance(liberty, Path) else liberty
    with tempfile.TemporaryDirectory(prefix="pdflow-inspect-sta-") as temp_dir:
        checks = Path(temp_dir) / "checks.json"
        spef_line = f"read_spef {{{spef}}}" if spef and spef.is_file() else ""
        liberty_lines = "\n".join(
            f"read_liberty {{{item}}}" for item in liberty_files
        )
        script = f"""
{liberty_lines}
read_verilog {{{verilog}}}
link_design gcd
read_sdc {{{sdc}}}
{spef_line}
report_wns
report_tns
report_worst_slack -max
report_checks -format end -group_path_count 5
report_checks -format json -group_path_count 3 > {{{checks}}}
"""
        code, stdout, stderr, timed_out = run_native(
            "sta",
            ["-no_init", "-exit"],
            cwd=flow,
            stdin=script,
            timeout=120,
        )
        output = f"{stdout}\n{stderr}"
        if timed_out:
            return None, "OpenSTA inspection timed out"
        if code != 0:
            return None, f"OpenSTA inspection failed with exit code {code}"
        paths: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[-1].strip("()") in {"MET", "VIOLATED"}:
                paths.append({"endpoint": parts[0], "slack": parts[-2], "status": parts[-1].strip("()")})
        json_paths: int | None = None
        try:
            raw = json.loads(checks.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("checks"), list):
                json_paths = len(raw["checks"])
        except (OSError, json.JSONDecodeError):
            pass
        def metric(pattern: str) -> str | None:
            for line in output.splitlines():
                if line.lower().startswith(pattern.lower()):
                    return line.split()[-1]
            return None
        return {
            "source": label,
            "wns": metric("wns max"),
            "tns": metric("tns max"),
            "worstSlack": metric("worst slack max"),
            "paths": paths[:5],
            "jsonPaths": json_paths,
        }, None


def inspect_yosys(verilog: Path) -> tuple[dict[str, Any] | None, str | None]:
    yosys_path = str(verilog).replace("\\", "\\\\").replace(" ", "\\ ")
    code, stdout, stderr, timed_out = run_native(
        "yosys",
        ["-Q", "-p", f"read_verilog {yosys_path}; hierarchy -top gcd; stat"],
        cwd=verilog.parent,
        timeout=90,
    )
    output = f"{stdout}\n{stderr}"
    if timed_out:
        return None, "Yosys inspection timed out"
    if code != 0:
        return None, f"Yosys inspection failed with exit code {code}"
    hits = [
        line.strip()[:160]
        for line in output.splitlines()
        if any(token.lower() in line.lower() for token in ("Number of cells", "Chip area", "DFF_X1", "NAND2_X1", "AND2_X1"))
        or line.strip().endswith("cells")
    ]
    cells = re.search(r"Number of cells:\s*(\d+)", output, re.IGNORECASE)
    if cells is None:
        cells = re.search(r"^\s*(\d+)\s+cells\s*$", output, re.MULTILINE)
    area = re.search(r"Chip area[^:]*:\s*([\d.]+)", output, re.IGNORECASE)
    dff = re.search(r"^\s*(\d+)\s+DFF_X1\s*$", output, re.MULTILINE)
    return {
        "cells": cells.group(1) if cells else None,
        "area": area.group(1) if area else None,
        "dff": dff.group(1) if dff else None,
        "rawHits": hits[:12],
    }, None


def main() -> int:
    stage = os.environ.get("PD_FLOW_INSPECT_STAGE", "")
    variant = os.environ.get("PD_FLOW_INSPECT_VARIANT", "")
    root_raw = os.environ.get("PD_FLOW_INSPECT_ROOT", "")
    repo_raw = os.environ.get("PD_FLOW_INSPECT_REPO_ROOT", "")
    if stage not in STAGES:
        return fail(f"invalid inspection stage: {stage}", "GAP", 78)
    if variant not in {"flowlab", "learn", "eco_scratch"} and not LAB_VARIANT_RE.fullmatch(variant):
        return fail(f"invalid inspection variant: {variant}", "GAP", 78)
    if not root_raw or not repo_raw:
        return fail("inspection roots are missing", "GAP", 78)
    root = Path(root_raw).resolve()
    repo_root = Path(repo_raw).resolve()
    flow = repo_root / "tools" / "OpenROAD-flow-scripts" / "flow"
    try:
        root.relative_to(repo_root)
    except ValueError:
        return fail("inspection root escaped repository", "GAP", 78)
    if not flow.is_dir():
        return fail("ORFS flow tree is missing", "GAP", 78)
    odb_path = root / str(STAGES[stage]["odb"])
    if not odb_path.is_file():
        return fail(f"missing ODB artifact: {odb_path.name}", "GAP", 78)

    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": "inspect_stage",
        "status": "PASS",
        "ok": True,
        "stage": stage,
        "variant": variant,
        "odb": None,
        "sta": None,
        "yosys": None,
        "hooks": [],
        "inputs": [],
    }
    result["inputs"].append(input_ref(odb_path, repo_root))
    odb, error = inspect_odb(odb_path, flow)
    if error:
        return fail(error)
    result["odb"] = odb

    netlist_name = STAGES[stage]["netlist"]
    netlist = root / str(netlist_name) if netlist_name else None
    if LAB_VARIANT_RE.fullmatch(variant):
        # The ASAP7 timing view is assembled from the same five native
        # liberty families used by the ORFS platform. A single AO file is not
        # a valid substitute for the sequential and inverter cells in 6_final.
        corner = "SS" if "_wc_" in variant else "FF" if "_bc_" in variant else "TT"
        vt = next(
            (name for name in ("SLVT", "LVT", "RVT", "SRAM") if f"_{name.lower()}_" in variant),
            "RVT",
        )
        lib_dir = flow / "platforms/asap7/lib/NLDM"
        liberty_files = []
        for family in ("AO", "INVBUF", "OA", "SEQ", "SIMPLE"):
            matches = sorted(
                item
                for item in lib_dir.glob(
                    f"asap7sc7p5t_{family}_{vt}_{corner}_nldm*"
                )
                if item.is_file() and not item.name.endswith("_FAKE.lib")
            )
            if matches:
                liberty_files.append(matches[0])
        liberty: Path | list[Path] = liberty_files
        sdc = root / "6_final.sdc"
        if not sdc.is_file():
            sdc = flow / "platforms/asap7/constraints.sdc"
    else:
        liberty = flow / "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
        sdc = flow / "designs/nangate45/gcd-tutorial/constraint.sdc"
    spef = root / "6_final.spef" if stage == "finish" else None
    if netlist and netlist.is_file():
        result["inputs"].append(input_ref(netlist, repo_root))
        liberty_ready = (
            bool(liberty)
            if isinstance(liberty, list)
            else liberty.is_file()
        )
        if liberty_ready and sdc.is_file():
            sta, error = inspect_sta(
                netlist,
                spef if spef and spef.is_file() else None,
                flow,
                f"OpenSTA · {netlist.name}{' + SPEF' if spef and spef.is_file() else ' (ideal / no parasitics)'}",
                liberty,
                sdc,
            )
            if error:
                return fail(error)
            result["sta"] = sta
            if spef and spef.is_file():
                result["inputs"].append(input_ref(spef, repo_root))
        else:
            return fail("OpenSTA liberty or SDC input is missing", "GAP", 78)
        if stage in {"synth", "floorplan"}:
            yosys, error = inspect_yosys(netlist)
            if error:
                return fail(error)
            result["yosys"] = yosys

    result["hooks"] = [
        {"id": "or-web", "label": "OpenROAD -web", "detail": "Agent-owned OpenROAD web viewer"},
        {"id": "or-gui", "label": "OpenROAD -gui", "detail": "Native desktop session via the local agent"},
        {"id": "or-odb", "label": "OpenROAD ODB inspection", "detail": "Native Tcl database statistics"},
        {"id": "sta", "label": "OpenSTA checks", "detail": "Native timing summary and structured checks"},
        {"id": "yosys", "label": "Yosys stat", "detail": "Native synthesis statistics"},
    ]
    write_result(result)
    print(f"INSPECT_PASS stage={stage} variant={variant} odb={odb_path.name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            raise SystemExit(fail(str(exc)))
        except Exception:
            print(f"INSPECT_FAIL {exc}", file=sys.stderr)
            raise SystemExit(1)
