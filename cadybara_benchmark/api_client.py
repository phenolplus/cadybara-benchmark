from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

import requests

from cadybara_benchmark.config import Settings, get_settings


@dataclass
class GenerateResult:
    stl_bytes: bytes
    raw_response: dict[str, Any]
    response_metadata: dict[str, Any]
    generated_code: str | None = None


class CadybaraApiError(RuntimeError):
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        response = payload.get("response")
        response_error = response.get("error") if isinstance(response, dict) else None
        super().__init__(
            payload.get("message")
            or payload.get("detail")
            or response_error
            or "Cadybara API error"
        )


class CadybaraApiClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate(
        self,
        prompt: str,
        parameters: dict[str, Any] | None = None,
    ) -> GenerateResult:
        api_key = self.settings.require_api_key()
        parameters = parameters or {}
        response_mode = parameters.get("response_mode", self.settings.default_response_mode)
        body = {
            "prompt": prompt,
            "response_mode": response_mode,
            "linear_deflection": parameters.get(
                "linear_deflection", self.settings.default_linear_deflection
            ),
            "angular_deflection": parameters.get(
                "angular_deflection", self.settings.default_angular_deflection
            ),
        }
        model = parameters.get("model")
        if model:
            body["model"] = model
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{self.settings.api_base_url}/api/agent/generate",
                headers={"Content-Type": "application/json", "X-API-Key": api_key},
                json=body,
                timeout=self.settings.request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CadybaraApiError(
                {"message": str(exc), "type": exc.__class__.__name__, "status_code": None}
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise CadybaraApiError(self._error_payload(response, latency_ms))

        if response_mode == "stl":
            raw_response = {"response_mode": "stl"}
            return GenerateResult(
                stl_bytes=response.content,
                raw_response=raw_response,
                response_metadata={"latency_ms": latency_ms, "response_mode": "stl"},
            )

        data = response.json()
        stl_base64 = data.get("stl_base64")
        if not stl_base64:
            raise CadybaraApiError(
                {
                    "message": "Cadybara JSON response did not include stl_base64.",
                    "status_code": response.status_code,
                    "response": data,
                    "latency_ms": latency_ms,
                }
            )
        stl_bytes = base64.b64decode(stl_base64)
        validation = data.get("validation") or {}
        response_metadata = {
            "latency_ms": latency_ms,
            "response_mode": data.get("response_mode", "json"),
            "validation": validation,
        }
        return GenerateResult(
            stl_bytes=stl_bytes,
            raw_response=data,
            response_metadata=response_metadata,
            generated_code=data.get("generated_code"),
        )

    @staticmethod
    def _error_payload(response: requests.Response, latency_ms: int) -> dict[str, Any]:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        payload = {
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "response": body,
        }
        if isinstance(body, dict):
            payload["code"] = body.get("code")
            payload["detail"] = body.get("detail")
            payload["message"] = body.get("message") or body.get("detail")
        else:
            payload["message"] = str(body)
        return payload
