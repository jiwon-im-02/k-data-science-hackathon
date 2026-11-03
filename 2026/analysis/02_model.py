# -*- coding: utf-8 -*-
"""용차 예측 모델: 피처엔지니어링 + LightGBM 시간분할 검증 -> model_stats.json"""
import json
import re
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.linear_model import LogisticRegression

pd.set_option('display.max_columns', None)
np.random.seed(42)

SRC = r"./코드\전처리_데이터.xlsx"
OUT = r"./분석\model_stats.json"

df = pd.read_excel(SRC).sort_values('작업일시').reset_index(drop=True)
df['y'] = (df['용차'] == '용차').astype(int)
df['hour'] = pd.to_datetime(df['작업시간'], format='%H:%M').dt.hour
df['dow'] = df['작업일시'].dt.dayofweek
df['날짜'] = df['작업일자'].dt.date

# ---------------------------------------------------------------
# STEP1 보조 전처리
# ---------------------------------------------------------------
PORT_GROUPS = ['부산신항', '부산북항', '인천신항', '인천항', '평택항', '광양항', '의왕']

def port_group(x):
    if pd.isna(x):
        return 'ETC'
    for p in PORT_GROUPS:
        if str(x).startswith(p):
            return p
    return 'ETC'

df['상차_항만그룹'] = df['상차지_전처리'].apply(port_group)
df['하차_항만그룹'] = df['하차지_전처리'].apply(port_group)
df['same_node'] = (df['상차지_전처리'] == df['하차지_전처리']).astype(int)

df['시도'] = df['지역'].astype(str).str.split().str[0]
df['시군구'] = df['지역'].astype(str).str.split().str[1].fillna('')

# 라인: 상위 20 + OTHER, 결측은 컨테이너 prefix 최빈매핑으로 보정 시도 후 UNK
line_map = (df.dropna(subset=['라인', '컨테이너'])
              .groupby('컨테이너')['라인'].agg(lambda s: s.value_counts().index[0]))
df['라인_보정'] = df['라인']
na_line = df['라인'].isna() & df['컨테이너'].notna()
df.loc[na_line, '라인_보정'] = df.loc[na_line, '컨테이너'].map(line_map)
df['라인_보정'] = df['라인_보정'].fillna('UNK')
top_lines = df['라인_보정'].value_counts().head(20).index
df['라인_cat'] = np.where(df['라인_보정'].isin(top_lines), df['라인_보정'], 'OTHER')

# 타입: 상위5 + ETC, 파생
top_types = ['40HC', '20DC', '40RF', '20RF', '40DC']
df['타입_cat'] = np.where(df['타입'].isin(top_types), df['타입'], 'ETC')
df['size20'] = df['타입'].astype(str).str.startswith('20').astype(int)
df['size40'] = df['타입'].astype(str).str.startswith('40').astype(int)
df['is_reefer'] = df['타입'].astype(str).str.contains('RF').astype(int)

# 중량
df['weight_na'] = df['중량'].isna().astype(int)
type_median = df.groupby('타입_cat')['중량'].transform('median')
df['w_kg'] = df['중량'].fillna(type_median)

df['is_month_end'] = (df['작업일자'].dt.day >= 25).astype(int)
df['레인'] = df['상차_항만그룹'] + '__' + df['시군구']

# ---------------------------------------------------------------
# STEP2-B 캐파 부하 피처
# ---------------------------------------------------------------
daily_fleet = (df[df['y'] == 0].groupby(['날짜', 'dow'])['차량'].nunique().rename('자차대수_당일').reset_index())
# 직전 4주 동일요일 자차대수 중앙값 (rolling, 누수 방지: 당일 제외)
daily_fleet = daily_fleet.sort_values('날짜')
fleet_by_dow = {}
own_fleet_cap = []
for _, row in daily_fleet.iterrows():
    d, dw, n = row['날짜'], row['dow'], row['자차대수_당일']
    hist = fleet_by_dow.get(dw, [])
    own_fleet_cap.append(np.median(hist[-4:]) if len(hist) > 0 else np.nan)
    hist.append(n)
    fleet_by_dow[dw] = hist
daily_fleet['own_fleet_capacity'] = own_fleet_cap
daily_fleet['own_fleet_capacity'] = daily_fleet['own_fleet_capacity'].fillna(daily_fleet['자차대수_당일'].median())

