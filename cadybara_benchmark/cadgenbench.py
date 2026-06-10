from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.experiment_files import save_experiment
from cadybara_benchmark.services.experiments import create_experiment, default_setup, get_experiment
from cadybara_benchmark.query_images import media_type_for_path
from cadybara_benchmark.time import utc_now


CadGenBenchSeries = Literal["100", "200"]

_SERIES_RANGES: dict[CadGenBenchSeries, range] = {
    "100": range(100, 200),
    "200": range(200, 300),
}

_RENDER_ORDER = ["iso", "front", "right", "top"]
_EDIT_PROMPT_TEMPLATE = (
    "The attached images shows several angles of a device. Implement this device. "
    "Then, perform the following operation(s): {operation}"
)


@dataclass(frozen=True)
class CadGenBenchQuery:
    folder_id: int
    series: CadGenBenchSeries
    text: str
    image_paths: list[Path]


def create_cadgenbench_experiment(
    data_dir: Path,
    series: list[CadGenBenchSeries],
    folder_ids: list[int] | None = None,
    name: str | None = None,
    description: str = "",
    category: str = "",
    model: str | None = None,
    response_mode: str | None = None,
    return_format: str | None = None,
    linear_deflection: float | None = None,
    angular_deflection: float | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    selected_series = _normalize_series(series)
    queries = collect_cadgenbench_queries(data_dir, selected_series, folder_ids)
    setup = _build_setup(
        settings,
        model=model,
        response_mode=response_mode,
        return_format=return_format,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )
    experiment = create_experiment(
        name or _default_experiment_name(selected_series),
        description or _default_experiment_description(selected_series, folder_ids),
        setup=setup,
        settings=settings,
    )
    experiment["queries"] = [
        _stored_query(query, category)
        for query in queries
    ]
    experiment["updated_at"] = utc_now()
    save_experiment(experiment, settings)
    return get_experiment(experiment["id"], settings)


def collect_cadgenbench_queries(
    data_dir: Path,
    series: list[CadGenBenchSeries],
    folder_ids: list[int] | None = None,
) -> list[CadGenBenchQuery]:
    data_dir = data_dir.expanduser().resolve()
    if not data_dir.exists():
        raise ValueError(f"CadGenBench data directory not found: {data_dir}")
    selected_series = _normalize_series(series)
    selected_folders = _select_folders(data_dir, selected_series, folder_ids)
    queries = [_load_query(folder) for folder in selected_folders]
    if not queries:
        raise ValueError("No CadGenBench folders matched the requested filters.")
    return queries


def _load_query(folder: Path) -> CadGenBenchQuery:
    folder_id = int(folder.name)
    series = _series_for_folder_id(folder_id)
    if series == "100":
        return _load_100_query(folder, folder_id)
    return _load_200_query(folder, folder_id)


def _load_100_query(folder: Path, folder_id: int) -> CadGenBenchQuery:
    description_path = folder / "description.yaml"
    fields = _read_description_yaml(description_path)
    text = str(fields.get("description") or "").strip()
    if not text:
        raise ValueError(f"Missing description in {description_path}")

    input_files = fields.get("input_files") or ["input.png"]
    if not isinstance(input_files, list):
        raise ValueError(f"input_files must be a list in {description_path}")
    image_paths = [_require_file(folder / str(image_name)) for image_name in input_files]
    return CadGenBenchQuery(folder_id, "100", text, image_paths)


def _load_200_query(folder: Path, folder_id: int) -> CadGenBenchQuery:
    operation_path = folder / "edit_description.txt"
    operation = _require_file(operation_path).read_text().strip()
    if not operation:
        raise ValueError(f"Missing operation text in {operation_path}")

    renders_dir = _render_dir(folder)
    image_paths = _render_images(renders_dir)
    text = _EDIT_PROMPT_TEMPLATE.format(operation=operation)
    return CadGenBenchQuery(folder_id, "200", text, image_paths)


def _read_description_yaml(path: Path) -> dict[str, object]:
    path = _require_file(path)
    fields: dict[str, object] = {}
    lines = path.read_text().splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            index += 1
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value in {">", "|"}:
            block_lines: list[str] = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or lines[index].startswith((" ", "\t"))
            ):
                block_lines.append(lines[index].strip())
                index += 1
            fields[key] = " ".join(part for part in block_lines if part).strip()
            continue
        if value == "":
            items: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith((" ", "\t")):
                item = lines[index].strip()
                if item.startswith("- "):
                    items.append(_unquote(item[2:].strip()))
                index += 1
            fields[key] = items
            continue
        fields[key] = _unquote(value)
        index += 1
    return fields


