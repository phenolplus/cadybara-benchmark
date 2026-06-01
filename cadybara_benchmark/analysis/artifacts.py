from __future__ import annotations

from pathlib import Path
from typing import Any

from cadybara_benchmark.config import REPO_ROOT


def inspect_artifacts(artifact_paths: list[str]) -> dict[str, Any]:
    files = []
    for raw_path in artifact_paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        exists = path.exists()
        info: dict[str, Any] = {
            "path": raw_path,
            "exists": exists,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size if exists else 0,
        }
        if exists and path.suffix.lower() == ".stl":
            prefix = path.read_bytes()[:80]
            info["stl_format"] = "ascii" if prefix.lstrip().startswith(b"solid") else "binary"
        files.append(info)
    stl_files = [file for file in files if file["extension"] == ".stl"]
    return {
        "files": files,
        "stl_count": len(stl_files),
        "existing_stl_count": len([file for file in stl_files if file["exists"] and file["size_bytes"] > 0]),
    }
