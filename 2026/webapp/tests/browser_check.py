"""Real-browser acceptance checks. Uses a temporary server and dispatch state.

Install the optional dependency with: python -m pip install -r requirements-dev.txt
Run: python tests/browser_check.py
Chrome must be installed. No model/API response is mocked.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="routeone-browser-") as temporary:
        os.environ["DISPATCH_STATE_FILE"] = str(Path(temporary) / "dispatch_state.json")
        from app import app
        from playwright.sync_api import sync_playwright, expect
        from werkzeug.serving import make_server

        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        screenshots = PROJECT_DIR / "docs" / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        errors = []
        results = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                context = browser.new_context(viewport={"width":1440, "height":1050}, locale="ko-KR", timezone_id="Asia/Seoul")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page.locator('[name="container_type"]:checked')).to_have_count(0)
                page.locator("#recommendButton").click()
                assert "/recommendations" not in page.url
                for kind in ("20DC", "20RF", "20TK", "40DC", "40HC", "40OT", "40RF", "45HC"):
                    page.locator(f'[name="container_type"][value="{kind}"]').check()
                    expect(page.locator("#containerType")).to_have_text(kind)
                page.locator("#container20DC").check()
                expect(page.locator("#containerType")).to_have_text("20DC")
                expect(page.locator("#locations option")).not_to_have_count(0)
                expect(page.locator("#gateBadge")).to_have_text("OK")
                page.screenshot(path=str(screenshots / "01-request-desktop.png"), full_page=True)
                assert page.locator("#candidateList").count() == 0
                with page.expect_response(lambda response: response.url.endswith("/api/recommend")) as response_info:
                    page.get_by_role("button", name="추천 차량 조회").click()
                    page.wait_for_url("**/recommendations")
                result = response_info.value.json()
                expect(page.locator(".candidate-card")).to_have_count(len(result["candidates"]))
                assert page.locator(".candidate-card").first.evaluate("el => el.clientHeight > 250"), "Candidate details must not be compressed by the scrolling container"
                first = result["candidates"][0]
                assert page.locator(".vehicle-name").first.inner_text() == first["vehicle_id"]
                assert str(first["rank"]) == page.locator(".rank-num").first.inner_text()
                expect(page.locator("#routeStatus")).not_to_contain_text("조회 중", timeout=15000)
                expect(page.locator(".leaflet-marker-icon")).not_to_have_count(0)
                route_status = page.locator("#routeStatus").inner_text()
                tile_count = page.locator(".leaflet-tile-loaded").count()
                page.screenshot(path=str(screenshots / "02-results-desktop.png"), full_page=True)
                results.append({"check":"real_model_and_map","candidates":result["feasible_candidate_count"],"first":first["vehicle_id"],"route_status":route_status,"loaded_tiles":tile_count})

                # A filter that hides the selection must also hide the confirmation dock.
                opposite = "용차" if first["owner_type"] == "자차" else "자차"
                page.locator(f'[data-filter="{opposite}"]').click()
                expect(page.locator("#dispatchDock")).to_be_hidden()
                page.locator('[data-filter="all"]').click()
                chosen = result["candidates"][1] if len(result["candidates"]) > 1 else first
                page.get_by_role("button", name=f'{chosen["vehicle_id"]} 배차 선택', exact=True).click()
                expect(page.locator("#selectedVehicle")).to_contain_text(chosen["vehicle_id"])
                page.locator("#openConfirm").click()
                expect(page.locator("#confirmDialog")).to_be_visible()
                page.screenshot(path=str(screenshots / "03-confirm-dialog.png"))
                page.locator("#cancelConfirm").click()
                expect(page.locator("#confirmDialog")).not_to_be_visible()
                page.locator("#openConfirm").click()
                page.locator("#confirmDispatch").click()
                expect(page.locator("#successState")).to_be_visible()
                expect(page.locator("#successDetails")).to_contain_text(chosen["vehicle_id"])
                page.reload()
                expect(page.locator("#successState")).to_be_visible()
                page.screenshot(path=str(screenshots / "04-confirmed.png"), full_page=True)
                results.append({"check":"select_confirm_reload","passed":True})

                # Verify model state is really updated, not only a UI success message.
                payload = {"pickup":"의왕ICD","dropoff":"부산신항","work_time":"2026-03-18T09:00","cargo_type":"일반 화물","container_type":"20DC","weight_kg":18000}
                next_result = context.request.post(base + "/api/recommend", data=payload).json()
                assert all(c["vehicle_id"] != chosen["vehicle_id"] for c in next_result["candidates"])
                results.append({"check":"confirmed_vehicle_excluded_from_next_request","passed":True})

                page.goto(base)
                page.locator("#container20DC").check()
                page.locator("#weight").fill("21500")
                expect(page.locator("#gateBadge")).to_have_text("WARN")
                page.locator("#recommendButton").click()
                expect(page.locator("#gateDialog")).to_be_visible()
                expect(page.locator("#continueWarning")).to_be_visible()
                page.locator("#continueWarning").click()
                page.wait_for_url("**/recommendations")
                expect(page.locator("#warningBanner")).to_be_visible()
                expect(page.locator(".candidate-card").first).to_be_visible()
                page.get_by_role("link", name="운송 정보 수정", exact=True).first.click()
                expect(page.locator("#weight")).to_have_value("21500")
                expect(page.locator("#container20DC")).to_be_checked()
                page.locator("#weight").fill("21750")
                expect(page.locator("#containerType")).to_have_text("20DC")
                expect(page.locator("#gateBadge")).to_have_text("BLOCK")
                page.locator("#recommendButton").click()
                expect(page.locator("#gateDialog")).to_be_visible()
                expect(page.locator("#continueWarning")).to_be_hidden()
                assert "/recommendations" not in page.url
                page.locator("#editGateInput").click()
                expect(page.locator("#gateDialog")).not_to_be_visible()
                results.append({"check":"warn_block_and_edit_restore","passed":True})
                page.locator("#weight").fill("18000")
                page.locator("#workTime").fill("2030-03-18T09:00")
                page.locator("#recommendButton").click()
                page.wait_for_url("**/recommendations")
                expect(page.locator("#emptyState")).to_be_visible()
                expect(page.locator("#dispatchDock")).to_be_hidden()
                results.append({"check":"no_feasible_candidates","passed":True})

                page.goto(base)
                page.locator("#container40HC").check()
                page.locator("#pickup").fill("부산북항")
                page.locator("#dropoff").fill("의왕ICD")
                with page.expect_response(lambda response: response.url.endswith("/api/recommend")) as movement_response:
                    page.locator("#recommendButton").click()
                    page.wait_for_url("**/recommendations")
                moving_result = movement_response.value.json()
                assert moving_result["order"]["container_type"] == "40HC"
                moving = next(c for c in moving_result["candidates"] if c["empty_distance_km"] > 0)
                page.get_by_role("button", name=f'{moving["vehicle_id"]} 배차 선택', exact=True).click()
                expect(page.locator("#emptyDistance")).to_contain_text(str(moving["empty_distance_km"]))
                expect(page.locator("#routeStatus")).not_to_contain_text("조회 중", timeout=15000)
                expect(page.locator('.leaflet-overlay-pane path[stroke="#ce8b49"]')).not_to_have_count(0)
                page.screenshot(path=str(screenshots / "07-empty-route.png"), full_page=True)
                results.append({"check":"nonzero_empty_route_selection","distance_km":moving["empty_distance_km"],"passed":True})

                mobile = browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,locale="ko-KR")
                phone = mobile.new_page()
                phone.on("pageerror", lambda error: errors.append(str(error)))
                phone.goto(base)
                phone.locator("#container20DC").check()
                expect(phone.locator("#containerType")).to_have_text("20DC")
                phone.screenshot(path=str(screenshots / "05-request-mobile.png"), full_page=True)
                assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
                phone.locator("#recommendButton").click()
                phone.wait_for_url("**/recommendations")
                expect(phone.locator(".candidate-card").first).to_be_visible()
                expect(phone.locator("#routeStatus")).not_to_contain_text("조회 중",timeout=15000)
                assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
                phone.screenshot(path=str(screenshots / "06-results-mobile.png"), full_page=True)
                results.append({"check":"mobile_no_horizontal_overflow","passed":True})

                # External map outages must never block actual local recommendations.
                offline_map = browser.new_context(viewport={"width":1280,"height":900})
                offline_map.route("https://tile.openstreetmap.org/**", lambda route: route.abort())
                offline_map.route("https://router.project-osrm.org/**", lambda route: route.abort())
                offline_page = offline_map.new_page()
                offline_page.on("pageerror", lambda error: errors.append(str(error)))
                offline_page.goto(base)
                offline_page.locator("#container20DC").check()
                expect(offline_page.locator("#containerType")).to_have_text("20DC")
                offline_page.locator("#recommendButton").click()
                offline_page.wait_for_url("**/recommendations")
                expect(offline_page.locator(".candidate-card").first).to_be_visible()
                expect(offline_page.locator("#routeStatus")).to_contain_text("연결선", timeout=15000)
                expect(offline_page.locator("#tileNotice")).to_be_visible()
                expect(offline_page.locator("#openConfirm")).to_be_enabled()
                results.append({"check":"map_outage_does_not_block_recommendation","passed":True})

                # A new browser context has no request draft.
                direct_context = browser.new_context()
                direct = direct_context.new_page()
                direct.goto(base + "/recommendations")
                expect(direct.locator("#pageError")).to_contain_text("조회할 운송건이 없습니다")
                results.append({"check":"direct_result_url_without_draft","passed":True})
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
        print(json.dumps({"checks":results,"javascript_errors":errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