def _select_folders(
    data_dir: Path,
    series: list[CadGenBenchSeries],
    folder_ids: list[int] | None,
) -> list[Path]:
    requested = set(folder_ids or [])
    folders: list[Path] = []
    for folder in data_dir.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
        folder_id = int(folder.name)
        if requested and folder_id not in requested:
            continue
        if _series_for_folder_id(folder_id) in series:
            folders.append(folder)

    found_ids = {int(folder.name) for folder in folders}
    missing = sorted(requested - found_ids)
    if missing:
        missing_text = ", ".join(str(folder_id) for folder_id in missing)
        raise ValueError(f"Requested CadGenBench folder(s) not found in selected series: {missing_text}")
    return sorted(folders, key=lambda path: int(path.name))


def _series_for_folder_id(folder_id: int) -> CadGenBenchSeries:
    for series, folder_range in _SERIES_RANGES.items():
        if folder_id in folder_range:
            return series
    raise ValueError(f"Unsupported CadGenBench folder id: {folder_id}")


def _render_dir(folder: Path) -> Path:
    for name in ("renders", "render"):
        candidate = folder / name
        if candidate.exists():
            if not candidate.is_dir():
                raise ValueError(f"Render path is not a directory: {candidate}")
            return candidate
    raise ValueError(f"Render directory not found in {folder}")


def _render_images(renders_dir: Path) -> list[Path]:
    by_stem = {path.stem: path for path in renders_dir.glob("*.png")}
    ordered = [by_stem.pop(stem) for stem in _RENDER_ORDER if stem in by_stem]
    ordered.extend(sorted(by_stem.values(), key=lambda path: path.name))
    if len(ordered) != 4:
        raise ValueError(f"Expected 4 render images in {renders_dir}, found {len(ordered)}")
    return ordered


def _normalize_series(series: list[CadGenBenchSeries]) -> list[CadGenBenchSeries]:
    normalized: list[CadGenBenchSeries] = []
    for value in series:
        if value not in _SERIES_RANGES:
            raise ValueError(f"Unsupported CadGenBench series: {value}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("At least one CadGenBench series is required.")
    return normalized


def _build_setup(
    settings: Settings,
    model: str | None,
    response_mode: str | None,
    return_format: str | None,
    linear_deflection: float | None,
    angular_deflection: float | None,
) -> dict[str, object]:
    setup = default_setup(settings)
    if model is not None:
        setup["model"] = model
    if response_mode is not None:
        setup["response_mode"] = response_mode
    if return_format is not None:
        setup["return_format"] = return_format
    if linear_deflection is not None:
        setup["linear_deflection"] = linear_deflection
    if angular_deflection is not None:
        setup["angular_deflection"] = angular_deflection
    return setup


def _stored_query(
    query: CadGenBenchQuery,
    category: str,
) -> dict[str, object]:
    return {
        "id": str(query.folder_id),
        "text": query.text,
        "model": "",
        "category": category or f"cadgenbench-{query.series}",
        "metadata": {
            "source": "cadgenbench-data",
            "folder_id": query.folder_id,
            "series": query.series,
        },
        "images": [
            {
                "path": _stored_image_path(path),
                "media_type": media_type_for_path(path),
            }
            for path in query.image_paths
        ],
    }


def _stored_image_path(path: Path) -> str:
    path = path.expanduser().resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _default_experiment_name(series: list[CadGenBenchSeries]) -> str:
    if len(series) == 1:
        return f"CadGenBench {series[0]} Series"
    return "CadGenBench 100 and 200 Series"


def _default_experiment_description(
    series: list[CadGenBenchSeries],
    folder_ids: list[int] | None,
) -> str:
    folder_text = "selected folders" if folder_ids else "all folders"
    series_text = " and ".join(series)
    return f"Generated from CadGenBench {series_text} series {folder_text}."


def _require_file(path: Path) -> Path:
    if not path.exists():
        raise ValueError(f"Required file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Expected file path: {path}")
    return path


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
