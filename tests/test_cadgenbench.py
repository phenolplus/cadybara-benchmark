from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cadybara_benchmark.cadgenbench import collect_cadgenbench_queries
from cadybara_benchmark.cadgenbench_cli import app
from cadybara_benchmark.experiment_files import load_experiment


runner = CliRunner()


def test_collects_100_series_description_and_yaml_images(tmp_path: Path):
    data_dir = tmp_path / "cadgenbench-data"
    folder = data_dir / "134"
    folder.mkdir(parents=True)
    (folder / "description.yaml").write_text(
        """
description: >
  Reproduce the geometry from the drawings.

input_files:
  - input.png
  - input2.png
""".lstrip()
    )
    _write_png(folder / "input.png")
    _write_png(folder / "input2.png")

    queries = collect_cadgenbench_queries(data_dir, ["100"], [134])

    assert len(queries) == 1
    assert queries[0].folder_id == 134
    assert queries[0].series == "100"
    assert queries[0].text == "Reproduce the geometry from the drawings."
    assert [path.name for path in queries[0].image_paths] == ["input.png", "input2.png"]


def test_collects_200_series_edit_prompt_and_render_images(tmp_path: Path):
    data_dir = tmp_path / "cadgenbench-data"
    folder = data_dir / "201"
    renders_dir = folder / "renders"
    renders_dir.mkdir(parents=True)
    (folder / "edit_description.txt").write_text("Make the bore 2mm wider.\n")
    for name in ["right.png", "top.png", "front.png", "iso.png"]:
        _write_png(renders_dir / name)

    queries = collect_cadgenbench_queries(data_dir, ["200"], [201])

    assert len(queries) == 1
    assert queries[0].text == (
        "The attached images shows several angles of a device. Implement this device. "
        "Then, perform the following operation(s): Make the bore 2mm wider."
    )
    assert [path.name for path in queries[0].image_paths] == [
        "iso.png",
        "front.png",
        "right.png",
        "top.png",
    ]


def test_cli_imports_selected_folders_into_one_experiment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    data_dir = tmp_path / "cadgenbench-data"
    _make_100_folder(data_dir / "134", ["input.png", "input2.png"])
    _make_200_folder(data_dir / "201")

    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(data_dir),
            "--series",
            "both",
            "--folder",
            "134",
            "--folder",
            "201",
            "--name",
            "CadGenBench Smoke",
            "--model",
            "gpt-5.5",
            "--response-mode",
            "json",
            "--return-format",
            "code",
            "--linear-deflection",
            "0.2",
            "--angular-deflection",
            "0.3",
        ],
    )

    assert result.exit_code == 0
    assert "Created experiment EXP001: CadGenBench Smoke with 2 query line(s)" in result.output
    experiment = load_experiment("EXP001")
    assert experiment["setup"] == {
        "model": "gpt-5.5",
        "response_mode": "json",
        "return_format": "code",
        "linear_deflection": 0.2,
        "angular_deflection": 0.3,
    }
    assert [query["id"] for query in experiment["queries"]] == ["134", "201"]
    assert [query["metadata"]["folder_id"] for query in experiment["queries"]] == [134, 201]
    assert len(experiment["queries"][0]["images"]) == 2
    assert len(experiment["queries"][1]["images"]) == 4
    assert not (tmp_path / "workspace" / "experiments" / "EXP001" / "images").exists()
    assert [Path(image["path"]) for image in experiment["queries"][0]["images"]] == [
        data_dir / "134" / "input.png",
        data_dir / "134" / "input2.png",
    ]
    for query in experiment["queries"]:
        for image in query["images"]:
            assert Path(image["path"]).exists()


def _make_100_folder(folder: Path, input_files: list[str] | None = None) -> None:
    input_files = input_files or ["input.png"]
    folder.mkdir(parents=True)
    input_file_lines = "\n".join(f"  - {filename}" for filename in input_files)
    (folder / "description.yaml").write_text(
        f"""
description: "Create the reference part."
input_files:
{input_file_lines}
""".lstrip()
    )
    for filename in input_files:
        _write_png(folder / filename)


def _make_200_folder(folder: Path) -> None:
    renders_dir = folder / "renders"
    renders_dir.mkdir(parents=True)
    (folder / "edit_description.txt").write_text("Add a chamfer.")
    for name in ["iso.png", "front.png", "right.png", "top.png"]:
        _write_png(renders_dir / name)


def _write_png(path: Path) -> None:
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63600000020001e221bc330000000049454e44ae426082"
        )
    )
