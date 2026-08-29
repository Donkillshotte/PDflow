"""Net-local buffer insertion on attributed STA path hops.

A *net* level action: insert a liberty BUF on the wire between two
named path instances. Not ABC, not a cell drive-up, not a chip restart.
Cross-module hops are skipped (ctrl↔dpath ports stay untouched).
"""

from __future__ import annotations

import re
from pathlib import Path

from .cell_space import leaf_inst, resolve_instance

_PIN = re.compile(r"\.([A-Za-z0-9_$]+)\s*\(\s*([^)]*?)\s*\)")
_OUT = {"Z", "ZN", "Q", "QN", "CO", "S", "Y"}
_CLK = {"CK", "CLK", "CLOCK"}
_SKIP_NET = {"clk", "clock", "reset", "rst"}
BUF_TYPE = "BUF_X2"
MAX_HOPS = 4


def _inst_span(lines: list[str], head: int) -> tuple[int, int]:
    i = head
    while i < len(lines) and ");" not in lines[i]:
        i += 1
    return head, min(i, len(lines) - 1)


def _pins_of(lines: list[str], head: int) -> tuple[dict[str, str], dict[str, int]]:
    lo, hi = _inst_span(lines, head)
    pins: dict[str, str] = {}
    pin_line: dict[str, int] = {}
    for i in range(lo, hi + 1):
        for m in _PIN.finditer(lines[i]):
            pins[m.group(1)] = m.group(2).strip()
            pin_line[m.group(1)] = i
    return pins, pin_line


def _is_dff(cell_type: str | None) -> bool:
    t = str(cell_type or "")
    return t.startswith("DFF") or t.startswith("DLH") or t.startswith("LD")


def _connect_net(src_pins: dict[str, str], dst_pins: dict[str, str]) -> tuple[str, str] | None:
    src_out = {p: n for p, n in src_pins.items() if p in _OUT and n}
    for dp, dn in dst_pins.items():
        if dp in _OUT or dp in _CLK:
            continue
        for _sp, sn in src_out.items():
            if sn == dn and sn.lower() not in _SKIP_NET:
                return dp, sn
    return None


def buffer_path_nets(
    text: str,
    hops: list[str],
    *,
    top: str = "gcd",
    buf: str = BUF_TYPE,
    max_n: int = MAX_HOPS,
    path_types: dict[str, str] | None = None,
) -> dict:
    """Insert ``buf`` on intra-module combo hops ``src->dst``. Module-scoped."""
    lines = text.splitlines(keepends=True)
    changed: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    n_id = 0
    path_types = path_types or {}
    for hop in hops:
        if len(changed) >= int(max_n):
            break
        if "->" not in hop:
            continue
        src, dst = hop.split("->", 1)
        src, dst = src.strip(), dst.strip()
        if _is_dff(path_types.get(src)) or _is_dff(path_types.get(dst)):
            continue
        blob = "".join(lines)
        src_hit = resolve_instance(blob, src, top=top) or resolve_instance(
            blob, leaf_inst(src), top=top
        )
        dst_hit = resolve_instance(blob, dst, top=top) or resolve_instance(
            blob, leaf_inst(dst), top=top
        )
        if not src_hit or not dst_hit:
            continue
        if src_hit["module"] != dst_hit["module"]:
            continue
        if _is_dff(src_hit["type"]) or _is_dff(dst_hit["type"]):
            continue
        src_pins, _ = _pins_of(lines, src_hit["line"])
        dst_pins, dst_pl = _pins_of(lines, dst_hit["line"])
        hit = _connect_net(src_pins, dst_pins)
        if hit is None:
            continue
        dest_pin, net = hit
        key = (dst_hit["module"], dest_pin, net)
        if key in seen:
            continue
        wname = f"netbuf_w{n_id}"
        iname = f"netbuf_{n_id}"
        if any(wname in ln or iname in ln for ln in lines):
            n_id += 1
            continue
        pl = dst_pl.get(dest_pin)
        if pl is None:
            continue
        old = lines[pl]
        new = old.replace(f".{dest_pin}({net})", f".{dest_pin}({wname})", 1)
        if new == old:
            new = old.replace(f".{dest_pin} ({net})", f".{dest_pin}({wname})", 1)
        if new == old:
            continue
        lines[pl] = new
        indent = dst_hit.get("indent") or "  "
        block = [
            f"{indent}wire {wname};\n",
            f"{indent}{buf} {iname} (\n",
            f"{indent}  .A({net}),\n",
            f"{indent}  .Z({wname})\n",
            f"{indent});\n",
        ]
        for j, bl in enumerate(block):
            lines.insert(dst_hit["line"] + j, bl)
        lines = "".join(lines).splitlines(keepends=True)
        seen.add(key)
        changed.append(
            {
                "hop": hop,
                "module": dst_hit["module"],
                "src": src_hit["inst"],
                "dst": dst_hit["inst"],
                "net": net,
                "wire": wname,
                "buf": buf,
                "inst": iname,
            }
        )
        n_id += 1
    return {"text": "".join(lines), "changed": changed, "n_changed": len(changed), "buf": buf}


def buffer_file(
    path: Path,
    hops: list[str],
    dest: Path,
    *,
    top: str = "gcd",
    buf: str = BUF_TYPE,
    max_n: int = MAX_HOPS,
    path_types: dict[str, str] | None = None,
) -> dict:
    raw = Path(path).read_text()
    out = buffer_path_nets(raw, hops, top=top, buf=buf, max_n=max_n, path_types=path_types)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out["text"])
    out["src"] = str(path)
    out["dest"] = str(dest)
    return out
