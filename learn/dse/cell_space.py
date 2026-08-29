"""Cell-local transforms from attributed STA/IR paths.

Drive-up is a *cell* level action: named instances on the worst path,
not another ABC sequence and not a chip restart. Hierarchical names
(`dpath/a_lt_b/_142_`) are resolved to the owning module so a leaf
`_07_` in ctrl is not confused with `_07_` in dpath.

Net-local BUF insertion lives in ``net_space`` — a different level.
"""

from __future__ import annotations

import re
from pathlib import Path

_MOD = re.compile(r"^module\s+(\S+?)\s*\(")
_END = re.compile(r"^endmodule\b")
_HEAD = re.compile(
    r"^(\s*)([A-Za-z_][A-Za-z0-9_$]*)\s+(\\[^\s]+|[A-Za-z_][A-Za-z0-9_$]*)\s*\("
)
_DRIVE = re.compile(r"^(?P<stem>.+)_X(?P<n>\d+)$")
_LIBERTY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*_X\d+$")
_SKIP = {
    "module",
    "endmodule",
    "wire",
    "input",
    "output",
    "inout",
    "assign",
    "reg",
    "and",
    "or",
    "not",
    "nand",
    "nor",
    "xor",
    "xnor",
    "buf",
}

DRIVE_NEXT = {1: 2, 2: 4, 4: 8}
_LEF = (
    Path(__file__).resolve().parents[2]
    / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef"
)
_MACRO = re.compile(r"^MACRO\s+(\S+)", re.M)
_LEF_MASTERS: set[str] | None = None


def lef_masters() -> set[str]:
    """OpenROAD place/route masters. Liberty-only sizes are not legal here."""
    global _LEF_MASTERS
    if _LEF_MASTERS is None:
        if _LEF.is_file():
            _LEF_MASTERS = set(_MACRO.findall(_LEF.read_text()))
        else:
            _LEF_MASTERS = set()
    return _LEF_MASTERS


def next_drive(cell_type: str) -> str | None:
    m = _DRIVE.match(str(cell_type))
    if not m:
        return None
    nxt = DRIVE_NEXT.get(int(m.group("n")))
    if nxt is None:
        return None
    name = f"{m.group('stem')}_X{nxt}"
    masters = lef_masters()
    if masters and name not in masters:
        return None
    return name


def inst_eq(a: str, b: str) -> bool:
    """Match ``ctrl`` to Yosys ``\\ctrl`` / ``ctrl``."""
    def n(x: str) -> str:
        return str(x).replace("\\", "").split()[0]

    return n(a) == n(b) and bool(n(a))


def leaf_inst(name: str) -> str:
    n = str(name).replace("\\", "").split()[0]
    if "/" in n:
        n = n.rsplit("/", 1)[-1]
    elif "." in n and not n.startswith("_"):
        n = n.rsplit(".", 1)[-1]
    return n.split("/")[-1]


def parse_modules(text: str) -> list[dict]:
    lines = text.splitlines(keepends=True)
    out: list[dict] = []
    i = 0
    while i < len(lines):
        m = _MOD.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        i += 1
        while i < len(lines) and not _END.match(lines[i]):
            i += 1
        out.append({"name": m.group(1), "start": start, "end": i, "lines": lines})
        i += 1
    return out


def _insts(lines: list[str], start: int, end: int) -> list[tuple[int, str, str, str]]:
    """(line_idx, indent, type, inst) for instantiations in [start, end)."""
    found: list[tuple[int, str, str, str]] = []
    for i in range(start + 1, end):
        h = _HEAD.match(lines[i])
        if not h:
            continue
        typ = h.group(2)
        if typ.lower() in _SKIP:
            continue
        found.append((i, h.group(1), typ, h.group(3).strip()))
    return found