day_order_n = df.groupby('날짜').size().rename('day_order_n').reset_index()
daily_fleet = daily_fleet.merge(day_order_n, on='날짜')
daily_fleet['load_ratio'] = daily_fleet['day_order_n'] / daily_fleet['own_fleet_capacity']

df = df.merge(daily_fleet[['날짜', 'own_fleet_capacity', 'load_ratio', 'day_order_n']], on='날짜', how='left')

df['terminal_day_n'] = df.groupby(['날짜', '상차_항만그룹'])['상차_항만그룹'].transform('size')
df['sido_day_n'] = df.groupby(['날짜', '시도'])['시도'].transform('size')
df['hour_bucket_congestion'] = df.groupby(['날짜', 'hour'])['hour'].transform('size')

# ---------------------------------------------------------------
# STEP2-C 이력 인코딩 (시간 안전 expanding target encoding)
# ---------------------------------------------------------------
PRIOR = 0.315
PRIOR_N = 20

def expanding_te(frame, key, target='y'):
    g = frame.groupby(key)[target]
    cum_sum = g.cumsum() - frame[target]
    cum_cnt = g.cumcount()
    return (cum_sum + PRIOR * PRIOR_N) / (cum_cnt + PRIOR_N)

for key, name in [('화주', 'te_화주'), ('상차지_전처리', 'te_상차지'), ('라인_cat', 'te_라인'), ('시군구', 'te_시군구'), ('레인', 'te_레인')]:
    df[name] = expanding_te(df, key)

df['화주_누적물량'] = df.groupby('화주').cumcount()
df['레인_누적건수'] = df.groupby('레인').cumcount()

# 화주 최근 30일 용차율 (rolling window by date, 시간 안전)
df = df.sort_values('작업일시')
cust_roll = []
cust_hist = {}
for idx, row in df.iterrows():
    cust = row['화주']
    hist = cust_hist.get(cust, [])
    cust_roll.append(np.mean(hist) if len(hist) > 0 else PRIOR)
    hist.append(row['y'])
    cust_hist[cust] = hist[-30:]
df['화주_최근30일용차율'] = cust_roll

# ---------------------------------------------------------------
# STEP2-D 체이닝 가능성 피처 (같은 날 같은 시군구 반대방향 오더)
# ---------------------------------------------------------------
pair_cnt = df.groupby(['날짜', '시군구', '수출입']).size().unstack(fill_value=0)
pair_cnt['pair_available'] = ((pair_cnt.get('수입', 0) > 0) & (pair_cnt.get('수출', 0) > 0)).astype(int)
pair_cnt = pair_cnt[['pair_available']].reset_index()
df = df.merge(pair_cnt, on=['날짜', '시군구'], how='left')
df['pair_available'] = df['pair_available'].fillna(0).astype(int)

term_pair_cnt = df.groupby(['날짜', '상차_항만그룹', '수출입']).size().unstack(fill_value=0)
term_pair_cnt['terminal_pair_available'] = ((term_pair_cnt.get('수입', 0) > 0) & (term_pair_cnt.get('수출', 0) > 0)).astype(int)
term_pair_cnt = term_pair_cnt[['terminal_pair_available']].reset_index()
df = df.merge(term_pair_cnt, on=['날짜', '상차_항만그룹'], how='left')
df['terminal_pair_available'] = df['terminal_pair_available'].fillna(0).astype(int)

# ---------------------------------------------------------------
# 모델링: 1~2월 학습 / 3월 검증 (시간분할)
# ---------------------------------------------------------------
FEATURES_NO_LEAK = [
    '수출입', '라인_cat', '타입_cat', 'size20', 'size40', 'is_reefer', 'w_kg', 'weight_na',
    'hour', 'dow', 'is_month_end', '상차_항만그룹', '하차_항만그룹', 'same_node',
    'day_order_n', 'own_fleet_capacity', 'load_ratio', 'terminal_day_n', 'sido_day_n',
    'hour_bucket_congestion', 'te_화주', 'te_상차지', 'te_라인', 'te_시군구', 'te_레인',
    '화주_누적물량', '레인_누적건수', '화주_최근30일용차율', 'pair_available', 'terminal_pair_available',
]
CAT_COLS = ['수출입', '라인_cat', '타입_cat', '상차_항만그룹', '하차_항만그룹']

