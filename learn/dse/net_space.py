"""Net-local buffer insertion on attributed STA path hops.

A *net* level action: insert a liberty BUF on the wire between two
named path instances. Not ABC, not a cell drive-up, not a chip restart.

Intra-module hops stay in ``buffer_path_nets`` (source ``net_buffer``).
Cross-module hops (ctrl↔dpath port nets, or dpath/a_lt_b→dpath/a_mux)
are a different transform: ``buffer_port_nets`` (source ``net_buffer_port``)
inserts the BUF in the parent and retargets the sink instance pin.
"""

from __future__ import annotations

import re
from pathlib import Path

from .cell_space import hier_frames, leaf_inst, parse_modules, resolve_instance

_PIN = re.compile(r"\.([A-Za-z0-9_$]+)\s*\(\s*([^)]*?)\s*\)")
_PORT_DIR = re.compile(
    r"^\s*(input|output|inout)(?:\s+(?:wire|reg))?\s+(?:\[[^\]]+\]\s+)?"
    r"(\\[^\s]+|[A-Za-z_][A-Za-z0-9_$]*)",
    re.M,
)
_ASSIGN = re.compile(r"^\s*assign\s+(\S+)\s*=\s*(\S+)\s*;", re.M)
_OUT = {"Z", "ZN", "Q", "QN", "CO", "S", "Y"}
_OUT_PORT = {"Z", "ZN", "Q", "QN", "CO", "Y"}
_CLK = {"CK", "CLK", "CLOCK"}
_SKIP_NET = {"clk", "clock", "reset", "rst"}
_CONST = re.compile(r"^\d+'b[01xz]+$", re.I)
BUF_TYPE = "BUF_X2"
MAX_HOPS = 4
MAX_PORT_HOPS = 2


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
            f"{indent}  .A({_emit_net(net)}),\n",
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


def hop_is_cross_module(hop: str) -> bool:
    """True when the hop names two different hierarchical owners.

    ``dpath/_07_->dpath/_08_`` is intra-module (same instance prefix).
    ``dpath/a_lt_b/_194_->ctrl/_06_`` and ``dpath/a_lt_b/_142_->dpath/a_mux/_40_``
    cross a module boundary.
    """
    if "->" not in hop:
        return False
    a, b = hop.split("->", 1)
    pa = a.rsplit("/", 1)[0] if "/" in a else ""
    pb = b.rsplit("/", 1)[0] if "/" in b else ""
    return bool(pa and pb and pa != pb)


def _norm_net(name: str) -> str:
    n = str(name or "").strip()
    if n.startswith("\\"):
        n = n[1:].strip()
    return n


def _emit_net(name: str) -> str:
    """Escaped Verilog ids need a terminating space before the next token."""
    n = str(name or "").strip()
    if n.startswith("\\") and not n.endswith(" "):
        return n + " "
    return n


def _skip_net(net: str) -> bool:
    n = _norm_net(net)
    if not n or n.lower() in _SKIP_NET:
        return True
    if _CONST.match(n) or n in {"1'b0", "1'b1"}:
        return True
    if ":" in n or n.startswith("{") or n.startswith('"'):
        return True
    return False


def _mod_blob(mod: dict) -> str:
    lines = mod["lines"]
    return "".join(lines[mod["start"] : mod["end"] + 1])


def _port_names(mod: dict) -> set[str]:
    return {_norm_net(m.group(2)) for m in _PORT_DIR.finditer(_mod_blob(mod))}


def _assign_port(mod: dict, net: str) -> str | None:
    ports = _port_names(mod)
    want = _norm_net(net)
    if want in ports:
        return net
    for m in _ASSIGN.finditer(_mod_blob(mod)):
        left, right = m.group(1), m.group(2).rstrip(",")
        if _norm_net(right) == want and _norm_net(left) in ports:
            return left
        if _norm_net(left) == want and _norm_net(right) in ports:
            return right
    return None


def _pin_lookup(pins: dict[str, str], port: str) -> tuple[str, str] | None:
    want = _norm_net(port)
    for p, n in pins.items():
        if _norm_net(p) == want:
            return p, n
    return None


def _retarget_pin(line: str, pin: str, old_net: str, new_net: str) -> str:
    def repl(m: re.Match) -> str:
        if _norm_net(m.group(1)) == _norm_net(old_net):
            return f".{pin}({new_net})"
        return m.group(0)

    new, n = re.subn(rf"\.{re.escape(pin)}\s*\(\s*([^)]*?)\s*\)", repl, line, count=1)
    return new if n else line


