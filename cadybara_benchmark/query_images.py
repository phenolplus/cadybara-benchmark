from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings

_MEDIA_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_EXTENSION_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def experiment_images_dir(experiment_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workspace_dir / "experiments" / experiment_id / "images"


def save_query_images(
    experiment_id: str,
    query_id: str,
    images: list[dict[str, Any]],
    settings: Settings | None = None,
) -> list[dict[str, str]]:
    if not images:
        return []

    directory = experiment_images_dir(experiment_id, settings)
    directory.mkdir(parents=True, exist_ok=True)
    stored: list[dict[str, str]] = []
    for index, image in enumerate(images):
        media_type = str(image.get("media_type") or "").strip()
        data = image.get("data")
        if not media_type or not isinstance(data, str) or not data.strip():
            raise ValueError("Each query image requires media_type and base64 data.")
        extension = _MEDIA_TYPE_EXTENSIONS.get(media_type)
        if extension is None:
            raise ValueError(f"Unsupported image media type: {media_type}")
        path = directory / f"{query_id}-{index}{extension}"
        path.write_bytes(base64.b64decode(data))
        stored.append({"path": _stored_path(path), "media_type": media_type})
    return stored


def save_query_image_files(
    experiment_id: str,
    query_id: str,
    image_paths: list[Path],
    settings: Settings | None = None,
) -> list[dict[str, str]]:
    if not image_paths:
        return []

    directory = experiment_images_dir(experiment_id, settings)
    directory.mkdir(parents=True, exist_ok=True)
    stored: list[dict[str, str]] = []
    for index, source in enumerate(image_paths):
        source = source.expanduser().resolve()
        if not source.exists():
            raise ValueError(f"Image file not found: {source}")
        media_type = media_type_for_path(source)
        extension = _MEDIA_TYPE_EXTENSIONS.get(media_type, source.suffix.lower())
        path = directory / f"{query_id}-{index}{extension}"
        path.write_bytes(source.read_bytes())
        stored.append({"path": _stored_path(path), "media_type": media_type})
    return stored


def load_api_images(stored_images: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    api_images: list[dict[str, str]] = []
    for image in stored_images or []:
        path_value = image.get("path")
        media_type = image.get("media_type")
        if not path_value or not media_type:
            continue
        path = _resolve_path(str(path_value))
        if not path.exists():
            raise ValueError(f"Query image not found: {path_value}")
        api_images.append(
            {
                "media_type": str(media_type),
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return api_images


def resolve_query_image_path(
    experiment_id: str,
    query_id: str,
    index: int,
    stored_images: list[dict[str, Any]] | None,
) -> Path:
    if index < 0:
        raise ValueError("Image index must be non-negative.")
    images = stored_images or []
    if index >= len(images):
        raise ValueError(f"Query {query_id} has no image at index {index}.")
    path_value = images[index].get("path")
    if not path_value:
        raise ValueError(f"Query {query_id} image {index} is missing a path.")
    path = _resolve_path(str(path_value))
    _ensure_experiment_image_path(experiment_id, path)
    if not path.exists():
        raise ValueError(f"Query image not found: {path_value}")
    return path


def media_type_for_path(path: Path) -> str:
    media_type = _EXTENSION_MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(f"Unsupported image file type: {path.suffix or '(none)'}")
    return media_type


def query_image_api_entries(
    experiment_id: str,
    query_id: str,
    stored_images: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    return [
        {
            "media_type": str(image.get("media_type") or ""),
            "url": f"/api/experiments/{experiment_id}/queries/{query_id}/images/{index}",
        }
        for index, image in enumerate(stored_images or [])
        if image.get("path") and image.get("media_type")
    ]


def _ensure_experiment_image_path(experiment_id: str, path: Path) -> None:
    settings = get_settings()
    images_root = (settings.workspace_dir / "experiments" / experiment_id / "images").resolve()
    resolved = path.resolve()
    if resolved != images_root and images_root not in resolved.parents:
        raise ValueError("Query image path is outside the experiment images directory.")


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate


def _stored_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