model_df = df.copy()
for c in CAT_COLS:
    model_df[c] = model_df[c].astype('category')

train_mask = model_df['작업일자'] < '2026-03-01'
valid_mask = model_df['작업일자'] >= '2026-03-01'

X_train, y_train = model_df.loc[train_mask, FEATURES_NO_LEAK], model_df.loc[train_mask, 'y']
X_valid, y_valid = model_df.loc[valid_mask, FEATURES_NO_LEAK], model_df.loc[valid_mask, 'y']

results = {}
results['n_train'] = int(len(X_train))
results['n_valid'] = int(len(X_valid))
results['train_period'] = '2026-01-01 ~ 2026-02-28'
results['valid_period'] = '2026-03-01 ~ 2026-03-31'

def fit_lgb(Xtr, ytr, Xva, yva, cat_cols):
    train_set = lgb.Dataset(Xtr, label=ytr, categorical_feature=cat_cols, free_raw_data=False)
    valid_set = lgb.Dataset(Xva, label=yva, categorical_feature=cat_cols, reference=train_set, free_raw_data=False)
    params = dict(objective='binary', metric='auc', learning_rate=0.05, num_leaves=31,
                  min_child_samples=30, feature_fraction=0.85, bagging_fraction=0.85,
                  bagging_freq=1, verbose=-1, seed=42)
    model = lgb.train(params, train_set, num_boost_round=500,
                       valid_sets=[valid_set],
                       callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
    pred = model.predict(Xva, num_iteration=model.best_iteration)
    return model, pred

# 메인 모델 (차량ID 제외)
model_main, pred_main = fit_lgb(X_train, y_train, X_valid, y_valid, CAT_COLS)
results['auc_main'] = round(float(roc_auc_score(y_valid, pred_main)), 4)
results['prauc_main'] = round(float(average_precision_score(y_valid, pred_main)), 4)
results['brier_main'] = round(float(brier_score_loss(y_valid, pred_main)), 4)

# 누수 검증용: 차량ID 포함 모델
X_train_leak = X_train.copy(); X_train_leak['차량'] = model_df.loc[train_mask, '차량'].astype('category')
X_valid_leak = X_valid.copy(); X_valid_leak['차량'] = model_df.loc[valid_mask, '차량'].astype('category')
_, pred_leak = fit_lgb(X_train_leak, y_train, X_valid_leak, y_valid, CAT_COLS + ['차량'])
results['auc_leak_차량포함'] = round(float(roc_auc_score(y_valid, pred_leak)), 4)

# 화주 제외 (블록C 의존도 확인)
feat_no_cust = [f for f in FEATURES_NO_LEAK if f not in ('te_화주', '화주_누적물량', '화주_최근30일용차율')]
_, pred_no_cust = fit_lgb(X_train[feat_no_cust], y_train, X_valid[feat_no_cust], y_valid, [c for c in CAT_COLS if c in feat_no_cust])
results['auc_화주제외'] = round(float(roc_auc_score(y_valid, pred_no_cust)), 4)

# 로지스틱 회귀 베이스라인 (해석용, 수치형만 단순 사용)
num_feats = ['w_kg', 'hour', 'dow', 'load_ratio', 'terminal_day_n', 'te_화주', 'te_상차지',
             'te_라인', 'te_레인', '화주_최근30일용차율', 'same_node', 'pair_available']
Xtr_lr = X_train[num_feats].fillna(0)
Xva_lr = X_valid[num_feats].fillna(0)
lr = LogisticRegression(max_iter=1000)
lr.fit(Xtr_lr, y_train)
pred_lr = lr.predict_proba(Xva_lr)[:, 1]
results['auc_logreg_baseline'] = round(float(roc_auc_score(y_valid, pred_lr)), 4)

# 규칙 베이스(터미널 평균 용차율)
term_rate = X_train.assign(y=y_train.values).groupby('상차_항만그룹', observed=True)['y'].mean()
pred_rule = X_valid['상차_항만그룹'].astype(str).map(term_rate).astype(float).fillna(y_train.mean())
results['auc_규칙베이스'] = round(float(roc_auc_score(y_valid, pred_rule)), 4)

# ---- 리프트 테이블 (10분위) ----
valid_out = pd.DataFrame({'y': y_valid.values, 'pred': pred_main})
valid_out['decile'] = pd.qcut(valid_out['pred'], 10, labels=False, duplicates='drop')
overall_rate = valid_out['y'].mean()
lift_tbl = valid_out.groupby('decile').agg(건수=('y', 'size'), 실제용차율=('y', 'mean')).reset_index()
lift_tbl = lift_tbl.sort_values('decile', ascending=False).reset_index(drop=True)
lift_tbl['리프트'] = (lift_tbl['실제용차율'] / overall_rate).round(2)
lift_tbl['실제용차율'] = (lift_tbl['실제용차율'] * 100).round(1)
lift_tbl['분위'] = ['상위 10%', '상위 20%', '상위 30%', '상위 40%', '상위 50%',
                    '상위 60%', '상위 70%', '상위 80%', '상위 90%', '전체(하위포함)'][:len(lift_tbl)]
results['lift_table'] = lift_tbl[['분위', '건수', '실제용차율', '리프트']].to_dict('records')
results['overall_valid_rate'] = round(float(overall_rate) * 100, 1)

top20_capture = valid_out.sort_values('pred', ascending=False).head(int(len(valid_out) * 0.2))['y'].sum() / valid_out['y'].sum()
results['top20_capture_pct'] = round(float(top20_capture) * 100, 1)

# ---- Feature Importance ----
imp = pd.DataFrame({'feature': model_main.feature_name(), 'importance': model_main.feature_importance(importance_type='gain')})
imp = imp.sort_values('importance', ascending=False)
imp['importance'] = (imp['importance'] / imp['importance'].sum() * 100).round(1)
results['feature_importance'] = imp.head(15).to_dict('records')

# ---- 왕복매칭 개선여지 (블록D 실측치) ----
results['pair_available_pct'] = round(float(df['pair_available'].mean()) * 100, 1)
results['terminal_pair_available_pct'] = round(float(df['terminal_pair_available'].mean()) * 100, 1)

# ---------------------------------------------------------------
# 신규 오더 스코어링용 산출물 저장 (실전 배차 판정에 재사용)
# ---------------------------------------------------------------
MODEL_DIR = r"./분석\model_artifacts"
import os
os.makedirs(MODEL_DIR, exist_ok=True)

# 전체 데이터(1~3월 전부)로 "지금 시점 기준" 룩업 재계산 -> 신규 오더 스코어링에 사용
def full_te(frame, key, target='y'):
    g = frame.groupby(key)[target].agg(['sum', 'count'])
    return ((g['sum'] + PRIOR * PRIOR_N) / (g['count'] + PRIOR_N)).round(4).to_dict()

lookups = {
    'prior': PRIOR,
    'te_화주': full_te(df, '화주'),
    'te_상차지': full_te(df, '상차지_전처리'),
    'te_라인': full_te(df, '라인_cat'),
    'te_시군구': full_te(df, '시군구'),
    'te_레인': full_te(df, '레인'),
    '화주_최근30일용차율': (df.sort_values('작업일시').groupby('화주')['y']
                          .apply(lambda s: s.tail(30).mean()).round(4).to_dict()),
    '화주_건수': df.groupby('화주').size().to_dict(),
    '상차지_건수': df.groupby('상차지_전처리').size().to_dict(),
    '레인_건수': df.groupby('레인').size().to_dict(),
    '화주_최빈지역': df.groupby('화주')['지역'].agg(lambda s: s.value_counts().index[0]).to_dict(),
    'top_lines': list(top_lines),
    'top_types': top_types,
    'port_groups': PORT_GROUPS,
    'default_load_ratio': round(float(daily_fleet['load_ratio'].median()), 3),
    'default_day_order_n': round(float(daily_fleet['day_order_n'].median()), 1),
    'default_own_fleet_capacity': round(float(daily_fleet['own_fleet_capacity'].median()), 1),
    'default_terminal_day_n_by_port': (df.groupby('상차_항만그룹').size() / df['날짜'].nunique()).round(1).to_dict(),
    'default_sido_day_n_by_sido': (df.groupby('시도').size() / df['날짜'].nunique()).round(1).to_dict(),
    'default_hour_bucket_congestion_by_hour': (df.groupby('hour').size() / df['날짜'].nunique()).round(1).to_dict(),
    'default_w_kg_by_type': df.groupby('타입_cat')['w_kg'].median().round(0).to_dict(),
    'default_pair_available_by_시군구': df.groupby('시군구')['pair_available'].mean().round(3).to_dict(),
    'default_terminal_pair_available_by_port': df.groupby('상차_항만그룹')['terminal_pair_available'].mean().round(3).to_dict(),
    'line_container_prefix_map': {k: v for k, v in line_map.items()},
}

# ---- 상차지별 자차 이력 TOP5 (차량 배정 추천용) ----
# 자차 비중 0.5 이상인 차량만 "우리 자차"로 간주, 상차지별 운행횟수 상위 5대
veh_own_ratio = df.groupby('차량')['y'].mean()  # y=1 이면 용차이므로 비율 낮을수록 자차성향
own_vehicles = set(veh_own_ratio[veh_own_ratio <= 0.5].index)
own_df = df[df['차량'].isin(own_vehicles) & (df['y'] == 0)]
terminal_vehicle_top = {}
for term, g in own_df.groupby('상차지_전처리'):
    top = g['차량'].value_counts().head(5)
    terminal_vehicle_top[term] = [{'차량': v, '운행횟수': int(c)} for v, c in top.items()]
lookups['terminal_vehicle_top'] = terminal_vehicle_top
lookups['own_vehicle_last_dropoff'] = (
    df[df['차량'].isin(own_vehicles)].sort_values('작업일시')
    .groupby('차량').agg(마지막하차지=('하차지_전처리', 'last'), 마지막작업일시=('작업일시', 'last')).reset_index()
    .assign(마지막작업일시=lambda d: d['마지막작업일시'].astype(str))
    .set_index('차량').to_dict('index')
)
with open(os.path.join(MODEL_DIR, 'lookups.json'), 'w', encoding='utf-8') as f:
    json.dump(lookups, f, ensure_ascii=False, indent=2, default=str)

# 최종 LightGBM: 전체 데이터로 재학습(운영 배포용) + 저장
full_train_set = lgb.Dataset(model_df[FEATURES_NO_LEAK], label=model_df['y'], categorical_feature=CAT_COLS, free_raw_data=False)
final_model = lgb.train(dict(objective='binary', metric='auc', learning_rate=0.05, num_leaves=31,
                              min_child_samples=30, feature_fraction=0.85, bagging_fraction=0.85,
                              bagging_freq=1, verbose=-1, seed=42),
                         full_train_set, num_boost_round=model_main.best_iteration or 200)
import shutil
_tmp_model_path = r"./lgbm_final.txt"
os.makedirs(os.path.dirname(_tmp_model_path), exist_ok=True)
final_model.save_model(_tmp_model_path)
shutil.copyfile(_tmp_model_path, os.path.join(MODEL_DIR, 'lgbm_final.txt'))

# 로지스틱 회귀(해석용/브라우저 즉시판정용) 계수 저장 - 전체데이터 재적합
lr_final = LogisticRegression(max_iter=2000)
X_all_lr = model_df[num_feats].fillna(0)
lr_final.fit(X_all_lr, model_df['y'])
lr_export = {
    'features': num_feats,
    'coef': lr_final.coef_[0].round(6).tolist(),
    'intercept': round(float(lr_final.intercept_[0]), 6),
    'auc_valid_reference': results['auc_logreg_baseline'],
}
with open(os.path.join(MODEL_DIR, 'logreg.json'), 'w', encoding='utf-8') as f:
    json.dump(lr_export, f, ensure_ascii=False, indent=2)

results['feature_columns'] = FEATURES_NO_LEAK
results['categorical_columns'] = CAT_COLS
print("\n모델 아티팩트 저장 완료:", MODEL_DIR)

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)

print(json.dumps({k: v for k, v in results.items() if not isinstance(v, list)}, ensure_ascii=False, indent=2))
print("\nLift table:")
for r in results['lift_table']:
    print(r)
print("\nTop features:")
for r in results['feature_importance'][:10]:
    print(r)
