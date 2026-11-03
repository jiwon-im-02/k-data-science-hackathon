"""Validate transport requests with an explicitly specified container type."""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from services.container_service import normalize_container_type


def validate_order_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("운송 요청은 JSON 객체여야 합니다.")
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}
    for field, label in (("pickup", "상차지"), ("dropoff", "하차지"), ("work_time", "상차 예정 일시")):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors[field] = f"{label}을(를) 입력해주세요."
        else:
            cleaned[field] = value.strip()
    try:
        cleaned["container_type"] = normalize_container_type(payload.get("container_type"))
    except ValueError as exc:
        errors.update(exc.args[0])
    try:
        raw_weight = payload.get("weight_kg")
        if isinstance(raw_weight, bool):
            raise ValueError
        weight = float(raw_weight)
        if not isfinite(weight) or not 0 < weight <= 100_000:
            raise ValueError
        cleaned["weight_kg"] = weight
    except (TypeError, ValueError):
        errors["weight_kg"] = "화물 중량은 0 초과, 100,000kg 이하의 숫자로 입력해주세요."
    try:
        parsed = datetime.fromisoformat(cleaned.get("work_time", ""))
        if parsed.tzinfo is not None:
            raise ValueError
        cleaned["work_time"] = parsed.isoformat()
    except ValueError:
        errors["work_time"] = "한국 표준시 기준의 올바른 상차 예정 일시를 입력해주세요."
    if cleaned.get("pickup") and cleaned.get("pickup") == cleaned.get("dropoff"):
        errors["dropoff"] = "상차지와 하차지는 달라야 합니다."

    # Optional description is retained for display, never used to infer equipment.
    cargo = payload.get("cargo_type", "")
    if not isinstance(cargo, str) or len(cargo.strip()) > 100:
        errors["cargo_type"] = "화물명은 100자 이내로 입력해주세요."
    else:
        cleaned["cargo_type"] = cargo.strip()
    if "order_id" in payload:
        order_id = payload["order_id"]
        if not isinstance(order_id, str) or not order_id.strip() or len(order_id) > 100:
            errors["order_id"] = "올바른 운송건 번호가 필요합니다."
        else:
            cleaned["order_id"] = order_id.strip()
    if errors:
        raise ValueError(errors)
    return cleaned
