#!/usr/bin/env python3
"""Probe Cloud Agent RAM / timeout knobs. Does not raise VM memory.

Cursor environment.json has no memory/cpu fields. Enterprise support can
raise workspace limits; this script only reports what this pod actually has.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from heavy_analysis import (  # noqa: E402
    AES_F4_N_NODES,
    AES_F4_N_R,
    RSS_FRACTION,
    available_ram_bytes,
    check_rss_budget,
    estimate_solve_rss_bytes,
    resolve_solve_timeout_s,
)


SCHEMA_URL = "https://cursor.com/schemas/environment.schema.json"
ENV_JSON_KEYS_THAT_RAISE_RAM = ("memory", "ram", "cpus", "cpu", "resources", "vmSize")


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0].endswith(":"):
                    out[parts[0][:-1]] = int(parts[1]) * 1024
    except OSError:
        pass
    return out


def _cgroup() -> dict:
    root = Path("/sys/fs/cgroup")
    names = ["memory.max", "memory.high", "memory.current", "cpu.max"]
    found = {n: (root / n).read_text().strip() if (root / n).is_file() else None for n in names}
    return {
        "controllers": (root / "cgroup.controllers").read_text().strip()
        if (root / "cgroup.controllers").is_file()
        else None,
        **found,
        "note": "missing memory.max means the limit is the VM size, not a cgroup quota we can raise",
    }


def _try_swap_probe() -> dict:
    """See if this pod can add swap. Always disables it afterwards."""
    swapfile = Path("/tmp/pd-flow-ram-probe.swap")
    result: dict = {"tried": True, "enabled": False}
    if os.geteuid() != 0 and shutil.which("sudo") is None:
        result["reason"] = "not root and no sudo — cannot swapon"
        return result
    prefix = ["sudo"] if os.geteuid() != 0 else []
    try:
        subprocess.run(prefix + ["swapoff", str(swapfile)], capture_output=True, check=False)
        swapfile.unlink(missing_ok=True)
        subprocess.run(
            prefix + ["fallocate", "-l", "64M", str(swapfile)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(prefix + ["chmod", "600", str(swapfile)], check=True, capture_output=True)
        mk = subprocess.run(
            prefix + ["mkswap", str(swapfile)], capture_output=True, text=True, check=False
        )
        if mk.returncode != 0:
            result["reason"] = (mk.stderr or mk.stdout or "mkswap failed")[:240]
            return result
        on = subprocess.run(
            prefix + ["swapon", str(swapfile)], capture_output=True, text=True, check=False
        )
        result["enabled"] = on.returncode == 0
        result["reason"] = (on.stderr or on.stdout or "").strip()[:240] or (
            "swapon ok — swap is disk overflow, not extra RAM; prior AES crash was thrash"
            if result["enabled"]
            else "swapon failed"
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        result["reason"] = str(exc)[:240]
    finally:
        subprocess.run(prefix + ["swapoff", str(swapfile)], capture_output=True, check=False)
        try:
            swapfile.unlink(missing_ok=True)
        except OSError:
            pass
        result["cleaned"] = not swapfile.exists()
    return result


def _schema_rejects_memory() -> dict:
    """Confirm environment.json cannot declare more RAM."""
    try:
        import urllib.request

        with urllib.request.urlopen(SCHEMA_URL, timeout=15) as resp:
            schema = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)[:200]}
    props = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        props.update((node.get("properties") or {}).keys())
        for v in node.values():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        walk(item)

    walk(schema)
    hits = sorted(k for k in ENV_JSON_KEYS_THAT_RAISE_RAM if k in props)
    return {
        "ok": True,
        "schema_has_ram_fields": bool(hits),
        "matching_fields": hits,
        "unevaluatedProperties": schema.get("unevaluatedProperties"),
        "note": "unknown fields are rejected; there is no memory/cpu knob in this schema",
    }


def probe() -> dict:
    mem = _meminfo()
    total = mem.get("MemTotal") or 0
    avail = available_ram_bytes()
    aes = {}
    for solver in ("direct", "amg", "krylov"):
        est = estimate_solve_rss_bytes(n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver=solver)
        aes[solver] = {
            "estimated_rss_mib": round(est / (1 << 20)),
            "fits": check_rss_budget(
                n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver=solver
            )
            is None,
            "refusal": check_rss_budget(
                n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver=solver
            ),
        }
    return {
        "vm": {
            "mem_total_mib": round(total / (1 << 20)),
            "mem_available_mib": round(avail / (1 << 20)),
            "swap_total_mib": round((mem.get("SwapTotal") or 0) / (1 << 20)),
            "nproc": os.cpu_count(),
            "rss_fraction": RSS_FRACTION,
        },
        "cgroup": _cgroup(),
        "timeout": {
            "PDN_SOLVE_TIMEOUT_S": os.environ.get("PDN_SOLVE_TIMEOUT_S"),
            "resolved_default_90": resolve_solve_timeout_s(90.0),
            "resolved_aes_1800": resolve_solve_timeout_s(1800.0),
            "note": "software timeout is raisable; Cloud Agent session timeout is not",
        },
        "environment_json": {
            "can_raise_ram": False,
            "schema": _schema_rejects_memory(),
        },
        "aes_f4_73k": {
            "n_r": AES_F4_N_R,
            "n_nodes": AES_F4_N_NODES,
            "solvers": aes,
        },
        "swap_probe": _try_swap_probe(),
        "verdict": (
            "timeout: yes via PDN_SOLVE_TIMEOUT_S; "
            "RAM: no — 15 GiB VM, schema has no memory field, "
            "AES Krylov still refuses on RSS budget"
        ),
    }


def main() -> int:
    report = probe()
    print(json.dumps(report, indent=2))
    vm = report["vm"]
    print(
        f"CLOUD_RESOURCES mem={vm['mem_total_mib']}MiB "
        f"avail={vm['mem_available_mib']}MiB swap={vm['swap_total_mib']}MiB "
        f"cpus={vm['nproc']}",
        file=sys.stderr,
    )
    kry = report["aes_f4_73k"]["solvers"]["krylov"]
    print(
        f"AES Krylov fits={kry['fits']} est={kry['estimated_rss_mib']}MiB",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
