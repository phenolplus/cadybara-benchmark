from __future__ import annotations

import json
from typing import Any


def dumps_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def loads_json(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)
