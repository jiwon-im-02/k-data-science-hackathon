# -*- coding: utf-8 -*-
"""
신규 오더 실시간 용차 판정기
=============================
새로운 컨테이너 운송 오더(건)가 접수됐을 때, 이 오더가 용차로 빠질 확률을 즉시 계산하고
배차 우선순위를 추천한다. 02_model.py가 저장한 model_artifacts/ (LightGBM 모델 + 이력 룩업)를
그대로 재사용하므로, 예선 검증에 쓰인 것과 동일한 모델로 신규 건을 판정한다.

사용법
------
1) 이 파일을 import 해서 score_new_order() 를 호출하거나,
2) 하단 __main__ 블록의 예시처럼 CLI로 바로 실행해 데모를 확인한다.

신규 오더가 들어올 때마다 아래 필드를 채워서 넘기면 된다:
    order = {
        "상차지_전처리": "인천항 인천E1",   # 필수 (전처리 규칙과 동일한 표기)
        "하차지_전처리": "경기도 화성시",   # 필수
        "화주": "화주0288",                 # 없으면 "UNK" (신규 화주 취급, prior 적용)
        "지역": "충청남도 서산시 대산읍",   # 없으면 화주 이력에서 최빈 지역 자동 조회
        "라인": "KMD",                      # 없으면 컨테이너 번호 앞 4자리로 추정
        "컨테이너": "BEAU1234567",
        "타입": "20DC",
        "중량": 14780,                      # kg, 모르면 None (타입별 중앙값 대체)
        "수출입": "수입",
        "작업일자": "2026-04-06",           # YYYY-MM-DD
        "작업시간": "09:00",                # HH:MM
    }
    당일_컨텍스트 = {  # 선택: 그날 이미 접수된 다른 오더 수 등 실시간 운영정보 (없으면 과거 평균으로 대체)
        "day_order_n": 190, "own_fleet_capacity": 110,
    }
    result = score_new_order(order, 당일_컨텍스트)
"""
import json
import os
import re
import lightgbm as lgb
import pandas as pd
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_artifacts")

with open(os.path.join(MODEL_DIR, "lookups.json"), encoding="utf-8") as f:
    LK = json.load(f)

_TMP_MODEL = r"./lgbm_final.txt"
os.makedirs(os.path.dirname(_TMP_MODEL), exist_ok=True)
import shutil
shutil.copyfile(os.path.join(MODEL_DIR, "lgbm_final.txt"), _TMP_MODEL)
BOOSTER = lgb.Booster(model_file=_TMP_MODEL)

FEATURE_ORDER = [
    '수출입', '라인_cat', '타입_cat', 'size20', 'size40', 'is_reefer', 'w_kg', 'weight_na',
    'hour', 'dow', 'is_month_end', '상차_항만그룹', '하차_항만그룹', 'same_node',
    'day_order_n', 'own_fleet_capacity', 'load_ratio', 'terminal_day_n', 'sido_day_n',
    'hour_bucket_congestion', 'te_화주', 'te_상차지', 'te_라인', 'te_시군구', 'te_레인',
    '화주_누적물량', '레인_누적건수', '화주_최근30일용차율', 'pair_available', 'terminal_pair_available',
]
CAT_COLS = ['수출입', '라인_cat', '타입_cat', '상차_항만그룹', '하차_항만그룹']
PORT_GROUPS = LK['port_groups']


