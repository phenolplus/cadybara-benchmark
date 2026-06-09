from __future__ import annotations

import base64

from tests.conftest import mock_generate_result
from cadybara_benchmark.experiment_files import load_experiment
from cadybara_benchmark.query_images import load_api_images, resolve_query_image_path
from cadybara_benchmark.services.experiments import create_experiment
from cadybara_benchmark.services.queries import add_query, list_queries
from cadybara_benchmark.services.runs import run_experiment
from cadybara_benchmark.web import api_get_query_image


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeClient:
    def __init__(self):
        self.calls: list[dict] = []

    def generate(self, prompt, parameters):
        self.calls.append({"prompt": prompt, "parameters": parameters})
        return mock_generate_result()


def _patch_settings(monkeypatch, settings):
    for module in (
        "cadybara_benchmark.web",
        "cadybara_benchmark.experiment_files",
        "cadybara_benchmark.services.experiments",
        "cadybara_benchmark.query_images",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)


def test_add_query_with_image_persists_and_serves(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Image Prompt Test", settings=settings)
    image_b64 = base64.b64encode(PNG_BYTES).decode("ascii")
    query = add_query(
        "EXP001",
        "Recreate this part in CAD.",
        images=[{"media_type": "image/png", "data": image_b64}],
        settings=settings,
    )

    assert query["images"] == [
        {
            "media_type": "image/png",
            "url": "/api/experiments/EXP001/queries/Q001/images/0",
        }
    ]

    stored = load_experiment("EXP001", settings)
    assert stored["queries"][0]["images"][0]["media_type"] == "image/png"
    assert stored["queries"][0]["images"][0]["path"].endswith("Q001-0.png")

    listed = list_queries("EXP001", settings)[0]
    assert listed["images"][0]["url"] == "/api/experiments/EXP001/queries/Q001/images/0"

    response = api_get_query_image("EXP001", "Q001", 0)
    assert str(response.path).endswith("Q001-0.png")
    assert response.media_type == "image/png"


def test_run_experiment_passes_images_to_api(settings):
    create_experiment("Image Prompt Run", settings=settings)
    image_b64 = base64.b64encode(PNG_BYTES).decode("ascii")
    add_query(
        "EXP001",
        "Recreate this bracket.",
        images=[{"media_type": "image/png", "data": image_b64}],
        settings=settings,
    )

    client = FakeClient()
    summary = run_experiment("EXP001", client=client, settings=settings)

    assert summary["completed"] == 1
    assert client.calls[0]["prompt"] == "Recreate this bracket."
    images = client.calls[0]["parameters"]["images"]
    assert len(images) == 1
    assert images[0]["media_type"] == "image/png"
    assert base64.b64decode(images[0]["data"]) == PNG_BYTES


def test_load_api_images_requires_existing_files(settings):
    create_experiment("Missing Image", settings=settings)
    stored_images = [{"path": "workspace/experiments/EXP001/images/missing.png", "media_type": "image/png"}]

    try:
        load_api_images(stored_images)
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("Expected missing image path to raise ValueError")


def test_resolve_query_image_path_rejects_outside_experiment_dir(settings):
    create_experiment("Image Guard", settings=settings)
    stored_images = [{"path": "workspace/experiments/EXP002/images/Q001-0.png", "media_type": "image/png"}]

    try:
        resolve_query_image_path("EXP001", "Q001", 0, stored_images)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("Expected out-of-experiment image path to raise ValueError")
