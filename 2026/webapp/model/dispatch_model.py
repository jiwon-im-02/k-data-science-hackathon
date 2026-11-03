"""Revised Stateful Real-Time Unified Vehicle Ranking engine.

This module directly implements `모델 코드_수정.txt`:

* Work Gap = Order Time - Vehicle Available Time, 0 < gap <= 24h
* Estimated Arrival = Vehicle Available Time + Empty Travel Time
* Arrival Slack = Order Time - Estimated Arrival, minimum 25 minutes
* Ranking = empty movement distance/time, arrival slack closest to 25 minutes, vehicle ID
* No weighted objective, future FIXED return constraint, or fallback cost
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import MAX_WORK_GAP_H, MIN_ARRIVAL_SLACK_MIN, MODEL_DATASET, STATE_STALE_CUTOFF_H, TOP_CANDIDATES
from model.data_builder_revised import MODEL_VERSION, build_dataset


@dataclass(frozen=True)
class DispatchOrder:
    order_id: str
    pickup_rep: str
    dropoff_rep: str
    order_time: datetime
    cargo_type: str
    weight_kg: float
    container_type: str


def _dt(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


class DispatchEngine:
    """Single-order web adapter for the revised sequential model."""

    def __init__(self, dataset_path: Path = MODEL_DATASET):
        if not dataset_path.exists():
            build_dataset(dataset_path)
        else:
            try:
                version = json.loads(dataset_path.read_text(encoding="utf-8")).get("model_version")
            except (json.JSONDecodeError, OSError):
                version = None
            if version != MODEL_VERSION:
                build_dataset(dataset_path)

        self.dataset_path = dataset_path
        self.data = json.loads(dataset_path.read_text(encoding="utf-8"))
        self.metadata = self.data["metadata"]
        self.locations = self.data["locations"]
        self.known_reps = self.data["known_reps"]
        self.od_map = self.data["od_map"]
        self.vehicles = self.data["vehicles"]

    def nearest_rep(self, text: str) -> str | None:
        value = str(text or "").strip()
        if value in self.known_reps:
            return value
        hits = [rep for rep in self.known_reps if value in rep or rep in value]
        return hits[0] if hits else None

    def get_od(self, origin: str, destination: str) -> tuple[float, float] | None:
        if origin == destination:
            return 0.0, 0.0
        row = self.od_map.get(f"{origin}\u241f{destination}")
        return (float(row["distance_km"]), float(row["time_h"])) if row else None

    def build_order(self, payload: dict[str, Any], container_type: str) -> DispatchOrder:
        pickup = self.nearest_rep(payload.get("pickup", ""))
        dropoff = self.nearest_rep(payload.get("dropoff", ""))
        if pickup is None:
            raise ValueError("상차지를 모델 OD 대표위치에서 찾지 못했습니다.")
        if dropoff is None:
            raise ValueError("하차지를 모델 OD 대표위치에서 찾지 못했습니다.")
        if self.get_od(pickup, dropoff) is None:
            raise ValueError(f"적재 구간 OD가 없습니다: {pickup} → {dropoff}")
        return DispatchOrder(
            order_id=str(payload["order_id"]),
            pickup_rep=pickup,
            dropoff_rep=dropoff,
            order_time=_dt(payload["work_time"]),
            cargo_type=str(payload.get("cargo_type", "일반 화물")),
            weight_kg=float(payload["weight_kg"]),
            container_type=container_type,
        )

    def _historical_jobs(self, vehicle_id: str) -> list[dict[str, Any]]:
        return self.vehicles[vehicle_id]["jobs"]

    def _state_at(self, vehicle_id: str, order_time: datetime, commits: list[dict[str, Any]]) -> dict[str, Any] | None:
        # The revised source uses only rows strictly earlier than the order and
        # excludes actual executions of re-dispatch targets.
        observed = [
            job for job in self._historical_jobs(vehicle_id)
            if not job["is_target"] and _dt(job["started_at"]) < order_time
        ]
        state = None
        if observed:
            latest = observed[-1]
            state = {
                "available_time": _dt(latest["started_at"]),
                "location_rep": latest["dropoff_rep"],
                "source": "observed_history",
                "active_commit": None,
            }

        # Stateful Sequential update: a previously confirmed web order wins
        # when its finish time is more recent than the observed state.
        relevant = [
            item for item in commits
            if item.get("vehicle_id") == vehicle_id and _dt(item["order_time"]) <= order_time
        ]
        for commit in sorted(relevant, key=lambda item: (item["order_time"], item["order_id"])):
            finish = _dt(commit["finish_time"])
            if state is None or finish >= state["available_time"]:
                state = {
                    "available_time": finish,
                    "location_rep": commit["dropoff_rep"],
                    "source": "confirmed_dispatch",
                    "active_commit": commit,
                }
        return state

    def vehicle_snapshot(self, vehicle_id: str, at: datetime, commits: list[dict[str, Any]]) -> dict[str, Any] | None:
        state = self._state_at(vehicle_id, at, commits)
        if state is None:
            return None
        commit = state["active_commit"]
        running = bool(commit and _dt(commit["order_time"]) <= at < _dt(commit["finish_time"]))
        return {
            "vehicle_id": vehicle_id,
            "owner_type": self.vehicles[vehicle_id]["owner_type"],
            "status": "운행 중" if running else "대기 중",
            "current_location": commit["pickup_rep"] if running else state["location_rep"],
            "available_location": state["location_rep"],
            "available_time": state["available_time"].isoformat(),
            "current_route": f"{commit['pickup_rep']} → {commit['dropoff_rep']}" if running else None,
            "current_pickup": commit["pickup_rep"] if running else None,
            "current_dropoff": commit["dropoff_rep"] if running else None,
            "current_finish_time": commit["finish_time"] if running else None,
            "state_source": state["source"],
        }

    def _score_vehicle(self, order: DispatchOrder, vehicle_id: str, commits: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
        state = self._state_at(vehicle_id, order.order_time, commits)
        if state is None:
            return None, "state_unknown"

        work_gap_h = (order.order_time - state["available_time"]).total_seconds() / 3600
        if work_gap_h <= 0 or work_gap_h > MAX_WORK_GAP_H:
            return None, "work_gap_fail"
        if state["source"] == "observed_history" and work_gap_h > STATE_STALE_CUTOFF_H:
            return None, "stale_state"

        od = self.get_od(state["location_rep"], order.pickup_rep)
        if od is None:
            return None, "pickup_od_missing"
        empty_km, empty_h = od

        estimated_arrival = state["available_time"] + timedelta(hours=empty_h)
        arrival_slack_min = (order.order_time - estimated_arrival).total_seconds() / 60
        if arrival_slack_min < MIN_ARRIVAL_SLACK_MIN:
            return None, "arrival_slack_fail"

        loaded = self.get_od(order.pickup_rep, order.dropoff_rep)
        assert loaded is not None
        finish_time = order.order_time + timedelta(hours=loaded[1])
        snapshot = self.vehicle_snapshot(vehicle_id, order.order_time, commits)
        assert snapshot is not None
        return {
            **snapshot,
            "work_gap_h": round(work_gap_h, 4),
            "work_gap_min": round(work_gap_h * 60),
            "empty_distance_km": round(empty_km, 2),
            "empty_time_h": round(empty_h, 4),
            "empty_time_min": round(empty_h * 60),
            "estimated_arrival_time": estimated_arrival.isoformat(),
            "arrival_slack_min": round(arrival_slack_min),
            "arrival_slack_delta_min": round(abs(arrival_slack_min - MIN_ARRIVAL_SLACK_MIN)),
            "estimated_finish_time": finish_time.isoformat(),
        }, None

    def recommend(self, order: DispatchOrder, commits: list[dict[str, Any]], top_n: int = TOP_CANDIDATES) -> dict[str, Any]:
        feasible: list[dict[str, Any]] = []
        excluded: dict[str, int] = {}
        for vehicle_id in sorted(self.vehicles):
            candidate, reason = self._score_vehicle(order, vehicle_id, commits)
            if candidate is None:
                excluded[reason or "unknown"] = excluded.get(reason or "unknown", 0) + 1
            else:
                feasible.append(candidate)

        # Rank by practical dispatch fit. Empty travel time remains informational
        # rather than a separate criterion derived from the same OD movement.
        feasible.sort(key=lambda item: (
            item["empty_distance_km"],

            item["arrival_slack_delta_min"],
            item["work_gap_h"],
            item["vehicle_id"],
        ))
        for rank, item in enumerate(feasible, start=1):
            item["rank"] = rank

        loaded = self.get_od(order.pickup_rep, order.dropoff_rep)
        return {
            "order": {
                **order.__dict__,
                "order_time": order.order_time.isoformat(),
                "loaded_distance_km": round(loaded[0], 2) if loaded else None,
                "loaded_time_min": round(loaded[1] * 60) if loaded else None,
            },
            "candidates": feasible[:top_n],
            "feasible_candidate_count": len(feasible),
            "evaluated_vehicle_count": len(self.vehicles),
            "excluded_reasons": excluded,
            "minimum_arrival_slack_min": MIN_ARRIVAL_SLACK_MIN,
            "maximum_work_gap_h": MAX_WORK_GAP_H,
            "ranking": ["empty_distance", "arrival_slack_closest_to_25_min", "work_gap_asc", "vehicle_id"],
        }

    def fleet_snapshot(self, at: datetime, commits: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
        rows = [self.vehicle_snapshot(vehicle_id, at, commits) for vehicle_id in sorted(self.vehicles)]
        rows = [row for row in rows if row is not None]
        return rows[:limit] if limit else rows

    def coordinate(self, location: str) -> dict[str, float] | None:
        return self.locations.get(location)



