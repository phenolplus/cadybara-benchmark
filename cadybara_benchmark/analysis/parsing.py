from __future__ import annotations

import json
from typing import Any


def parse_output(raw_output: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw_output is None:
        return {}
    if isinstance(raw_output, str):
        try:
            raw_output = json.loads(raw_output)
        except json.JSONDecodeError:
            return {"raw_text": raw_output}
    validation = raw_output.get("validation") or {}
    return {
        "response_mode": raw_output.get("response_mode"),
        "has_generated_code": bool(raw_output.get("generated_code")),
        "validation": validation,
    }
