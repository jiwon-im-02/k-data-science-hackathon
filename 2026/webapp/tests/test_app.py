"""Integration tests for the revised model, Gate, metrics, and state."""

from datetime import datetime, timedelta

from app import app, engine, store
from services.weight_gate import judge_weight_gate


SAMPLE = {
    "pickup": "의왕ICD",
    "dropoff": "부산신항",
    "work_time": "2026-03-18T09:00",
    "cargo_type": "일반 화물",
    "weight_kg": 18_000,
    "container_type": "20DC",
}


def test_separate_pages_and_local_map_assets():
    client = app.test_client()
    request_page = client.get("/")
    results_page = client.get("/recommendations")
    assert request_page.status_code == results_page.status_code == 200
    assert b'id="orderForm"' in request_page.data
    assert b'id="gateDialog"' in request_page.data
    assert request_page.data.count(b'name="container_type"') == 8
    assert b'name="cargo_category"' not in request_page.data
    assert b'name="cargo_profile"' not in request_page.data
    assert b'id="candidateList"' not in request_page.data
    assert b'id="candidateList"' in results_page.data
    assert b'id="orderForm"' not in results_page.data
    for asset in ("js/request.js", "js/results.js", "js/common.js", "js/route-map.js", "vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css"):
        assert client.get(f"/static/{asset}").status_code == 200


def test_order_status_restores_confirmed_dispatch():
    store.clear()
    client = app.test_client()
    assert client.get("/api/orders/not-found").get_json()["commit"] is None
    result = client.post("/api/recommend", json=SAMPLE).get_json()
    order = {**SAMPLE, "order_id": result["order_id"]}
    selected = result["candidates"][0]["vehicle_id"]
    response = client.post("/api/dispatch", json={"vehicle_id": selected, "order": order})
    restored = client.get(f"/api/orders/{result['order_id']}").get_json()["commit"]
    assert restored == response.get_json()["commit"]
    store.clear()


def test_weight_gate_boundaries():
    assert judge_weight_gate("20DC", 21_499)["status"] == "OK"
    assert judge_weight_gate("20DC", 21_500)["status"] == "WARN"
    assert judge_weight_gate("20DC", 21_750)["status"] == "BLOCK"
    assert judge_weight_gate("40RF", 25_779)["status"] == "OK"
    assert judge_weight_gate("40RF", 25_780)["status"] == "BLOCK"


def test_specified_types_preserved_through_gate_recommendation_and_commit():
    from services.weight_gate import WEIGHT_GATE
    client = app.test_client()
    for container_type, limits in WEIGHT_GATE.items():
        store.clear()
        # Even a light 40/45ft request keeps its booked type.
        order = {**SAMPLE, "container_type": container_type, "weight_kg": 1000,
                 "cargo_type": ""}
        preview = client.post("/api/container", json=order)
        assert preview.status_code == 200
        assert preview.get_json()["container"]["container_type"] == container_type
        data = client.post("/api/recommend", json=order).get_json()
        assert data["order"]["container_type"] == container_type
        assert data["candidates"]
        order["order_id"] = data["order_id"]
        response = client.post("/api/dispatch", json={
            "vehicle_id": data["candidates"][0]["vehicle_id"], "order": order})
        assert response.status_code == 200
        commit = response.get_json()["commit"]
        assert commit["container_type"] == container_type
        assert client.get(f"/api/orders/{order['order_id']}").get_json()["commit"] == commit

        # Exact BLOCK boundaries are checked against the selected type,
        # including 20DC/20RF which used to switch automatically to 40ft.
        blocked = {**order, "weight_kg": limits["block_kg"]}
        from unittest.mock import patch
        with patch.object(engine,
                          "recommend", side_effect=AssertionError("BLOCK must not rank vehicles")):
            result = client.post("/api/recommend", json=blocked).get_json()
            assert result["container"]["container_type"] == container_type
            assert result["status"] == "BLOCK" and result["candidates"] == []
        denied = client.post("/api/dispatch", json={
            "vehicle_id": commit["vehicle_id"], "order": blocked})
        assert denied.status_code == 409
        below = client.post("/api/container", json={**order, "weight_kg": limits["block_kg"] - 1}).get_json()
        assert below["gate"]["status"] == ("WARN" if limits["warn_kg"] else "OK")
        if limits["warn_kg"]:
            warning = client.post("/api/container", json={**order, "weight_kg": limits["warn_kg"]}).get_json()
            assert warning["gate"]["status"] == "WARN"
    store.clear()


