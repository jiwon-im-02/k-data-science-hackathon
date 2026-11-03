# -*- coding: utf-8 -*-
"""
공차 판정 로직 (전처리 코드.R 맨 아래, 최신 버전) 재현
====================================================
전처리_데이터.xlsx(11,530건) 전체에 대해 추정공차 O/X를 계산하고,
팀이 최종 확정한 공차_최종_전처리_데이터.xlsx(586건, O만 필터링된 결과)와 대조 검증한다.
"""
import re
import numpy as np
import pandas as pd
import json

DATA_DIR = r"./코드"
BASE = pd.read_excel(DATA_DIR + r"\전처리_데이터.xlsx")
GT = pd.read_excel(DATA_DIR + r"\공차_최종_전처리_데이터.xlsx")  # 팀이 확정한 공차(O) 정답셋


def port_suffix(x):
    """앞 2글자를 제외한 나머지에서 첫 공백 전까지 (R의 항만구분 로직)"""
    s = str(x).strip()
    rest = s[2:].strip()
    return re.sub(r'\s.*$', '', rest)


df = BASE.copy()
df = df.sort_values(['차량', '작업일자', '작업시간']).reset_index(drop=True)

df['차량작업건수'] = df.groupby('차량')['차량'].transform('size')
# 이전하차지·공차시간_분은 이미 컬럼에 있음 (분 단위) -> 시간 단위로 변환
df['공차시간_시간'] = df['공차시간_분'] / 60

상차지_문자 = df['상차지_전처리'].astype(str).str.strip()
하차지_문자 = df['하차지_전처리'].astype(str).str.strip()
이전하차지_문자 = df['이전하차지'].astype(str).str.strip()

df['상차지_앞2'] = 상차지_문자.str[:2]
df['하차지_앞2'] = 하차지_문자.str[:2]
df['이전하차지_앞2'] = 이전하차지_문자.str[:2]

df['상차지_항만구분'] = 상차지_문자.apply(port_suffix)
df['하차지_항만구분'] = 하차지_문자.apply(port_suffix)

PORT_TYPES = {'항', '신항', '북항'}
df['동일지역_다른항만'] = (
    (df['상차지_앞2'] == df['하차지_앞2']) &
    df['상차지_항만구분'].isin(PORT_TYPES) &
    df['하차지_항만구분'].isin(PORT_TYPES) &
    (df['상차지_항만구분'] != df['하차지_항만구분'])
)

# 1단계
df['추정공차'] = np.where(
    (df['상차지_앞2'] != df['하차지_앞2']) | df['동일지역_다른항만'],
    'O', 'X'
)

# 2~5단계
cond_single = (df['추정공차'] == 'O') & (df['차량작업건수'] == 1)
cond_multi_keep = (
    (df['추정공차'] == 'O') & (df['차량작업건수'] > 1) &
    (df['이전하차지_앞2'] != df['상차지_앞2']) &
    (df['공차시간_시간'] >= 0) & (df['공차시간_시간'] <= 12)
)
cond_multi_drop = (df['추정공차'] == 'O') & (df['차량작업건수'] > 1) & ~cond_multi_keep

df.loc[cond_multi_drop, '추정공차'] = 'X'
# (cond_single, cond_multi_keep은 이미 'O' 유지이므로 별도 처리 불필요)

n_O = int((df['추정공차'] == 'O').sum())
print(f"전체 {len(df)}건 중 추정공차 O: {n_O}건 ({n_O/len(df)*100:.1f}%)")
print(f"정답셋(공차_최종_전처리_데이터.xlsx): {len(GT)}건")

# ---- 검증: 정답셋과 매칭 ----
key_cols = ['작업일자', '작업시간', '차량', '상차지_전처리', '하차지_전처리']
df_key = df.set_index(key_cols)
gt_key = GT.set_index(key_cols)
matched = gt_key.index.isin(df_key.index)
print(f"정답셋 중 내 계산에서도 O로 나온 건: {matched.sum()} / {len(GT)} ({matched.sum()/len(GT)*100:.1f}%)")