def _escape_chain(text: str, hier: str, start_net: str, *, top: str = "gcd") -> list[dict]:
    """Walk ``start_net`` upward through ports. Each step is a parent connection."""
    frames = hier_frames(text, hier, top=top)
    if len(frames) < 2:
        return []
    mods = {m["name"]: m for m in parse_modules(text)}
    lines = text.splitlines(keepends=True)
    net = start_net
    chain: list[dict] = []
    # frames[0] is the top module; frames[1:] are instances / the leaf cell.
    # The net lives in the parent of the leaf (or of the current frame).
    i = len(frames) - 1
    if frames[i].get("role") == "cell":
        i -= 1
    while i >= 1:
        inst = frames[i]
        child_mod_name = inst.get("module")
        parent_name = inst.get("parent_module")
        if not child_mod_name or not parent_name or child_mod_name not in mods:
            break
        port = _assign_port(mods[child_mod_name], net)
        if port is None:
            break
        pins, _ = _pins_of(lines, inst["line"])
        hit = _pin_lookup(pins, port)
        if hit is None:
            break
        pin_name, parent_net = hit
        if _skip_net(parent_net):
            break
        chain.append(
            {
                "parent_module": parent_name,
                "parent_net": parent_net,
                "child_inst": inst["inst"],
                "child_port": pin_name,
                "inst_line": inst["line"],
                "indent": inst.get("indent") or "  ",
                "kind": "port",
            }
        )
        net = parent_net
        i -= 1
    return chain


def find_port_crossing(
    text: str,
    src: str,
    dst: str,
    *,
    top: str = "gcd",
    path_types: dict[str, str] | None = None,
) -> dict | None:
    """Parent-module net that electrically joins a cross-module hop."""
    path_types = path_types or {}
    if _is_dff(path_types.get(src)) or _is_dff(path_types.get(dst)):
        return None
    src_hit = resolve_instance(text, src, top=top) or resolve_instance(text, leaf_inst(src), top=top)
    dst_hit = resolve_instance(text, dst, top=top) or resolve_instance(text, leaf_inst(dst), top=top)
    if not src_hit or not dst_hit:
        return None
    if src_hit["module"] == dst_hit["module"]:
        return None
    if _is_dff(src_hit["type"]) or _is_dff(dst_hit["type"]):
        return None
    lines = text.splitlines(keepends=True)
    src_pins, _ = _pins_of(lines, src_hit["line"])
    dst_pins, _ = _pins_of(lines, dst_hit["line"])
    src_outs = [n for p, n in src_pins.items() if p in _OUT_PORT and n and not _skip_net(n)]
    dst_ins = [
        (p, n)
        for p, n in dst_pins.items()
        if p not in _OUT_PORT and p not in _CLK and n and not _skip_net(n)
    ]
    src_levels: list[dict] = []
    for n in src_outs:
        src_levels.extend(_escape_chain(text, src, n, top=top))
        src_levels.append(
            {
                "parent_module": src_hit["module"],
                "parent_net": n,
                "child_inst": src_hit["inst"],
                "child_port": next((p for p, q in src_pins.items() if q == n), ""),
                "inst_line": src_hit["line"],
                "indent": src_hit.get("indent") or "  ",
                "kind": "local",
            }
        )
    matches: list[dict] = []
    for dp, dn in dst_ins:
        dst_levels = list(_escape_chain(text, dst, dn, top=top))
        dst_levels.append(
            {
                "parent_module": dst_hit["module"],
                "parent_net": dn,
                "child_inst": dst_hit["inst"],
                "child_port": dp,
                "inst_line": dst_hit["line"],
                "indent": dst_hit.get("indent") or "  ",
                "kind": "local",
            }
        )
        for sl in src_levels:
            for dl in dst_levels:
                if sl.get("kind") == "local" and dl.get("kind") == "local":
                    continue
                if sl["parent_module"] != dl["parent_module"]:
                    continue
                if _norm_net(sl["parent_net"]) != _norm_net(dl["parent_net"]):
                    continue
                matches.append(dl)
    if not matches:
        return None

    def score(m: dict) -> tuple[int, int]:
        topish = 0 if m["parent_module"] == top else 1
        kind = 0 if m.get("kind") == "port" else 1
        return (topish, kind)

    matches.sort(key=score)
    hit = matches[0]
    return {
        "parent_module": hit["parent_module"],
        "net": hit["parent_net"],
        "dst_inst": hit["child_inst"],
        "dst_port": hit["child_port"],
        "inst_line": hit["inst_line"],
        "indent": hit.get("indent") or "  ",
        "kind": hit.get("kind") or "port",
        "src": src_hit["inst"],
        "dst": dst_hit["inst"],
        "src_module": src_hit["module"],
        "dst_module": dst_hit["module"],
    }


