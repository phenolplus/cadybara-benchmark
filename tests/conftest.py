from __future__ import annotations

import pytest

from cadybara_benchmark.config import Settings
from cadybara_benchmark.db import init_db


@pytest.fixture
def settings(tmp_path):
    workspace = tmp_path / "workspace"
    published = tmp_path / "published"
    test_settings = Settings(
        api_base_url="https://api.cadybara.com",
        api_key="pfk_test",
        db_path=workspace / "research.db",
        workspace_dir=workspace,
        published_dir=published,
        default_response_mode="json",
        default_linear_deflection=0.1,
        default_angular_deflection=0.1,
        request_timeout_seconds=180,
    )
    init_db(test_settings)
    return test_settings
