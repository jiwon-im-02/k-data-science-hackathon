"""Export dispatch candidate audit workbooks for specific order times."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app import engine, prepare_order, store  # noqa: E402
from config import FIXED_HISTORY_WORKBOOK  # noqa: E402


OUTPUT_PATH = BASE_DIR / "data" / "runtime" / "후보차량_검증_부산신항_인천신항_20260324.xlsx"


def as_dt(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def load_source_index() -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    workbook = load_workbook(FIXED_HISTORY_WORKBOOK, read_only=True, data_only=True)
    try:
        sheet = workbook["01_전체스케줄_타겟표시"]
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value) if value is not None else "" for value in next(rows)]
        index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for excel_row, values in enumerate(rows, start=2):
            row = dict(zip(headers, values))
            vehicle = row.get("차량")
            event_time = row.get("작업일시")
            dropoff_rep = row.get("현재하차지_rep")
            if not vehicle or not isinstance(event_time, datetime) or not dropoff_rep:
                continue
            key = (str(vehicle).strip(), event_time.replace(microsecond=0).isoformat(), str(dropoff_rep).strip())
            row["_excel_row"] = excel_row
            index[key].append(row)
        for matches in index.values():
            matches.sort(key=lambda item: (
                str(item.get("재배차대상여부") or "").strip().upper() == "O",
                item.get("_excel_row") or 0,
            ))
        return index
    finally:
        workbook.close()


def latest_job_for_candidate(vehicle_id: str, available_time: str, dropoff_rep: str) -> dict[str, Any] | None:
    jobs = engine.vehicles[vehicle_id]["jobs"]
    for job in reversed(jobs):
        if (
            not job["is_target"]
            and job["started_at"] == available_time
            and job["dropoff_rep"] == dropoff_rep
        ):
            return job
    return None


def build_result(work_time: str) -> dict[str, Any]:
    payload = {
        "order_id": f"AUDIT-{work_time.replace(':', '').replace('-', '').replace('T', '-')}",
        "pickup": "부산신항",
        "dropoff": "인천신항",
        "work_time": work_time,
        "cargo_type": "일반 화물",
        "weight_kg": 18_000,
        "container_type": "20DC",
    }
    cleaned, container, gate = prepare_order(payload)
    order = engine.build_order(cleaned, container["container_type"])
    result = engine.recommend(order, store.commits(), top_n=len(engine.vehicles))
    result["container"] = container
    result["gate"] = gate
    return result


def candidate_rows(result: dict[str, Any], source_index: dict[tuple[str, str, str], list[dict[str, Any]]]) -> list[list[Any]]:
    order_time = as_dt(result["order"]["order_time"])
    rows: list[list[Any]] = []
    for item in result["candidates"]:
        vehicle_id = item["vehicle_id"]
        latest = latest_job_for_candidate(vehicle_id, item["available_time"], item["available_location"])
        key = (vehicle_id, item["available_time"], item["available_location"])
        source_matches = source_index.get(key, [])
        source_row = {}
        if source_matches:
            latest_pickup = latest.get("pickup_rep") if latest else None
            source_row = next(
                (
                    row for row in source_matches
                    if str(row.get("재배차대상여부") or "").strip().upper() != "O"
                    and (latest_pickup is None or row.get("현재상차지_rep") == latest_pickup)
                ),
                source_matches[0],
            )
        available_dt = as_dt(item["available_time"])
        eta_dt = as_dt(item["estimated_arrival_time"])
        reason = (
            f"{item['available_location']} 기준, 공차 {item['empty_distance_km']:.2f}km/"
            f"{item['empty_time_min']}분, 요청시각 대비 {item['arrival_slack_min']}분 여유"
        )
        if item["work_gap_h"] == 24:
            reason += " (24시간 한계값)"
        rows.append([
            item["rank"],
            vehicle_id,
            item["owner_type"],
            item["status"],
            item["state_source"],
            source_row.get("_excel_row"),
            available_dt,
            source_row.get("차량내_작업순번"),
            source_row.get("차량내_시각순번"),
            latest.get("source_order_id") if latest else None,
            source_row.get("재배차대상여부"),
            source_row.get("상차지"),
            source_row.get("하차지"),
            latest.get("pickup_rep") if latest else source_row.get("현재상차지_rep"),
            item["available_location"],
            item["current_location"],
            item["current_route"] or "",
            order_time,
            item["work_gap_h"],
            item["work_gap_min"],
            item["empty_distance_km"],
            item["empty_time_h"],
            item["empty_time_min"],
            eta_dt,
            item["arrival_slack_min"],
            item["estimated_finish_time"],
            result["order"]["loaded_distance_km"],
            result["order"]["loaded_time_min"],
            reason,
        ])
    return rows


def style_sheet(sheet, table_rows: int, table_cols: int) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(table_cols)}{table_rows + 1}"
    sheet.sheet_view.showGridLines = False

    header_fill = PatternFill("solid", fgColor="1F2937")
    header_font = Font(color="FFFFFF", bold=True)
    border = Border(bottom=Side(style="thin", color="D1D5DB"))
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row in sheet.iter_rows(min_row=2, max_row=table_rows + 1, max_col=table_cols):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=False)

    widths = {
        "A": 8, "B": 12, "C": 10, "D": 11, "E": 18, "F": 12, "G": 19, "H": 13,
        "I": 13, "J": 18, "K": 12, "L": 26, "M": 26, "N": 16, "O": 16, "P": 16,
        "Q": 18, "R": 19, "S": 12, "T": 13, "U": 14, "V": 12, "W": 13, "X": 19,
        "Y": 13, "Z": 20, "AA": 15, "AB": 15, "AC": 58,
    }
    for col, width in widths.items():
        sheet.column_dimensions[col].width = width

    for col in ("G", "R", "X"):
        for cell in sheet[col][1:]:
            cell.number_format = "yyyy-mm-dd hh:mm"
    for col in ("S", "V"):
        for cell in sheet[col][1:]:
            cell.number_format = "0.0000"
    for col in ("U",):
        for cell in sheet[col][1:]:
            cell.number_format = "#,##0.00"
    for col in ("T", "W", "Y", "AA", "AB"):
        for cell in sheet[col][1:]:
            cell.number_format = "#,##0"


def write_candidate_sheet(workbook: Workbook, name: str, result: dict[str, Any], source_index: dict[tuple[str, str, str], list[dict[str, Any]]]) -> None:
    sheet = workbook.create_sheet(name)
    headers = [
        "추천순위", "차량ID", "자차/용차", "상태", "상태출처", "원본행번호", "마지막기준작업일시",
        "차량내_작업순번", "차량내_시각순번", "source_order_id", "재배차대상여부",
        "원본상차지", "원본하차지", "마지막상차대표지", "마지막하차대표지", "현재위치",
        "현재작업구간", "요청상차일시", "작업간격_h", "작업간격_분", "공차거리_km",
        "공차시간_h", "공차시간_분", "예상도착시각", "도착여유_분", "예상운송완료시각",
        "적재거리_km", "적재시간_분", "추천근거",
    ]
    rows = candidate_rows(result, source_index)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    style_sheet(sheet, len(rows), len(headers))


def write_summary(workbook: Workbook, results: dict[str, dict[str, Any]]) -> None:
    sheet = workbook.active
    sheet.title = "요약"
    sheet.sheet_view.showGridLines = False
    sheet["A1"] = "부산신항 → 인천신항 후보 차량 검증"
    sheet["A1"].font = Font(size=16, bold=True, color="111827")
    sheet["A2"] = "화물: 일반 화물 / 18,000kg / 지정 컨테이너 20DC / 중량 Gate OK"
    sheet["A2"].font = Font(color="4B5563")
    sheet["A4"] = "요청시각"
    sheet["B4"] = "후보수"
    sheet["C4"] = "부산신항 기준 후보"
    sheet["D4"] = "제외: 작업간격"
    sheet["E4"] = "제외: 도착여유"
    sheet["F4"] = "제외: 상태없음"
    for cell in sheet[4]:
        cell.fill = PatternFill("solid", fgColor="1F2937")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")

    for idx, (label, result) in enumerate(results.items(), start=5):
        origins = Counter(item["available_location"] for item in result["candidates"])
        excluded = result["excluded_reasons"]
        sheet.cell(idx, 1).value = result["order"]["order_time"].replace("T", " ")
        sheet.cell(idx, 2).value = result["feasible_candidate_count"]
        sheet.cell(idx, 3).value = origins.get("부산신항", 0)
        sheet.cell(idx, 4).value = excluded.get("work_gap_fail", 0)
        sheet.cell(idx, 5).value = excluded.get("arrival_slack_fail", 0)
        sheet.cell(idx, 6).value = excluded.get("state_unknown", 0)

    notes = [
        "판정 방식: 요청시각 이전의 마지막 비타겟 작업을 차량의 기준 상태로 사용합니다.",
        "작업간격_h = 요청상차일시 - 마지막기준작업일시이며, 0 < 작업간격_h <= 24 조건을 통과해야 합니다.",
        "예상도착시각 = 마지막기준작업일시 + 기준 위치에서 부산신항까지의 공차시간입니다.",
        "도착여유_분이 25분 이상인 차량만 후보입니다.",
        "따라서 3월 19일 마지막 작업 차량은 3월 24일 11:00 요청에서는 24시간 제한으로 제외되는 것이 정상입니다.",
        "웹 모델은 현재 수정 모델 설정에 맞춰 이후 FIXED 작업 복귀 제약을 사용하지 않습니다.",
    ]
    sheet["A8"] = "검증 메모"
    sheet["A8"].font = Font(bold=True)
    for offset, note in enumerate(notes, start=9):
        sheet.cell(offset, 1).value = note

    for col, width in {"A": 30, "B": 12, "C": 18, "D": 16, "E": 16, "F": 16}.items():
        sheet.column_dimensions[col].width = width


def main() -> None:
    source_index = load_source_index()
    results = {
        "11시_요청기준": build_result("2026-03-24T11:00"),
        "23시_비교기준": build_result("2026-03-24T23:00"),
    }

    workbook = Workbook()
    write_summary(workbook, results)
    for name, result in results.items():
        write_candidate_sheet(workbook, name, result, source_index)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(OUTPUT_PATH)
    print(OUTPUT_PATH)
    for name, result in results.items():
        origins = Counter(item["available_location"] for item in result["candidates"])
        print(name, result["feasible_candidate_count"], dict(origins))


if __name__ == "__main__":
    main()

