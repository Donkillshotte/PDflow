"""Run-scoped artifact catalog with finish protection and candidate support."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .contracts import ArtifactRef, atomic_write_json, finish_authority, hash_file


class ArtifactCatalog:
    EXTENSIONS = {
        ".odb",
        ".gds",
        ".oas",
        ".def",
        ".lef",
        ".v",
        ".sv",
        ".spef",
        ".lib",
        ".sdc",
        ".sp",
        ".spi",
        ".cdl",
        ".json",
        ".log",
        ".lyrdb",
        ".vcd",
        ".raw",
        ".prn",
        ".png",
        ".webp",
        ".jpg",
        ".jpeg",
        ".ok",
    }

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self._hash_cache: dict[str, tuple[int, int, str | None]] = {}
        self._revision_path = self.repo_root / ".pdflow" / "agent" / "revisions.json"
        try:
            stored = self._revision_path.read_text(encoding="utf-8")
            raw_revisions = json.loads(stored)
            self._revisions = {
                str(key): int(value)
                for key, value in raw_revisions.items()
                if isinstance(key, str) and isinstance(value, int) and value >= 0
            }
        except (OSError, ValueError, AttributeError):
            self._revisions = {}

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (
            self.repo_root / "tools" / "OpenROAD-flow-scripts" / "flow" / "results",
            self.repo_root / "learn" / "sim" / "reports",
            self.repo_root / "learn" / "sim" / "previews",
            self.repo_root / "learn" / "sim" / "spice",
            self.repo_root / "learn" / "sim" / "pex",
            self.repo_root / ".pdflow" / "generated",
            self.repo_root / ".pdflow" / "runs",
        )

    def _under_allowed_root(self, path: Path) -> bool:
        resolved = path.resolve()
        return any(
            resolved == root.resolve() or root.resolve() in resolved.parents
            for root in self.allowed_roots
        )

    def _iter_files(self):
        for root in self.allowed_roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and not path.name.startswith(".")
                    and path.suffix.lower() in self.EXTENSIONS
                ):
                    yield path

    def _scope(self, relative_path: str) -> str:
        value = relative_path.replace("\\", "/")
        if value.startswith(".pdflow/runs/") and "/candidate/" in value:
            return "package" if "/package/" in value else "flow"
        if "/learn/sim/dse/" in f"/{value}" or value.startswith("learn/sim/dse/"):
            return "lab"
        if value.startswith(".pdflow/generated/"):
            return "generated"
        if "/pkg_" in value or value.startswith("learn/sim/reports/pkg_"):
            return "package"
        if value.startswith("learn/sim/reports/"):
            return "generated"
        if "/results/" in value:
            return "flow"
        return "generated"

    def _variant(self, relative_path: str) -> str:
        parts = relative_path.replace("\\", "/").split("/")
        try:
            idx = parts.index("results")
            if idx + 3 < len(parts):
                return parts[idx + 3]
        except ValueError:
            pass
        if len(parts) >= 3 and parts[0] == ".pdflow" and parts[1] == "generated":
            return parts[2]
        match = re.search(r"_(flowlab|learn|eco_scratch|current)(?:\.[^.]+)?$", Path(relative_path).stem)
        return match.group(1) if match else "current"

    @staticmethod
    def _kind(path: Path) -> str:
        return {
            ".odb": "odb",
            ".gds": "gds",
            ".oas": "oas",
            ".def": "def",
            ".lef": "lef",
            ".v": "verilog",
            ".sv": "verilog",
            ".spef": "spef",
            ".lib": "liberty",
            ".sdc": "sdc",
            ".sp": "spice",
            ".spi": "spice",
            ".cdl": "cdl",
            ".json": "json",
            ".log": "log",
            ".lyrdb": "drc",
            ".vcd": "vcd",
            ".raw": "spice_raw",
            ".prn": "spice_raw",
            ".png": "image",
            ".webp": "image",
            ".jpg": "image",
            ".jpeg": "image",
        }.get(path.suffix.lower(), "file")

    def _hash(self, path: Path, stat: os.stat_result) -> str | None:
        key = str(path)
        previous = self._hash_cache.get(key)
        stamp = (int(stat.st_size), int(stat.st_mtime_ns))
        if previous and previous[:2] == stamp:
            return previous[2]
        digest = hash_file(path)
        self._hash_cache[key] = (stamp[0], stamp[1], digest)
        return digest

    def _ref(self, path: Path) -> ArtifactRef | None:
        try:
            stat = path.stat()
            relative = path.relative_to(self.repo_root).as_posix()
        except (FileNotFoundError, OSError, ValueError):
            return None
        digest = self._hash(path, stat)
        identity = hashlib.sha256(
            f"{relative}:{digest or 'missing'}".encode("utf-8")
        ).hexdigest()
        authority, mutable = finish_authority(relative)
        run_id = None
        parts = relative.split("/")
        if len(parts) >= 3 and parts[0] == ".pdflow" and parts[1] == "runs":
            run_id = parts[2]
        producer = "pdflow" if relative.startswith(".pdflow/") else "orfs"
        return ArtifactRef(
            artifact_id=f"artifact-{identity[:24]}",
            kind=self._kind(path),
            scope=self._scope(relative),
            variant=self._variant(relative),
            relative_path=relative,
            content_hash=digest,
            size=int(stat.st_size),
            mtime_ns=int(stat.st_mtime_ns),
            revision=self._revisions.get(relative, 0),
            producer=producer,
            run_id=run_id,
            authority=authority,
            mutable=mutable,
        )

    def bump_revision(self, relative_path: str) -> int:
        """Increment the saved revision for a path after a real file change."""

        cleaned = relative_path.replace("\\", "/").lstrip("/")
        self._revisions[cleaned] = self._revisions.get(cleaned, 0) + 1
        try:
            atomic_write_json(self._revision_path, self._revisions)
        except OSError:
            pass
        return self._revisions[cleaned]

    def list(
        self,
        limit: int = 200,
        *,
        scope: str | None = None,
        variant: str | None = None,
        authority: str | None = None,
        run_id: str | None = None,
    ) -> list[ArtifactRef]:
        refs = [ref for path in self._iter_files() if (ref := self._ref(path))]
        if scope:
            refs = [ref for ref in refs if ref.scope == scope]
        if variant:
            refs = [ref for ref in refs if ref.variant == variant]
        if authority:
            refs = [ref for ref in refs if ref.authority == authority]
        if run_id:
            refs = [ref for ref in refs if ref.run_id == run_id]
        refs.sort(key=lambda item: item.relative_path)
        return refs[: max(1, min(limit, 2000))]

    def resolve(self, artifact_id: str) -> ArtifactRef | None:
        for ref in self.list(limit=2000):
            if ref.artifact_id == artifact_id:
                return ref
        return None

    def resolve_path(self, relative_path: str) -> ArtifactRef | None:
        cleaned = relative_path.replace("\\", "/").lstrip("/")
        if not cleaned or "\x00" in cleaned or ".." in Path(cleaned).parts:
            return None
        path = (self.repo_root / cleaned).resolve()
        if not self._under_allowed_root(path) or not path.is_file():
            return None
        return self._ref(path)

    def path_for(self, ref: ArtifactRef) -> Path:
        path = (self.repo_root / ref.relative_path).resolve()
        if not self._under_allowed_root(path):
            raise ValueError("artifact path outside allowlist")
        return path

    def snapshot(self) -> dict[str, tuple[int, int, str | None]]:
        result: dict[str, tuple[int, int, str | None]] = {}
        for ref in self.list(limit=2000):
            result[ref.artifact_id] = (ref.size, ref.mtime_ns, ref.content_hash)
        return result

    def create_candidate(self, source: ArtifactRef, run_id: str) -> ArtifactRef:
        if not run_id or not re.fullmatch(r"[A-Za-z0-9_.-]{8,100}", run_id):
            raise ValueError("invalid run_id")
        source_path = self.path_for(source)
        if not source_path.is_file():
            raise FileNotFoundError(source.relative_path)
        relative = source.relative_path.replace("\\", "/")
        parts = relative.split("/")
        try:
            results_index = parts.index("results")
        except ValueError as exc:
            raise ValueError("only results artifacts can be copied to a FlowLab candidate") from exc
        target_dir = (
            self.repo_root
            / ".pdflow"
            / "runs"
            / run_id
            / "candidate"
            / "orfs"
            / Path(*parts[results_index:]).parent
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source_path.name
        if target.exists():
            raise FileExistsError(target)
        # Copy through a hidden temporary file so the watcher never exposes a
        # partially copied ODB/GDS as a candidate artifact.
        temporary = target_dir / f".{source_path.name}.{os.getpid()}.tmp"
        try:
            shutil.copy2(source_path, temporary)
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        ref = self._ref(target)
        if ref is None:
            raise RuntimeError("candidate copy disappeared")
        return ref