def test_missing_invalid_type_never_falls_back_to_automatic_selection():
    client = app.test_client()
    for container_type in (None, "", "99DC", ["20DC"], 20):
        order = {**SAMPLE, "container_type": container_type}
        for endpoint in ("/api/container", "/api/recommend"):
            response = client.post(endpoint, json=order)
            assert response.status_code == 400
            assert "container_type" in response.get_json()["error"]
        assert client.post("/api/dispatch", json={
            "vehicle_id": "test", "order": order}).status_code == 400
    legacy = {key: value for key, value in SAMPLE.items() if key != "container_type"}
    legacy.update({"refrigerated": True, "cargo_profile": "tall"})
    assert client.post("/api/container", json=legacy).status_code == 400
    normalized = client.post("/api/container", json={**SAMPLE, "container_type": " 40rf "}).get_json()
    assert normalized["container"]["container_type"] == "40RF"
    # Deprecated auto-selection fields must not change a supplied type.
    result = client.post("/api/container", json={
        **SAMPLE, "container_type": "40DC", "liquid": True, "refrigerated": True,
        "cargo_profile": "top_open", "special_cargo": True}).get_json()
    assert result["container"]["container_type"] == "40DC"


def test_invalid_requests_return_validation_errors():
    client = app.test_client()
    for invalid in (["bad"], "bad"):
        for endpoint in ("/api/container", "/api/recommend", "/api/dispatch"):
            assert client.post(endpoint, json=invalid).status_code == 400
    for weight in (True, 0, -1, "NaN", "Infinity", None):
        assert client.post("/api/container", json={**SAMPLE, "weight_kg": weight}).status_code == 400


def test_health_and_model_recommendation():
    store.clear()
    client = app.test_client()
    assert client.get("/api/health").status_code == 200
    response = client.post("/api/recommend", json=SAMPLE)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "RECOMMENDED"
    assert data["container"]["container_type"] == "20DC"
    assert data["gate"]["status"] == "OK"
    assert data["evaluated_vehicle_count"] > 0
    assert data["feasible_candidate_count"] > 0
    assert data["minimum_arrival_slack_min"] == 25
    assert data["maximum_work_gap_h"] == 24
    first = data["candidates"][0]
    available = datetime.fromisoformat(first["available_time"])
    expected_arrival = available + timedelta(hours=first["empty_time_h"])
    actual_arrival = datetime.fromisoformat(first["estimated_arrival_time"])
    assert abs((actual_arrival - expected_arrival).total_seconds()) < 2
    expected_slack = (datetime.fromisoformat(SAMPLE["work_time"]) - actual_arrival).total_seconds() / 60
    assert abs(first["arrival_slack_min"] - expected_slack) < 1
    assert 0 < first["work_gap_h"] <= 24
    assert first["arrival_slack_min"] >= 25
    ranking = [(c["empty_distance_km"], c["arrival_slack_delta_min"], c["work_gap_h"], c["vehicle_id"]) for c in data["candidates"]]
    assert ranking == sorted(ranking)
    assert "objective_cost" not in first


def test_block_stops_recommendation():
    client = app.test_client()
    blocked = {**SAMPLE, "weight_kg": 26_740}
    response = client.post("/api/recommend", json=blocked)
    data = response.get_json()
    assert data["status"] == "BLOCK"
    assert data["candidates"] == []


def test_dispatch_commit_updates_state_and_prevents_duplicate_assignment():
    store.clear()
    client = app.test_client()
    recommendation = client.post("/api/recommend", json=SAMPLE).get_json()
    selected = recommendation["candidates"][0]["vehicle_id"]
    order = {**SAMPLE, "order_id": recommendation["order_id"]}
    confirmed = client.post("/api/dispatch", json={"vehicle_id": selected, "order": order})
    assert confirmed.status_code == 200
    assert confirmed.get_json()["commit"]["dropoff_rep"] == "부산신항"
    next_result = client.post("/api/recommend", json={**SAMPLE, "order_id": "ORD-WEB-NEXT"}).get_json()
    assert all(item["vehicle_id"] != selected for item in next_result["candidates"])
    duplicate = client.post("/api/dispatch", json={"vehicle_id": selected, "order": order})
    assert duplicate.status_code == 409
    store.clear()


def test_revised_evaluation_metrics_api():
    store.clear()
    client = app.test_client()
    empty = client.get("/api/evaluation").get_json()["metrics"]
    assert empty["Minimum_Arrival_Slack_min"] == 25
    assert empty["Maximum_Work_Gap_h"] == 24
    assert empty["전체주문수"] == 0

    recommendation = client.post("/api/recommend", json=SAMPLE).get_json()
    vehicle = recommendation["candidates"][0]["vehicle_id"]
    order = {**SAMPLE, "order_id": recommendation["order_id"]}
    assert client.post("/api/dispatch", json={"vehicle_id": vehicle, "order": order}).status_code == 200
    metrics = client.get("/api/evaluation").get_json()["metrics"]
    assert metrics["추천성공주문수"] == 1
    assert metrics["평균추천작업간격_h"] is not None
    assert metrics["평균도착여유_min"] >= 25
    store.clear()

