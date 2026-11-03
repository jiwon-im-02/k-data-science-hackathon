"""Build the revised runtime dataset from the supplied model workbooks.

The revised final model restores vehicle state exclusively from
`순차모델링_FIXED스케줄.xlsx`.  Despite its filename, only the past history
sheet is used; future FIXED events are intentionally not loaded.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

from config import FIXED_HISTORY_WORKBOOK, MODEL_DATASET, MODEL_WORKBOOK, OD_WORKBOOK


MODEL_VERSION = "slack25-workgap24h"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value if value and value.lower() not in {"nan", "none", "null", "<na>"} else None


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _rows(path: Path, sheet: str) -> Iterable[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet]
        iterator = worksheet.iter_rows(values_only=True)
        headers = [str(value) if value is not None else "" for value in next(iterator)]
        for values in iterator:
            yield dict(zip(headers, values))
    finally:
        workbook.close()


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def build_dataset(output_path: Path = MODEL_DATASET) -> dict[str, Any]:
    for path in (MODEL_WORKBOOK, FIXED_HISTORY_WORKBOOK, OD_WORKBOOK):
        if not path.exists():
            raise FileNotFoundError(f"필수 모델 데이터가 없습니다: {path}")

    locations: dict[str, dict[str, float]] = {}
    for row in _rows(MODEL_WORKBOOK, "02_대표위치좌표"):
        name, lon, lat = _text(row.get("대표위치")), row.get("lon"), row.get("lat")
        if name and isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            locations[name] = {"lon": float(lon), "lat": float(lat)}

    od_map: dict[str, dict[str, float]] = {}
    distances: list[float] = []
    travel_times: list[float] = []
    for row in _rows(OD_WORKBOOK, "02_ODCache"):
        origin, destination = _text(row.get("origin_rep")), _text(row.get("destination_rep"))
        distance, travel_h = row.get("도로거리_km"), row.get("예상시간_h")
        if not origin or not destination or not isinstance(distance, (int, float)) or not isinstance(travel_h, (int, float)):
            continue
        od_map[f"{origin}\u241f{destination}"] = {"distance_km": float(distance), "time_h": float(travel_h)}
        if distance > 0:
            distances.append(float(distance))
        if travel_h > 0:
            travel_times.append(float(travel_h))

    known_reps = sorted({part for key in od_map for part in key.split("\u241f")})
    jobs_by_vehicle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dispatch_counts: dict[str, Counter] = defaultdict(Counter)
    excluded_ambiguous = 0

    for row in _rows(FIXED_HISTORY_WORKBOOK, "01_전체스케줄_타겟표시"):
        vehicle = _text(row.get("차량"))
        event_time = row.get("작업일시")
        pickup_rep = _text(row.get("현재상차지_rep"))
        dropoff_rep = _text(row.get("현재하차지_rep"))
        if not vehicle or not isinstance(event_time, datetime) or not dropoff_rep:
            excluded_ambiguous += 1
            continue
        dispatch_type = _text(row.get("용차")) or "용차"
        dispatch_counts[vehicle][dispatch_type] += 1
        jobs_by_vehicle[vehicle].append({
            "started_at": _iso(event_time),
            # In the revised model 작업일시 itself is the vehicle available time.
            "finish_at": _iso(event_time),
            "pickup_rep": pickup_rep or dropoff_rep,
            "dropoff_rep": dropoff_rep,
            "is_target": str(row.get("재배차대상여부") or "").strip().upper() == "O",
            "source_order_id": _text(row.get("재배차_order_id")),
        })

    vehicles: dict[str, dict[str, Any]] = {}
    for vehicle, jobs in jobs_by_vehicle.items():
        jobs.sort(key=lambda item: item["started_at"])
        counts = dispatch_counts[vehicle]
        vehicles[vehicle] = {
            "owner_type": "자차" if counts["자차"] > counts["용차"] else "용차",
            "jobs": jobs,
        }

    dataset = {
        "model_version": MODEL_VERSION,
        "metadata": {
            "model_version": MODEL_VERSION,
            "built_at": _iso(datetime.now()),
            "source": "모델 코드_수정.txt + 순차모델링_FIXED스케줄.xlsx",
            "vehicle_count": len(vehicles),
            "od_count": len(od_map),
            "location_count": len(known_reps),
            "excluded_ambiguous_history_rows": excluded_ambiguous,
            "minimum_arrival_slack_min": 25,
            "maximum_work_gap_h": 24,
            "dist_q75": _percentile(distances, .75),
            "time_q75": _percentile(travel_times, .75),
        },
        "locations": locations,
        "known_reps": known_reps,
        "od_map": od_map,
        "vehicles": vehicles,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(output_path)
    return dataset


if __name__ == "__main__":
    built = build_dataset()
    print(json.dumps(built["metadata"], ensure_ascii=False, indent=2))

