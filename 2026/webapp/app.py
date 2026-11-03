"""Flask entrypoint for the vehicle dispatch recommendation system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from config import MAX_WORK_GAP_H, MIN_ARRIVAL_SLACK_MIN, TOP_CANDIDATES
from model.dispatch_model import DispatchEngine
from services.container_service import CONTAINER_LABELS, describe_container
from services.evaluation_service import evaluate
from services.state_store import DispatchStateStore
from services.validation import validate_order_payload
from services.weight_gate import WEIGHT_GATE, judge_weight_gate


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
engine = DispatchEngine()
store = DispatchStateStore()


def api_error(message: Any, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def prepare_order(payload: dict[str, Any]) -> tuple[dict[str, Any], dict, dict]:
    cleaned = validate_order_payload(payload)
    container = describe_container(cleaned["container_type"])
    gate = judge_weight_gate(container["container_type"], cleaned["weight_kg"])
    return cleaned, container, gate


def dashboard(at: datetime) -> dict[str, Any]:
    commits = store.commits()
    fleet = engine.fleet_snapshot(at, commits)
    slacks = [item.get("arrival_slack_min") for item in commits if isinstance(item.get("arrival_slack_min"), (int, float))]
    return {
        "waiting": sum(item["status"] == "대기 중" for item in fleet),
        "driving": sum(item["status"] == "운행 중" for item in fleet),
        "today_orders": len([item for item in commits if str(item.get("order_time", "")).startswith(at.date().isoformat())]),
        "average_slack_min": round(sum(slacks) / len(slacks)) if slacks else 0,
        "warn_orders": sum(item.get("gate_status") == "WARN" for item in commits),
        "recent_dispatches": list(reversed(commits[-6:])),
    }


@app.get("/")
def index():
    return render_template("index.html", container_labels=CONTAINER_LABELS)


@app.get("/recommendations")
def recommendations_page():
    """Separate result page; the browser restores requests, not model scores."""
    return render_template("results.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "model": "Stateful Sequential Slack25/WorkGap24h", "vehicles": len(engine.vehicles), "od_pairs": len(engine.od_map), "top_candidates": TOP_CANDIDATES})


@app.get("/api/orders/<order_id>")
def order_status(order_id: str):
    """Restore confirmed results after reload or a lost confirmation response."""
    commit = next((item for item in store.commits() if item["order_id"] == order_id), None)
    return jsonify({"ok": True, "commit": commit})


@app.get("/api/bootstrap")
def bootstrap():
    try:
        reference = datetime.fromisoformat(request.args.get("at", "2026-03-18T09:00"))
    except ValueError:
        return api_error("기준시각 형식이 올바르지 않습니다.")
    commits = store.commits()
    return jsonify({
        "ok": True,
        "locations": engine.known_reps,
        "coordinates": engine.locations,
        "fleet": engine.fleet_snapshot(reference, commits, limit=80),
        "dashboard": dashboard(reference),
        "model": {
            "name": "Stateful Real-Time Unified Vehicle Ranking",
            "dataset": engine.metadata,
            "minimum_arrival_slack_min": MIN_ARRIVAL_SLACK_MIN,
            "maximum_work_gap_h": MAX_WORK_GAP_H,
            "ranking": ["공차거리 최소", "도착 여유 25분에 가까운 순", "가용 후 경과시간 짧은 순", "차량 ID"],
            "weighted_objective": False,
            "future_fixed_schedule": False,
        },
        "weight_rules": WEIGHT_GATE,
    })


@app.get("/api/evaluation")
def evaluation():
    """Return revised evaluation metrics for confirmed web dispatches."""
    return jsonify({"ok": True, "metrics": evaluate(store.commits())})


@app.post("/api/container")
def container_preview():
    try:
        _, container, gate = prepare_order(request.get_json(silent=True) or {})
        return jsonify({"ok": True, "container": container, "gate": gate})
    except ValueError as exc:
        return api_error(exc.args[0])


@app.post("/api/recommend")
def recommend():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return api_error("운송 요청은 JSON 객체여야 합니다.")
    payload.setdefault("order_id", f"ORD-WEB-{uuid.uuid4().hex[:8].upper()}")
    try:
        cleaned, container, gate = prepare_order(payload)
        response = {"ok": True, "container": container, "gate": gate, "order_id": cleaned["order_id"]}
        if gate["status"] == "BLOCK":
            response.update({"status": "BLOCK", "candidates": [], "feasible_candidate_count": 0})
            return jsonify(response)
        order = engine.build_order(cleaned, container["container_type"])
        result = engine.recommend(order, store.commits(), top_n=TOP_CANDIDATES)
        response.update(result)
        response["status"] = "RECOMMENDED" if result["candidates"] else "NO_FEASIBLE"
        response["map"] = {"pickup": engine.coordinate(order.pickup_rep), "dropoff": engine.coordinate(order.dropoff_rep)}
        return jsonify(response)
    except ValueError as exc:
        return api_error(exc.args[0])
    except Exception as exc:
        app.logger.exception("recommendation failed")
        return api_error(f"추천 처리 중 오류가 발생했습니다: {exc}", 500)


@app.post("/api/dispatch")
def confirm_dispatch():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return api_error("배차 요청은 JSON 객체여야 합니다.")
    vehicle_id = str(payload.get("vehicle_id", "")).strip()
    if not vehicle_id:
        return api_error("배차할 차량을 선택해주세요.")
    try:
        cleaned, container, gate = prepare_order(payload.get("order", {}))
        if not cleaned.get("order_id"):
            return api_error("추천 조회 후 운송건 번호와 함께 배차를 확정해주세요.")
        if gate["status"] == "BLOCK":
            return api_error("BLOCK 주문은 배차를 확정할 수 없습니다.", 409)
        order = engine.build_order(cleaned, container["container_type"])
        result = engine.recommend(order, store.commits(), top_n=len(engine.vehicles))
        candidate = next((item for item in result["candidates"] if item["vehicle_id"] == vehicle_id), None)
        if candidate is None:
            return api_error("차량 상태가 변경되어 더 이상 배차할 수 없습니다. 다시 추천해주세요.", 409)
        commit = {
            "order_id": order.order_id,
            "recommendation_status": "RECOMMENDED",
            "vehicle_id": vehicle_id,
            "owner_type": candidate["owner_type"],
            "order_time": order.order_time.isoformat(),
            "finish_time": candidate["estimated_finish_time"],
            "pickup_rep": order.pickup_rep,
            "dropoff_rep": order.dropoff_rep,
            "container_type": order.container_type,
            "cargo_type": order.cargo_type,
            "weight_kg": order.weight_kg,
            "gate_status": gate["status"],
            "candidate_count": result["feasible_candidate_count"],
            "work_gap_h": candidate["work_gap_h"],
            "empty_distance_km": candidate["empty_distance_km"],
            "empty_time_min": candidate["empty_time_min"],
            "arrival_slack_min": candidate["arrival_slack_min"],
            "confirmed_at": datetime.now().replace(microsecond=0).isoformat(),
        }
        store.add_commit(commit)
        return jsonify({"ok": True, "message": f"{vehicle_id} 배차가 확정되었습니다.", "commit": commit, "vehicle": engine.vehicle_snapshot(vehicle_id, order.order_time, store.commits())})
    except ValueError as exc:
        status = 409 if isinstance(exc.args[0], str) and "이미" in exc.args[0] else 400
        return api_error(exc.args[0], status)


@app.post("/api/reset")
def reset_demo():
    store.clear()
    return jsonify({"ok": True, "message": "시연 배차 이력이 초기화되었습니다."})


@app.errorhandler(404)
def not_found(_exception):
    return api_error("요청한 페이지를 찾을 수 없습니다.", 404)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


