"""Evaluation metrics ported from the revised final model.

The functions accept ordinary dictionaries so the web layer can evaluate live
session results without adding pandas to the runtime dependencies.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median
from typing import Any

from config import MAX_WORK_GAP_H, MIN_ARRIVAL_SLACK_MIN


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def make_vehicle_saving_table(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate actual/recommended empty distance by recommended vehicle."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        actual = _number(row.get("actual_empty_distance_km"))
        proposed = _number(row.get("empty_distance_km", row.get("recommended_empty_distance_km")))
        vehicle = row.get("vehicle_id", row.get("recommended_vehicle"))
        if row.get("recommendation_status", "RECOMMENDED") == "RECOMMENDED" and vehicle and actual is not None and proposed is not None:
            grouped[str(vehicle)].append({"actual": actual, "proposed": proposed})

    output = []
    for vehicle, rows in grouped.items():
        actual_total = sum(row["actual"] for row in rows)
        proposed_total = sum(row["proposed"] for row in rows)
        saved = actual_total - proposed_total
        output.append({
            "recommended_vehicle": vehicle,
            "recommendation_count": len(rows),
            "actual_empty_distance_total_km": actual_total,
            "recommended_empty_distance_total_km": proposed_total,
            "saved_empty_distance_km": saved,
            "vehicle_saving_rate": saved / actual_total if actual_total > 0 else None,
            "improved": proposed_total < actual_total,
        })
    return sorted(output, key=lambda row: (-(row["vehicle_saving_rate"] if row["vehicle_saving_rate"] is not None else -math.inf), -row["recommendation_count"]))


def evaluate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the revised coverage, recommendation, order, and vehicle metrics."""
    total = len(results)
    blocked = [row for row in results if row.get("recommendation_status") == "BLOCK"]
    recommended = [row for row in results if row.get("recommendation_status", "RECOMMENDED") == "RECOMMENDED"]
    no_feasible = [row for row in results if row.get("recommendation_status") == "NO_FEASIBLE"]
    eligible = total - len(blocked)

    def values(*keys: str) -> list[float]:
        output = []
        for row in recommended:
            value = None
            for key in keys:
                value = _number(row.get(key))
                if value is not None:
                    break
            if value is not None:
                output.append(value)
        return output

    candidates = values("candidate_count")
    work_gaps = values("work_gap_h")
    distances = values("empty_distance_km", "recommended_empty_distance_km")
    empty_times = values("empty_time_min", "recommended_empty_time_min")
    slacks = values("arrival_slack_min")

    comparable = []
    for row in recommended:
        actual = _number(row.get("actual_empty_distance_km"))
        proposed = _number(row.get("empty_distance_km", row.get("recommended_empty_distance_km")))
        if actual is not None and proposed is not None:
            comparable.append((actual, proposed))
    actual_total = sum(pair[0] for pair in comparable) if comparable else None
    proposed_total = sum(pair[1] for pair in comparable) if comparable else None
    positive_rates = [(actual - proposed) / actual for actual, proposed in comparable if actual > 0]

    vehicles = make_vehicle_saving_table(results)
    vehicle_rates = [row["vehicle_saving_rate"] for row in vehicles if row["vehicle_saving_rate"] is not None]
    return {
        "Minimum_Arrival_Slack_min": MIN_ARRIVAL_SLACK_MIN,
        "Maximum_Work_Gap_h": MAX_WORK_GAP_H,
        "전체주문수": total,
        "BLOCK주문수": len(blocked),
        "추천대상주문수": eligible,
        "추천성공주문수": len(recommended),
        "추천성공률": len(recommended) / eligible if eligible else None,
        "후보없음주문수": len(no_feasible),
        "평균후보차량수": mean(candidates) if candidates else None,
        "중앙값후보차량수": median(candidates) if candidates else None,
        "평균추천작업간격_h": mean(work_gaps) if work_gaps else None,
        "중앙값추천작업간격_h": median(work_gaps) if work_gaps else None,
        "Q95추천작업간격_h": _quantile(work_gaps, .95),
        "평균추천공차거리_km": mean(distances) if distances else None,
        "중앙값추천공차거리_km": median(distances) if distances else None,
        "0km추천비율": sum(value <= 1e-9 for value in distances) / len(distances) if distances else None,
        "평균추천공차시간_min": mean(empty_times) if empty_times else None,
        "중앙값추천공차시간_min": median(empty_times) if empty_times else None,
        "평균도착여유_min": mean(slacks) if slacks else None,
        "중앙값도착여유_min": median(slacks) if slacks else None,
        "Q25도착여유_min": _quantile(slacks, .25),
        "Q75도착여유_min": _quantile(slacks, .75),
        "실제비교가능주문수": len(comparable),
        "실제공차거리합_km": actual_total,
        "추천공차거리합_km": proposed_total,
        "공차거리절감률": (actual_total - proposed_total) / actual_total if actual_total and proposed_total is not None else None,
        "실제대비개선주문비율": sum(proposed < actual for actual, proposed in comparable) / len(comparable) if comparable else None,
        "주문당평균절감거리_km": mean(actual - proposed for actual, proposed in comparable) if comparable else None,
        "평균주문별공차절감률": mean(positive_rates) if positive_rates else None,
        "중앙값주문별공차절감률": median(positive_rates) if positive_rates else None,
        "비교차량수": len(vehicles),
        "공차거리개선차량비율": sum(row["improved"] for row in vehicles) / len(vehicles) if vehicles else None,
        "평균차량별공차절감률": mean(vehicle_rates) if vehicle_rates else None,
        "중앙값차량별공차절감률": median(vehicle_rates) if vehicle_rates else None,
        "Q25차량별공차절감률": _quantile(vehicle_rates, .25),
        "Q75차량별공차절감률": _quantile(vehicle_rates, .75),
    }

