# 수정 모델 분석 및 웹 연동 기준

## 1. 최종 원본

현재 웹 엔진의 기준은 `model/original_model_code_revised.txt`이며 원본 파일명은 `모델 코드_수정.txt`이다. 입력은 다음 세 자료다.

- `모델링_최종후보표.xlsx`: 주문 ID, 작업시각, 대표 상·하차지, 예상 완료시각, 실제 차량·공차거리
- `순차모델링_FIXED스케줄.xlsx`: 차량, 작업일시, 대표 하차지, 자차/용차, 재배차 대상 여부
- `순차모델링_OD캐시.xlsx`: 대표 위치 쌍, 도로거리(km), 예상시간(h)

파일명에 FIXED가 포함되지만 수정 모델은 `01_전체스케줄_타겟표시`의 과거 이력만 상태 복원에 사용한다. 미래 FIXED 일정은 사용하지 않는다.

## 2. 최종 후보 조건

수정 코드의 계산을 그대로 적용한다.

```text
Work Gap = Order Time - Vehicle Available Time
0 < Work Gap <= 24시간

Estimated Arrival = Vehicle Available Time + Empty Travel Time
Arrival Slack = Order Time - Estimated Arrival
Arrival Slack >= 25분
```

중량은 Objective에 포함하지 않고 기존과 동일하게 `OK / WARN / BLOCK` Gate에만 사용한다.

## 3. 최종 순위

Weighted Objective Cost를 사용하지 않는다. Hard Constraint를 통과한 차량을 다음 순서로 정렬한다.

1. 공차거리 최소
2. 도착여유가 25분에 가까운 순
3. 작업 간격이 짧은 순
4. 차량 ID 오름차순

미래 FIXED 복귀 제약, Fallback Cost, MILP도 사용하지 않는다.

## 4. Stateful 상태 갱신

확정된 차량은 주문 예상 완료시각에 하차지에서 다시 가용한 것으로 저장한다. 이후 주문에서는 관측 이력과 웹 확정 상태 중 더 최신인 상태를 사용한다. 동일 시각에 이미 확정된 차량은 완료시각이 미래이므로 Work Gap 조건에서 제외되어 중복 배차되지 않는다.

## 5. 웹 모듈

- `model/data_builder_revised.py`: FIXED 과거 상태 이력과 OD를 경량 JSON으로 변환
- `model/dispatch_model.py`: 25분 Arrival Slack, 24시간 Work Gap, 거리 우선 순위
- `services/container_service.py`: 요청서에 지정된 컨테이너 타입 검증 (자동 추정 없음)
- `services/weight_gate.py`: 원본 중량 Gate
- `services/state_store.py`: 배차 확정 상태 영속화
- `services/evaluation_service.py`: 수정된 평가 지표를 Python 표준 자료구조로 구현
- `app.py`: 입력 검증, 추천, 확정, 평가 API

## 6. 변경된 평가 지표

수정 코드에 맞춰 다음 지표를 제공한다.

- Coverage: 전체/BLOCK/추천대상/추천성공/후보없음 및 추천성공률
- 후보: 평균·중앙값 후보차량 수
- Work Gap: 평균·중앙값·Q95
- 공차: 평균·중앙값 거리, 0km 비율, 평균·중앙값 시간
- Arrival Slack: 평균·중앙값·Q25·Q75
- 주문 수준: 실제/추천 공차거리 합, 절감률, 개선 주문 비율, 주문별 절감률
- 차량 수준: 비교 차량 수, 개선 차량 비율, 평균·중앙값·Q25·Q75 차량별 절감률

웹 확정 주문에는 실제 배차 공차거리가 없으므로 실제 비교 지표는 값이 제공된 경우에만 계산한다. 세션 평가는 `GET /api/evaluation`에서 확인할 수 있다.

## 지정 컨테이너 입력 (2026-09-10)

웹 입력은 `container_type`을 필수로 받는다. 지정 타입은 중량 변화에도 유지하고, 해당 타입의 Gate로 주문을 통과/경고/차단한다. 화물명은 선택 설명이다. 20DC에서 40DC로 바꾸는 등의 자동 선택 로직은 제거했다. 원본 보관 파일의 실험 코드는 수정하지 않는다.

원본 이력의 과거 운송 타입은 장비 호환성 목록이 아니다. 현재 차량 마스터에는 장착 샤시·운송 가능 컨테이너 타입 데이터가 없어 차량별 장비 호환성을 자동 검증하지 않는다. Gate 통과 주문의 차량 순위는 기존 가용시각·OD 거리·시간 모델로 계산한다. 이 구분은 README와 배차 확정 화면에 명시한다.
