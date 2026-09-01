"""Architecture plugins vs RTL rewrites.

The GCD e-graph extracts (two's complement sub, or-reduce eqz, borrow lt)
are **rtl_rewrite**, not architecture. A real architecture plugin must
declare I/O contract, latency, and a verification strategy. Binary/Euclid
GCD generators are registered but stay ``finish_ready=False`` until
transactional equiv PASSes — this module does not invent a fake proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .arch_space import EXTRACTS, emit_gcd_variant


@dataclass
class ArchPlugin:
    name: str
    kind: str  # rtl_rewrite | architecture
    latency: str  # same | variable
    verify: str  # yosys_equiv | transactional | unsupported
    generate: Callable[[Path, Path], dict]
    note: str = ""
    compatible_profiles: tuple[str, ...] = ("balanced", "performance", "low_power")

    def emit(self, src: Path, dest: Path) -> dict:
        meta = self.generate(src, dest)
        meta.update(
            {
                "plugin": self.name,
                "kind": self.kind,
                "latency": self.latency,
                "verify": self.verify,
                "finish_ready": False if self.kind == "architecture" else meta.get("finish_ready", False),
            }
        )
        return meta


def _rewrite(name: str) -> Callable[[Path, Path], dict]:
    def _gen(src: Path, dest: Path) -> dict:
        meta = emit_gcd_variant(src, name, dest)
        meta["kind"] = "rtl_rewrite"
        meta["finish_ready"] = False  # still needs equiv + place gate
        return meta

    return _gen


def _identity(src: Path, dest: Path) -> dict:
    dest.write_text(Path(src).read_text())
    return {
        "extract": "gcd_subtractive",
        "kind": "architecture",
        "operator": "identity",
        "note": "current handshake GCD — baseline architecture",
        "finish_ready": False,
    }


def _binary_stub(src: Path, dest: Path) -> dict:
    """Do not emit unverified binary-GCD RTL as a drop-in.

    Writes nothing finish-ready. Callers must treat ``unsupported`` verify
    as R1 fail until a transactional checker exists.
    """
    if dest.exists():
        dest.unlink()
    return {
        "extract": "gcd_binary",
        "kind": "architecture",
        "operator": "binary",
        "note": "binary GCD requires transactional equiv — not a string rewrite of gcd.v",
        "finish_ready": False,
        "verify": "unsupported",
    }


PLUGINS: dict[str, ArchPlugin] = {}


def _register() -> None:
    PLUGINS["gcd_subtractive"] = ArchPlugin(
        name="gcd_subtractive",
        kind="architecture",
        latency="same",
        verify="yosys_equiv",
        generate=_identity,
        note="baseline subtractive GCD",
    )
    for name in EXTRACTS:
        PLUGINS[name] = ArchPlugin(
            name=name,
            kind="rtl_rewrite",
            latency="same",
            verify="yosys_equiv",
            generate=_rewrite(name),
            note=str(EXTRACTS[name].get("note") or name),
        )
    PLUGINS["gcd_binary"] = ArchPlugin(
        name="gcd_binary",
        kind="architecture",
        latency="variable",
        verify="unsupported",
        generate=_binary_stub,
        note="registered, not finish-ready",
    )


_register()


def plugin(name: str) -> ArchPlugin:
    if name not in PLUGINS:
        raise KeyError(f"unknown architecture plugin {name}")
    return PLUGINS[name]


def classify(name: str) -> str:
    return plugin(name).kind