def _port_group(x):
    if not x or (isinstance(x, float) and pd.isna(x)):
        return 'ETC'
    for p in PORT_GROUPS:
        if str(x).startswith(p):
            return p
    return 'ETC'


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def build_features(order: dict, context: dict = None) -> dict:
    """오더 1건 + (선택)당일 실시간 컨텍스트 -> 학습 때와 동일한 피처 벡터"""
    context = context or {}
    상차지 = order.get('상차지_전처리') or order.get('상차지') or ''
    하차지 = order.get('하차지_전처리') or order.get('하차지') or ''
    화주 = order.get('화주') or 'UNK'
    지역 = order.get('지역') or LK['화주_최빈지역'].get(화주, '')
    시군구 = 지역.split()[1] if len(지역.split()) > 1 else ''
    타입 = order.get('타입', 'ETC')
    타입_cat = 타입 if 타입 in LK['top_types'] else 'ETC'

    라인 = order.get('라인')
    if not 라인 and order.get('컨테이너'):
        prefix = str(order['컨테이너'])[:4]
        라인 = LK['line_container_prefix_map'].get(prefix)
    라인 = 라인 or 'UNK'
    라인_cat = 라인 if 라인 in LK['top_lines'] else 'OTHER'

    hour = int(str(order.get('작업시간', '09:00')).split(':')[0])
    dow = pd.Timestamp(order.get('작업일자', pd.Timestamp.today().strftime('%Y-%m-%d'))).dayofweek
    day = pd.Timestamp(order.get('작업일자', pd.Timestamp.today().strftime('%Y-%m-%d'))).day

    상차_항만그룹 = _port_group(상차지)
    하차_항만그룹 = _port_group(하차지)
    레인 = 상차_항만그룹 + '__' + 시군구

    중량 = order.get('중량')
    weight_na = 1 if 중량 is None else 0
    w_kg = float(중량) if 중량 is not None else LK['default_w_kg_by_type'].get(타입_cat, 15000)

    day_order_n = context.get('day_order_n', LK['default_day_order_n'])
    own_fleet_capacity = context.get('own_fleet_capacity', LK['default_own_fleet_capacity'])
    load_ratio = day_order_n / own_fleet_capacity if own_fleet_capacity else LK['default_load_ratio']
    terminal_day_n = context.get('terminal_day_n', LK['default_terminal_day_n_by_port'].get(상차_항만그룹, 50))
    sido = 지역.split()[0] if 지역 else ''
    sido_day_n = context.get('sido_day_n', LK['default_sido_day_n_by_sido'].get(sido, 30))
    hour_bucket_congestion = context.get('hour_bucket_congestion', LK['default_hour_bucket_congestion_by_hour'].get(str(hour), 100))

    pair_available = context.get('pair_available', LK['default_pair_available_by_시군구'].get(시군구, 0.5))
    terminal_pair_available = context.get('terminal_pair_available', LK['default_terminal_pair_available_by_port'].get(상차_항만그룹, 0.8))

    feats = {
        '수출입': order.get('수출입', '수입'),
        '라인_cat': 라인_cat,
        '타입_cat': 타입_cat,
        'size20': 1 if str(타입).startswith('20') else 0,
        'size40': 1 if str(타입).startswith('40') else 0,
        'is_reefer': 1 if 'RF' in str(타입) else 0,
        'w_kg': w_kg,
        'weight_na': weight_na,
        'hour': hour,
        'dow': dow,
        'is_month_end': 1 if day >= 25 else 0,
        '상차_항만그룹': 상차_항만그룹,
        '하차_항만그룹': 하차_항만그룹,
        'same_node': 1 if 상차지 == 하차지 else 0,
        'day_order_n': day_order_n,
        'own_fleet_capacity': own_fleet_capacity,
        'load_ratio': load_ratio,
        'terminal_day_n': terminal_day_n,
        'sido_day_n': sido_day_n,
        'hour_bucket_congestion': hour_bucket_congestion,
        'te_화주': LK['te_화주'].get(화주, LK['prior']),
        'te_상차지': LK['te_상차지'].get(상차지, LK['prior']),
        'te_라인': LK['te_라인'].get(라인_cat, LK['prior']),
        'te_시군구': LK['te_시군구'].get(시군구, LK['prior']),
        'te_레인': LK['te_레인'].get(레인, LK['prior']),
        '화주_누적물량': LK['화주_건수'].get(화주, 0),
        '레인_누적건수': LK['레인_건수'].get(레인, 0),
        '화주_최근30일용차율': LK['화주_최근30일용차율'].get(화주, LK['prior']),
        'pair_available': pair_available,
        'terminal_pair_available': terminal_pair_available,
    }
    return feats


def recommend_vehicle(order: dict, available_vehicles: list = None) -> dict:
    """
    이 오더에 어떤 자차를 배정할지 추천한다.

    available_vehicles: 오늘 대기 중인 자차 목록을 실제로 안다면 넘긴다.
        [{"차량": "12가1234", "최근하차지": "인천항 인천E1", "유휴시간_분": 90}, ...]
        각 차량의 '최근하차지'가 이번 오더의 상차지와 같거나 같은 항만그룹이면
        공차 없이 바로 투입 가능하므로 우선순위가 높다.
    없으면(모르면) 과거 이력에서 이 상차지를 가장 많이 뛴 자차 TOP5를 참고용으로 반환한다
    (실시간 위치가 아니라 "이 구간을 잘 아는 차량" 힌트일 뿐, 오늘 대기 여부는 보장하지 않음).
    """
    상차지 = order.get('상차지_전처리') or order.get('상차지') or ''
    상차_항만그룹 = _port_group(상차지)

    if available_vehicles:
        ranked = []
        for v in available_vehicles:
            recent = v.get('최근하차지', '')
            if recent == 상차지:
                score, reason = 2, f"최근 하차지가 상차지({상차지})와 정확히 일치 — 공차 없이 즉시 투입 가능"
            elif _port_group(recent) == 상차_항만그룹 and 상차_항만그룹 != 'ETC':
                score, reason = 1, f"최근 하차지가 같은 항만그룹({상차_항만그룹}) — 단거리 공차만 발생"
            else:
                score, reason = 0, f"최근 하차지({recent or '미상'})가 이 상차지와 무관 — 공차 이동 거리 큼"
            idle = v.get('유휴시간_분', 0) or 0
            ranked.append({'차량': v.get('차량', '?'), '점수': score, '유휴시간_분': idle, '사유': reason})
        ranked.sort(key=lambda x: (-x['점수'], -x['유휴시간_분']))
        return {'모드': '실시간(대기차량 목록 기반)', '추천': ranked[:5]}

    hist = LK['terminal_vehicle_top'].get(상차지, [])
    if not hist:
        return {'모드': '이력없음', '추천': [], '안내': '이 상차지의 자차 이력이 없습니다 — 오늘 대기 중인 자차 목록을 넘기면 실시간 추천이 가능합니다.'}
    out = []
    for h in hist:
        last = LK['own_vehicle_last_dropoff'].get(h['차량'], {})
        out.append({'차량': h['차량'], '이력_운행횟수': h['운행횟수'], '마지막_이력상_하차지': last.get('마지막하차지')})
    return {'모드': '이력기반(참고용, 오늘 대기 여부 보장 안됨)', '추천': out}


