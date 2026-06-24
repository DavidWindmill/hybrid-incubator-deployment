from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def source_key(source: dict[str, Any]) -> str:
    raw = source.get("repository") or source.get("local_path")
    revision = source.get("revision", "main")
    return hashlib.sha256(f"{raw}@{revision}".encode()).hexdigest()[:16]


def resolve_local_source(
    source: dict[str, Any],
    *,
    spec_path: Path,
    workspace: Path,
) -> Path:
    local_path = source.get("local_path")
    if local_path:
        resolved = (spec_path.parent / local_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"No existe el repositorio local: {resolved}")
        return resolved

    repository = source["repository"]
    revision = source.get("revision", "main")
    destination = workspace / "sources" / source_key(source)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--no-checkout", repository, str(destination)])
    run(["git", "-C", str(destination), "fetch", "--depth", "1", "origin", revision])
    run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"])
    return destination


def resolve_cloud_source(
    source: dict[str, Any],
    *,
    workspace: Path,
) -> Path:
    repository = source.get("repository")
    if not repository:
        raise ValueError("El despliegue cloud exige source.repository.")
    revision = source.get("revision", "main")
    destination = workspace / "sources" / source_key(source)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--no-checkout", repository, str(destination)])
    run(["git", "-C", str(destination), "fetch", "--depth", "1", "origin", revision])
    run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"])
    return destination
