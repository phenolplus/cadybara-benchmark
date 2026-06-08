from __future__ import annotations

import pytest

from cadybara_benchmark.config import Settings


@pytest.fixture
def settings(tmp_path):
    workspace = tmp_path / "workspace"
    published = tmp_path / "published"
    test_settings = Settings(
        api_base_url="https://api.cadybara.com",
        api_key="pfk_test",
        workspace_dir=workspace,
        published_dir=published,
        default_response_mode="json",
        default_linear_deflection=0.1,
        default_angular_deflection=0.1,
        request_timeout_seconds=180,
    )
    return test_settings
