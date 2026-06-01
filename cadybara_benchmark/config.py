from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


def _path_from_env(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_key: str | None
    db_path: Path
    workspace_dir: Path
    published_dir: Path
    default_response_mode: str
    default_linear_deflection: float
    default_angular_deflection: float
    request_timeout_seconds: int

    def require_api_key(self) -> str:
        if not self.api_key or self.api_key == "pfk_replace_me":
            raise RuntimeError(
                "CADYBARA_API_KEY is required. Add it to .env or export it in the environment."
            )
        return self.api_key


def get_settings() -> Settings:
    _load_env()
    return Settings(
        api_base_url=os.getenv("CADYBARA_API_BASE_URL", "https://api.cadybara.com").rstrip("/"),
        api_key=os.getenv("CADYBARA_API_KEY"),
        db_path=_path_from_env("CADYBARA_DB_PATH", "workspace/research.db"),
        workspace_dir=_path_from_env("CADYBARA_WORKSPACE_DIR", "workspace"),
        published_dir=_path_from_env("CADYBARA_PUBLISHED_DIR", "published"),
        default_response_mode=os.getenv("CADYBARA_DEFAULT_RESPONSE_MODE", "json"),
        default_linear_deflection=float(os.getenv("CADYBARA_DEFAULT_LINEAR_DEFLECTION", "0.1")),
        default_angular_deflection=float(os.getenv("CADYBARA_DEFAULT_ANGULAR_DEFLECTION", "0.1")),
        request_timeout_seconds=int(os.getenv("CADYBARA_REQUEST_TIMEOUT_SECONDS", "180")),
    )
