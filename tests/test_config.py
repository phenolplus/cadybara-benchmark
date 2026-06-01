from __future__ import annotations

import pytest

from cadybara_benchmark.config import Settings


def test_require_api_key_rejects_missing(tmp_path):
    settings = Settings(
        api_base_url="https://api.cadybara.com",
        api_key=None,
        db_path=tmp_path / "research.db",
        workspace_dir=tmp_path / "workspace",
        published_dir=tmp_path / "published",
        default_response_mode="json",
        default_linear_deflection=0.1,
        default_angular_deflection=0.1,
        request_timeout_seconds=180,
    )

    with pytest.raises(RuntimeError):
        settings.require_api_key()


def test_require_api_key_accepts_real_value(settings):
    assert settings.require_api_key() == "pfk_test"
