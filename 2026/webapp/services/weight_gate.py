"""Container weight gate preserved from the supplied model code."""

from __future__ import annotations

import math


WEIGHT_GATE = {
    "20DC": {"warn_kg": 21_500, "block_kg": 21_750},
    "20RF": {"warn_kg": 21_500, "block_kg": 22_000},
    "20TK": {"warn_kg": 21_500, "block_kg": 32_270},
    "40DC": {"warn_kg": 26_000, "block_kg": 26_740},
    "40HC": {"warn_kg": 26_000, "block_kg": 26_540},
    "40OT": {"warn_kg": 26_000, "block_kg": 26_500},
    "40RF": {"warn_kg": None, "block_kg": 25_780},
    "45HC": {"warn_kg": None, "block_kg": 25_760},
}


def judge_weight_gate(container_type: str, weight_kg: float) -> dict:
    """Apply the original >= WARN/BLOCK boundary semantics."""
    ctype = str(container_type or "").strip().upper()
    if ctype not in WEIGHT_GATE:
        return {"status": "UNKNOWN_TYPE", "message": "지원하지 않는 컨테이너 타입입니다."}
    try:
        weight = float(weight_kg)
    except (TypeError, ValueError):
        return {"status": "UNKNOWN_WEIGHT", "message": "유효한 화물 중량을 입력해주세요."}
    if not math.isfinite(weight) or weight <= 0:
        return {"status": "UNKNOWN_WEIGHT", "message": "화물 중량은 0보다 커야 합니다."}

    rule = WEIGHT_GATE[ctype]
    if weight >= rule["block_kg"]:
        return {
            "status": "BLOCK",
            "message": f"{ctype} 허용 중량 {rule['block_kg']:,}kg 이상입니다. 중량 또는 컨테이너 조건을 수정해주세요.",
            **rule,
        }
    if rule["warn_kg"] is not None and weight >= rule["warn_kg"]:
        return {
            "status": "WARN",
            "message": f"{ctype} 과적 주의 구간입니다. 축중과 운송 조건을 확인한 뒤 배차를 확정해주세요.",
            **rule,
        }
    return {"status": "OK", "message": "중량 기준을 정상 통과했습니다.", **rule}