def buffer_port_nets(
    text: str,
    hops: list[str],
    *,
    top: str = "gcd",
    buf: str = BUF_TYPE,
    max_n: int = MAX_PORT_HOPS,
    path_types: dict[str, str] | None = None,
) -> dict:
    """Insert ``buf`` on cross-module port nets. Parent-scoped, not intra-module."""
    lines = text.splitlines(keepends=True)
    changed: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    n_id = 0
    path_types = path_types or {}
    for hop in hops:
        if len(changed) >= int(max_n):
            break
        if not hop_is_cross_module(hop):
            continue
        src, dst = hop.split("->", 1)
        src, dst = src.strip(), dst.strip()
        blob = "".join(lines)
        cross = find_port_crossing(blob, src, dst, top=top, path_types=path_types)
        if cross is None:
            continue
        key = (cross["parent_module"], cross["dst_inst"], cross["dst_port"], _norm_net(cross["net"]))
        if key in seen:
            continue
        wname = f"portbuf_w{n_id}"
        iname = f"portbuf_{n_id}"
        if any(wname in ln or iname in ln for ln in lines):
            n_id += 1
            continue
        pl = None
        pins, pin_line = _pins_of(lines, cross["inst_line"])
        hit = _pin_lookup(pins, cross["dst_port"])
        if hit is None:
            continue
        dest_pin, net = hit
        if _norm_net(net) != _norm_net(cross["net"]):
            continue
        pl = pin_line.get(dest_pin)
        if pl is None:
            continue
        old = lines[pl]
        new = _retarget_pin(old, dest_pin, net, wname)
        if new == old:
            continue
        lines[pl] = new
        indent = cross.get("indent") or "  "
        block = [
            f"{indent}wire {wname};\n",
            f"{indent}{buf} {iname} (\n",
            f"{indent}  .A({_emit_net(net)}),\n",
            f"{indent}  .Z({wname})\n",
            f"{indent});\n",
        ]
        at = int(cross["inst_line"])
        for j, bl in enumerate(block):
            lines.insert(at + j, bl)
        lines = "".join(lines).splitlines(keepends=True)
        seen.add(key)
        changed.append(
            {
                "hop": hop,
                "module": cross["parent_module"],
                "src": cross["src"],
                "dst": cross["dst"],
                "src_module": cross["src_module"],
                "dst_module": cross["dst_module"],
                "net": net,
                "wire": wname,
                "buf": buf,
                "inst": iname,
                "dst_inst": cross["dst_inst"],
                "dst_port": dest_pin,
                "scope": "port",
            }
        )
        n_id += 1
    return {
        "text": "".join(lines),
        "changed": changed,
        "n_changed": len(changed),
        "buf": buf,
        "scope": "port",
    }


def buffer_file(
    path: Path,
    hops: list[str],
    dest: Path,
    *,
    top: str = "gcd",
    buf: str = BUF_TYPE,
    max_n: int = MAX_HOPS,
    path_types: dict[str, str] | None = None,
    scope: str = "module",
) -> dict:
    raw = Path(path).read_text()
    if scope == "port":
        out = buffer_port_nets(raw, hops, top=top, buf=buf, max_n=max_n, path_types=path_types)
    else:
        out = buffer_path_nets(raw, hops, top=top, buf=buf, max_n=max_n, path_types=path_types)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out["text"])
    out["src"] = str(path)
    out["dest"] = str(dest)
    return out


def buffer_port_file(
    path: Path,
    hops: list[str],
    dest: Path,
    *,
    top: str = "gcd",
    buf: str = BUF_TYPE,
    max_n: int = MAX_PORT_HOPS,
    path_types: dict[str, str] | None = None,
) -> dict:
    return buffer_file(
        path, hops, dest, top=top, buf=buf, max_n=max_n, path_types=path_types, scope="port"
    )
