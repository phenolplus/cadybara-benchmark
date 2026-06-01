from __future__ import annotations

from typing import Any


def score_result(
    query: dict[str, Any],
    output: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, float]:
    artifact_score = 1.0 if artifacts.get("existing_stl_count", 0) > 0 else 0.0
    validation = output.get("validation") or {}
    validation_score = None
    if validation:
        validation_score = float(validation.get("confidence") or 0.0) if validation.get("valid") else 0.0

    scores = [artifact_score]
    if validation_score is not None:
        scores.append(validation_score)
    overall = sum(scores) / len(scores)
    return {
        "artifact_score": artifact_score,
        "validation_score": validation_score if validation_score is not None else artifact_score,
        "overall": overall,
    }
