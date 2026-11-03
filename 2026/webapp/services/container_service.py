"""Validate the container type specified in the transport request.

The booking's type is authoritative. Weight and cargo names never change it.
"""
from __future__ import annotations

from services.weight_gate import WEIGHT_GATE

CONTAINER_LABELS = {
    "20DC": "20피트 드라이",
    "20RF": "20피트 냉장·냉동",
    "20TK": "20피트 탱크",
    "40DC": "40피트 드라이",
    "40HC": "40피트 하이큐브",
    "40OT": "40피트 오픈탑",
    "40RF": "40피트 냉장·냉동",
    "45HC": "45피트 하이큐브",
}


def normalize_container_type(value: object) -> str:
    if not isinstance(value, str) or value.strip().upper() not in WEIGHT_GATE:
        raise ValueError({"container_type": "운송 요청에 지정된 컨테이너 타입을 선택해주세요."})
    return value.strip().upper()


def describe_container(container_type: str) -> dict:
    """Return metadata for the specified type, without inferring a new type."""
    selected = normalize_container_type(container_type)
    return {
        "container_type": selected,
        "label": CONTAINER_LABELS[selected],
        "source": "specified",
        "reason": f"지정한 {selected}의 중량 기준을 적용합니다.",
    }