def score_new_order(order: dict, context: dict = None, available_vehicles: list = None) -> dict:
    feats = build_features(order, context)
    row = pd.DataFrame([feats])[FEATURE_ORDER]
    for c in CAT_COLS:
        row[c] = row[c].astype('category')
    prob = float(BOOSTER.predict(row, predict_disable_shape_check=True)[0])
    vehicle_rec = recommend_vehicle(order, available_vehicles)

    if prob >= 0.667:
        tier, action = '상위 10~20% 위험군', '자차 최우선 배정 — 예측대로면 실제 용차 전환율 67~92%'
    elif prob >= 0.499:
        tier, action = '상위 30% 위험군', '자차 우선 배정 권고 (실측 용차율 약 50%)'
    elif prob >= 0.31:
        tier, action = '평균 수준', '통상 배차 프로세스 진행'
    else:
        tier, action = '저위험군', '자차 캐파 부족 시 용차로 돌려도 무방'

    return {
        '용차_확률': round(prob, 4),
        '위험등급': tier,
        '추천': action,
        '차량배정': vehicle_rec,
        '참고_피처': feats,
    }


if __name__ == "__main__":
    demo_orders = [
        {
            "상차지_전처리": "인천항 인천E1", "하차지_전처리": "충청남도 서산시 대산읍",
            "화주": "화주0288", "라인": "KMD", "타입": "20DC", "중량": 14780,
            "수출입": "수입", "작업일자": "2026-04-06", "작업시간": "09:00",
        },
        {
            "상차지_전처리": "평택항 평택컨터미널(PCTC)", "하차지_전처리": "경기도 평택시",
            "화주": "화주9999(신규)", "타입": "40HC", "중량": 22000,
            "수출입": "수출", "작업일자": "2026-04-06", "작업시간": "14:00",
        },
        {
            "상차지_전처리": "의왕 부곡에이멘", "하차지_전처리": "충청남도 천안시",
            "화주": "화주0813", "타입": "20DC",
            "수출입": "수입", "작업일자": "2026-04-09", "작업시간": "08:30",
        },
    ]
    print("=" * 70)
    print("신규 오더 판정 데모 (실제 저장된 LightGBM 모델로 즉시 스코어링)")
    print("=" * 70)
    # 오더3에 대해서만 "오늘 대기 중인 자차 목록"을 안다고 가정한 실시간 매칭 데모
    live_vehicles = [
        {"차량": "12가1234", "최근하차지": "의왕 부곡에이멘", "유휴시간_분": 40},
        {"차량": "34나5678", "최근하차지": "부산신항 부산신항(PNC)", "유휴시간_분": 200},
        {"차량": "56다9012", "최근하차지": "의왕 부곡동부", "유휴시간_분": 15},
    ]

    for i, o in enumerate(demo_orders, 1):
        av = live_vehicles if i == 3 else None
        r = score_new_order(o, available_vehicles=av)
        print(f"\n[오더 {i}] {o['상차지_전처리']} / {o.get('화주')} / {o['작업일자']} {o['작업시간']}")
        print(f"  -> 용차 확률: {r['용차_확률']*100:.1f}%  |  {r['위험등급']}")
        print(f"  -> 추천: {r['추천']}")
        vr = r['차량배정']
        print(f"  -> 차량배정 [{vr['모드']}]:")
        for v in vr['추천'][:3]:
            print(f"     · {v}")
