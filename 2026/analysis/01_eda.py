# -*- coding: utf-8 -*-
"""예선 EDA 재현: 전처리_데이터.xlsx 기반 통계 산출 -> stats.json"""
import json
import numpy as np
import pandas as pd

pd.set_option('display.max_columns', None)

SRC = r"./코드\전처리_데이터.xlsx"
OUT = r"./분석\stats.json"

df = pd.read_excel(SRC)
df['용차_bin'] = (df['용차'] == '용차').astype(int)
df['dow'] = df['작업일시'].dt.dayofweek  # 0=Mon
df['hour'] = pd.to_datetime(df['작업시간'], format='%H:%M').dt.hour
df['날짜'] = df['작업일자'].dt.date

stats = {}

# ---- 0-1 기본 구조 ----
stats['n_rows'] = int(len(df))
stats['date_min'] = str(df['작업일자'].min().date())
stats['date_max'] = str(df['작업일자'].max().date())
stats['n_days'] = int(df['날짜'].nunique())
stats['수출입_ratio'] = df['수출입'].value_counts(normalize=True).round(4).to_dict()
stats['용차_ratio'] = df['용차'].value_counts(normalize=True).round(4).to_dict()
stats['n_차량'] = int(df['차량'].nunique())
stats['n_화주'] = int(df['화주'].nunique())
stats['n_상차지'] = int(df['상차지_전처리'].nunique())
stats['n_하차지'] = int(df['하차지_전처리'].nunique())
stats['n_라인'] = int(df['라인'].nunique())

# ---- 0-2 결측 ----
stats['na_중량_pct'] = round(df['중량'].isna().mean() * 100, 1)
stats['na_중량_수출'] = round(df.loc[df['수출입'] == '수출', '중량'].isna().mean() * 100, 1)
stats['na_중량_수입'] = round(df.loc[df['수출입'] == '수입', '중량'].isna().mean() * 100, 1)
stats['na_라인'] = int(df['라인'].isna().sum())
stats['na_컨테이너'] = int(df['컨테이너'].isna().sum())

# 중량 단위 혼재 (<100)
low_mask = df['중량'].notna() & (df['중량'] < 100)
stats['중량_저값_pct'] = round(low_mask.mean() * 100, 1)
stats['중량_저값_타입별'] = (
    df.assign(low=low_mask).groupby('타입')['low'].mean().mul(100).round(1).sort_values(ascending=False).head(8).to_dict()
)

# ---- 지역=하차지 동일 비중 (전처리 완료본은 상차지=하차지 케이스가 남아있는지 체크) ----
same_node = (df['상차지_전처리'] == df['하차지_전처리'])
stats['same_node_pct'] = round(same_node.mean() * 100, 1)
stats['same_node_pct_수입'] = round(same_node[df['수출입'] == '수입'].mean() * 100, 1)
stats['same_node_pct_수출'] = round(same_node[df['수출입'] == '수출'].mean() * 100, 1)

# ---- 차량 ID 누수 검증 ----
veh = df.groupby('차량')['용차_bin'].agg(['mean', 'count'])
stats['차량_전건용차_pct'] = round((veh['mean'] == 1).mean() * 100, 1)
stats['차량_전건자차_pct'] = round((veh['mean'] == 0).mean() * 100, 1)
stats['차량_혼재_pct'] = round(((veh['mean'] > 0) & (veh['mean'] < 1)).mean() * 100, 1)
stats['차량_1회등장_용차율'] = round(veh.loc[veh['count'] == 1, 'mean'].mean() * 100, 1)
stats['차량_20회초과_용차율'] = round(veh.loc[veh['count'] > 20, 'mean'].mean() * 100, 1)

# ---- 캐파 부하 vs 용차율 상관 (일자 단위) ----
daily = df.groupby('날짜').agg(
    총오더=('용차_bin', 'size'),
    용차율=('용차_bin', 'mean'),
    자차대수=('차량', lambda s: df.loc[s.index].loc[df.loc[s.index, '용차'] == '자차', '차량'].nunique())
).reset_index()
# load_ratio: 당일 총오더 / 당일 가동 자차대수(단순 상관 확인용, 누수 아님 - 상관관계 검증 목적)
daily['load_ratio'] = daily['총오더'] / daily['자차대수'].replace(0, np.nan)
stats['corr_물량_용차율'] = round(daily['총오더'].corr(daily['용차율']), 3)
stats['corr_load_ratio_용차율'] = round(daily['load_ratio'].corr(daily['용차율']), 3)

# ---- 상차지별 용차율 (100건 이상) ----
grp = df.groupby('상차지_전처리')['용차_bin'].agg(['mean', 'count'])
grp = grp[grp['count'] >= 100].sort_values('mean', ascending=False)
stats['상차지별_용차율_top10'] = [
    {'상차지': idx, '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for idx, r in grp.head(10).iterrows()
]
stats['상차지별_용차율_bottom5'] = [
    {'상차지': idx, '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for idx, r in grp.tail(5).iterrows()
]
stats['상차지별_용차율_전체'] = [
    {'상차지': idx, '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for idx, r in grp.iterrows()
]

# ---- 시간대별 용차율 ----
hour_grp = df.groupby('hour')['용차_bin'].agg(['mean', 'count']).reset_index()
stats['시간대별_용차율'] = [
    {'hour': int(r['hour']), '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for _, r in hour_grp.iterrows()
]

# ---- 요일별 용차율 ----
dow_names = ['월', '화', '수', '목', '금', '토', '일']
dow_grp = df.groupby('dow')['용차_bin'].agg(['mean', 'count']).reset_index()
stats['요일별_용차율'] = [
    {'요일': dow_names[int(r['dow'])], '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for _, r in dow_grp.iterrows()
]

# ---- 타입별 용차율 ----
type_grp = df.groupby('타입')['용차_bin'].agg(['mean', 'count']).reset_index()
type_grp = type_grp[type_grp['count'] >= 30].sort_values('mean', ascending=False)
stats['타입별_용차율'] = [
    {'타입': r['타입'], '건수': int(r['count']), '용차율': round(r['mean'] * 100, 1)}
    for _, r in type_grp.iterrows()
]

# ---- 화주별 용차율 분포 (20건 이상) ----
cust = df.groupby('화주')['용차_bin'].agg(['mean', 'count'])
cust = cust[cust['count'] >= 20]
stats['n_화주_20건이상'] = int(len(cust))
stats['화주_용차율_분위'] = {
    'p5': round(cust['mean'].quantile(0.05) * 100, 1),
    'p50': round(cust['mean'].quantile(0.50) * 100, 1),
    'p95': round(cust['mean'].quantile(0.95) * 100, 1),
}

# ---- 일자별 시계열 (용차율, 물량) ----
stats['일자별_시계열'] = [
    {'날짜': str(r['날짜']), '총오더': int(r['총오더']), '용차율': round(r['용차율'] * 100, 1)}
    for _, r in daily.sort_values('날짜').iterrows()
]

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print("saved:", OUT)
print(json.dumps({k: v for k, v in stats.items() if not isinstance(v, list)}, ensure_ascii=False, indent=2))