def resolve_instance(text: str, hier: str, *, top: str = "gcd") -> dict | None:
    """Map `dpath/a_lt_b/_142_` to a module-local liberty instance."""
    parts = [p for p in str(hier).replace("\\", "").split()[0].replace(".", "/").split("/") if p]
    if not parts:
        return None
    mods = parse_modules(text)
    by_name = {m["name"]: m for m in mods}
    cur = by_name.get(top) or (mods[-1] if mods else None)
    if cur is None:
        return None
    for part in parts[:-1]:
        hit = None
        for _i, _ind, typ, inst in _insts(cur["lines"], cur["start"], cur["end"]):
            if inst_eq(inst, part):
                hit = typ
                break
        if hit is None or hit not in by_name:
            return None
        cur = by_name[hit]
    leaf = parts[-1]
    for idx, indent, typ, inst in _insts(cur["lines"], cur["start"], cur["end"]):
        if inst_eq(inst, leaf) and _LIBERTY.match(typ):
            return {
                "module": cur["name"],
                "inst": inst,
                "type": typ,
                "line": idx,
                "indent": indent,
                "hier": hier,
            }
    return None


def hier_frames(text: str, hier: str, *, top: str = "gcd") -> list[dict]:
    """Walk ``dpath/a_lt_b/_194_`` from the top module down to the leaf.

    Each frame after the top names the instance in its parent, the module
    type it implements (if any), and the source line of that instantiation.
    """
    raw = str(hier).replace("\\", "").split()[0].replace(".", "/")
    parts = [p for p in raw.split("/") if p]
    if not parts:
        return []
    mods = parse_modules(text)
    by_name = {m["name"]: m for m in mods}
    cur = by_name.get(top) or (mods[-1] if mods else None)
    if cur is None:
        return []
    frames = [
        {
            "role": "top",
            "module": cur["name"],
            "inst": top,
            "type": cur["name"],
            "parent_module": None,
            "line": cur["start"],
            "indent": "",
        }
    ]
    for i, part in enumerate(parts):
        hit = None
        for idx, indent, typ, inst in _insts(cur["lines"], cur["start"], cur["end"]):
            if inst_eq(inst, part):
                hit = (idx, indent, typ, inst)
                break
        if hit is None:
            return []
        idx, indent, typ, inst = hit
        child_mod = typ if typ in by_name else None
        frames.append(
            {
                "role": "cell" if child_mod is None else "inst",
                "module": child_mod,
                "inst": inst,
                "type": typ,
                "parent_module": cur["name"],
                "line": idx,
                "indent": indent,
            }
        )
        if child_mod is None:
            if i != len(parts) - 1:
                return []
            break
        cur = by_name[child_mod]
    return frames


def upsize_path_cells(text: str, cells: list[str], *, top: str = "gcd") -> dict:
    """Rewrite liberty drive on named path instances. Module-scoped."""
    lines = text.splitlines(keepends=True)
    changed: list[dict] = []
    seen_lines: set[int] = set()
    for hier in cells:
        hit = resolve_instance("".join(lines), hier, top=top)
        if hit is None:
            # Flatten-first: unique leaf at top.
            leaf = leaf_inst(hier)
            if leaf != hier:
                hit = resolve_instance("".join(lines), leaf, top=top)
        if hit is None or hit["line"] in seen_lines:
            continue
        nxt = next_drive(hit["type"])
        if not nxt or nxt == hit["type"]:
            continue
        idx = hit["line"]
        old = lines[idx]
        lines[idx] = old.replace(f"{hit['type']} {hit['inst']}", f"{nxt} {hit['inst']}", 1)
        if lines[idx] == old:
            continue
        seen_lines.add(idx)
        changed.append(
            {
                "hier": hit.get("hier") or hier,
                "module": hit["module"],
                "inst": hit["inst"],
                "from": hit["type"],
                "to": nxt,
            }
        )
    return {"text": "".join(lines), "changed": changed, "n_changed": len(changed)}


def upsize_file(path: Path, cells: list[str], dest: Path, *, top: str = "gcd") -> dict:
    raw = Path(path).read_text()
    out = upsize_path_cells(raw, cells, top=top)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out["text"])
    out["src"] = str(path)
    out["dest"] = str(dest)
    return out
