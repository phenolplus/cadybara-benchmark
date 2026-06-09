from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

from cadybara_benchmark.config import Settings, get_settings


@dataclass
class GenerateResult:
    export_format: str
    raw_response: dict[str, Any]
    response_metadata: dict[str, Any]
    generated_code: str | None = None
    model_bytes: bytes | None = None


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
        export_format = parameters.get(
            "export_format", self.settings.default_return_format
        )
        body = {
            "prompt": prompt,
            "response_mode": response_mode,
            "export_format": export_format,
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
        images = parameters.get("images")
        if images:
            body["images"] = images
        started = time.perf_counter()
        stream = response_mode == "sse"
        try:
            response = requests.post(
                f"{self.settings.api_base_url}/api/agent/generate",
                headers={"Content-Type": "application/json", "X-API-Key": api_key},
                json=body,
                timeout=self.settings.request_timeout_seconds,
                stream=stream,
            )
        except requests.RequestException as exc:
            raise CadybaraApiError(
                {"message": str(exc), "type": exc.__class__.__name__, "status_code": None}
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise CadybaraApiError(self._error_payload(response, latency_ms))

        if response_mode == "sse":
            data = self._parse_sse_response(response, latency_ms)
        else:
            data = response.json()

        return self._build_generate_result(data, latency_ms)

    def _parse_sse_response(
        self, response: requests.Response, latency_ms: int
    ) -> dict[str, Any]:
        terminal_event: dict[str, Any] | None = None
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:].strip())
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            if event_type == "result":
                terminal_event = event
                break
            if event_type == "error":
                raise CadybaraApiError(
                    {
                        "message": event.get("error") or "Cadybara SSE error",
                        "status_code": event.get("status_code"),
                        "code": event.get("code"),
                        "response": event,
                        "latency_ms": latency_ms,
                    }
                )

        if terminal_event is None:
            raise CadybaraApiError(
                {
                    "message": "Cadybara SSE stream ended without a result event.",
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                }
            )
        return terminal_event

    def _build_generate_result(
        self, data: dict[str, Any], latency_ms: int
    ) -> GenerateResult:
        export_format = data.get("export_format", "stl")
        model_bytes = None
        model_base64 = data.get("model_base64")
        if model_base64:
            model_bytes = base64.b64decode(model_base64)
        elif export_format != "code":
            raise CadybaraApiError(
                {
                    "message": "Cadybara response did not include model_base64.",
                    "response": data,
                    "latency_ms": latency_ms,
                }
            )

        validation = data.get("validation") or {}
        response_metadata = {
            "latency_ms": latency_ms,
            "response_mode": data.get("response_mode", "json"),
            "export_format": export_format,
            "validation": validation,
        }
        return GenerateResult(
            export_format=export_format,
            raw_response=data,
            response_metadata=response_metadata,
            generated_code=data.get("generated_code"),
            model_bytes=model_bytes,
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