my_O = df[df['추정공차'] == 'O'].set_index(key_cols)
matched2 = my_O.index.isin(gt_key.index)
print(f"내가 O로 계산한 것 중 정답셋에 있는 건: {matched2.sum()} / {len(my_O)} ({matched2.sum()/len(my_O)*100:.1f}%)")

# ---- 통계 산출 (대시보드 갱신용) ----
df['hour'] = pd.to_datetime(df['작업시간'], format='%H:%M', errors='coerce').dt.hour
df['dow'] = pd.to_datetime(df['작업일자']).dt.dayofweek
df['O_bin'] = (df['추정공차'] == 'O').astype(int)
dow_names = ['월', '화', '수', '목', '금', '토', '일']

PORT_GROUPS = ['부산신항', '부산북항', '인천신항', '인천항', '평택항', '광양항', '의왕']
def port_group(x):
    if pd.isna(x):
        return 'ETC'
    for p in PORT_GROUPS:
        if str(x).startswith(p):
            return p
    return 'ETC'
df['상차_항만그룹'] = df['상차지_전처리'].apply(port_group)

stats = {}
stats['n_rows'] = int(len(df))
stats['n_공차'] = n_O
stats['공차_비율'] = round(n_O / len(df) * 100, 2)
stats['검증_정답셋_건수'] = int(len(GT))
stats['검증_재현율'] = round(float(matched.mean()) * 100, 1)
stats['검증_정밀도'] = round(float(matched2.mean()) * 100, 1)

cross = pd.crosstab(df['용차'], df['추정공차'], normalize='index').mul(100).round(1)
stats['용차_추정공차_교차'] = cross.to_dict()

grp = df.groupby('상차_항만그룹')['O_bin'].agg(['mean', 'count'])
grp = grp[grp['count'] >= 50].sort_values('mean', ascending=False)
stats['항만그룹별_공차율'] = [{'항만그룹': i, '건수': int(r['count']), '공차율': round(r['mean']*100, 1)} for i, r in grp.iterrows()]

hg = df.groupby('hour')['O_bin'].agg(['mean', 'count']).reset_index()
stats['시간대별_공차율'] = [{'hour': int(r['hour']), '건수': int(r['count']), '공차율': round(r['mean']*100, 1)} for _, r in hg.iterrows() if not pd.isna(r['hour'])]

dg = df.groupby('dow')['O_bin'].agg(['mean', 'count']).reset_index()
stats['요일별_공차율'] = [{'요일': dow_names[int(r['dow'])], '건수': int(r['count']), '공차율': round(r['mean']*100, 1)} for _, r in dg.iterrows()]

o_rows = df[df['O_bin'] == 1]
gap = o_rows['공차시간_시간'].dropna()
stats['공차시간_통계'] = {'n': int(gap.shape[0]), 'mean': round(float(gap.mean()), 1) if len(gap) else None,
                        'median': round(float(gap.median()), 1) if len(gap) else None}

df['다건'] = (df['차량작업건수'] > 1).astype(int)
mg = df.groupby('다건')['O_bin'].agg(['mean', 'count'])
stats['단건다건_공차율'] = {
    '1건차량': {'건수': int(mg.loc[0, 'count']), '공차율': round(mg.loc[0, 'mean']*100, 1)},
    '다건차량': {'건수': int(mg.loc[1, 'count']), '공차율': round(mg.loc[1, 'mean']*100, 1)},
}

OUT = r"./분석\gongcha_stats.json"
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

# 전체 라벨 붙은 데이터도 저장 (다른 스크립트에서 재사용)
df.to_pickle(r"./분석\model_artifacts\df_with_gongcha.pkl")

print(json.dumps({k: v for k, v in stats.items() if not isinstance(v, list)}, ensure_ascii=False, indent=2))
