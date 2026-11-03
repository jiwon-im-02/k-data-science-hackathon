# -*- coding: utf-8 -*-
"""
에이아이로직스 신규 오더 판정 웹앱
====================================
04_score_new_order.py 가 로드하는 실제 LightGBM 모델(§3 검증 AUC 0.845)을 그대로 백엔드로 써서,
브라우저 폼에서 새 오더를 입력하면 진짜 모델 추론 결과를 즉시 보여주는 로컬 웹앱.

실행:
    python 05_app.py
그 다음 브라우저에서 http://127.0.0.1:5000 접속
"""
import importlib.util
import os

from flask import Flask, jsonify, render_template_string, request

HERE = os.path.dirname(os.path.abspath(__file__))

# 파일명이 숫자로 시작해 일반 import 문을 못 쓰므로 importlib로 직접 로드
_spec = importlib.util.spec_from_file_location("score_new_order_mod", os.path.join(HERE, "04_score_new_order.py"))
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

app = Flask(__name__)


@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

# 자동완성용 목록 (전체 상차지, 화주는 건수 상위 300개)
TERMINALS = sorted(
    [{"name": k, "n": scorer.LK["상차지_건수"].get(k, 0), "te": v} for k, v in scorer.LK["te_상차지"].items()],
    key=lambda d: -d["n"],
)
CUSTOMERS = sorted(
    [{"name": k, "n": v, "te": scorer.LK["te_화주"].get(k, scorer.LK["prior"])} for k, v in scorer.LK["화주_건수"].items()],
    key=lambda d: -d["n"],
)[:300]

# 거점별 공차 현황 (실측치, gongcha_stats.json 항만그룹별_공차율 기반) — 미니맵 마커 좌표는 개략적 상대 위치
MAP_POINTS = [
    {"name": "인천항",   "rate": 6.2,  "n": 520,  "x": 96,  "y": 132},
    {"name": "인천신항", "rate": 7.1,  "n": 1226, "x": 92,  "y": 150},
    {"name": "의왕",     "rate": 15.6, "n": 1596, "x": 118, "y": 162},
    {"name": "평택항",   "rate": 0.2,  "n": 2636, "x": 104, "y": 190},
    {"name": "광양항",   "rate": 3.0,  "n": 238,  "x": 96,  "y": 322},
    {"name": "부산북항", "rate": 8.0,  "n": 1376, "x": 224, "y": 330},
    {"name": "부산신항", "rate": 2.5,  "n": 3937, "x": 214, "y": 344},
]
_rates = [p["rate"] for p in MAP_POINTS]
_rmin, _rmax = min(_rates), max(_rates)
for p in MAP_POINTS:
    p["t"] = (p["rate"] - _rmin) / (_rmax - _rmin) if _rmax > _rmin else 0.5  # 0~1 정규화(색상용)
    p["r"] = 5 + 9 * (p["n"] / max(pt["n"] for pt in MAP_POINTS))  # 반경(물량용)
    p["color"] = "var(--aqua)" if p["rate"] < 5 else ("var(--yellow)" if p["rate"] < 10 else "var(--red)")

# 모델 피처 중요도(§ 검증 단계 실측)를 사용자 이해용 4개 그룹으로 합산
FACTOR_GROUPS = [
    {"label": "화주별 용차 이력", "pct": 43.0, "color": "var(--blue)"},
    {"label": "구간·터미널 이력", "pct": 22.4, "color": "var(--violet)"},
    {"label": "당일 물량·시간대", "pct": 6.2, "color": "var(--aqua)"},
    {"label": "선사·중량·기타", "pct": 28.4, "color": "var(--yellow)"},
]

PAGE = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>배차 AI — 에이아이로직스</title>
<style>
  :root {
    color-scheme: light;
    --surface-0:#f4f5f7; --surface-1:#ffffff; --surface-2:#f7f8fa; --text-primary:#0c1220; --text-secondary:#5b6472;
    --text-muted:#9aa2b1; --grid:#e7e9ee; --border:#e3e6ec;
    --blue:#2a5fd6; --blue-ink:#1b3fa0; --blue-soft:#eaf0ff;
    --aqua:#0fa36b; --yellow:#e0930c; --red:#e0413f; --violet:#5b45c9;
    --shadow-sm: 0 1px 2px rgba(15,23,42,.04);
    --shadow-md: 0 8px 24px -10px rgba(15,23,42,.16), 0 2px 6px -2px rgba(15,23,42,.06);
    --shadow-lg: 0 24px 60px -20px rgba(15,23,42,.28), 0 4px 12px -4px rgba(15,23,42,.08);
  }
  @media (prefers-color-scheme: dark) {
    :root { color-scheme: dark; --surface-0:#0a0c10; --surface-1:#131722; --surface-2:#171c29; --text-primary:#f2f4f8;
      --text-secondary:#a7afc0; --text-muted:#6b7385; --grid:#232838; --border:#242a3a;
      --blue:#4d7bf0; --blue-ink:#8fabf8; --blue-soft:#182246;
      --aqua:#1ec489; --yellow:#f0a92c; --red:#f0625f; --violet:#8b73ec;
      --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
      --shadow-md: 0 8px 24px -10px rgba(0,0,0,.55), 0 2px 6px -2px rgba(0,0,0,.4);
      --shadow-lg: 0 24px 60px -20px rgba(0,0,0,.7), 0 4px 12px -4px rgba(0,0,0,.4);
    }
  }
  * { box-sizing:border-box; }
  html, body { height:100%; }
  body {
    margin:0; font-family: system-ui,-apple-system,"Segoe UI",sans-serif;
    color:var(--text-primary); -webkit-font-smoothing:antialiased;
    background-color: var(--surface-0);
    background-image:
      radial-gradient(900px 480px at 8% -12%, color-mix(in srgb, var(--blue) 20%, transparent), transparent 60%),
      radial-gradient(700px 420px at 100% 0%, color-mix(in srgb, var(--violet) 16%, transparent), transparent 55%),
      radial-gradient(800px 500px at 85% 100%, color-mix(in srgb, var(--aqua) 12%, transparent), transparent 55%),
      radial-gradient(circle, color-mix(in srgb, var(--text-primary) 6%, transparent) 1px, transparent 1.4px);
    background-repeat: no-repeat, no-repeat, no-repeat, repeat;
    background-size: auto, auto, auto, 22px 22px;
    background-attachment: fixed;
    min-height:100vh;
  }
  @media (prefers-color-scheme: dark) {
    body { background-image:
      radial-gradient(900px 480px at 8% -12%, color-mix(in srgb, var(--blue) 30%, transparent), transparent 60%),
      radial-gradient(700px 420px at 100% 0%, color-mix(in srgb, var(--violet) 24%, transparent), transparent 55%),
      radial-gradient(800px 500px at 85% 100%, color-mix(in srgb, var(--aqua) 18%, transparent), transparent 55%),
      radial-gradient(circle, color-mix(in srgb, #ffffff 7%, transparent) 1px, transparent 1.4px);
      background-size: auto, auto, auto, 22px 22px;
    }
  }
  .app-shell { max-width: 1040px; margin:0 auto; padding: 26px 24px 60px; animation: shellIn .5s ease both; }
  @keyframes shellIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }

  /* ---------- top bar ---------- */
  .topbar {
    display:flex; align-items:center; justify-content:space-between; gap:18px; padding: 12px 20px; flex-wrap:wrap;
    background: color-mix(in srgb, var(--surface-1) 82%, transparent);
    backdrop-filter: blur(14px) saturate(1.4); -webkit-backdrop-filter: blur(14px) saturate(1.4);
    border:1px solid var(--border); border-radius:18px; box-shadow: var(--shadow-md);
    margin-bottom: 22px;
  }
  .brand { display:flex; align-items:center; gap:12px; }
  .brand-mark {
    width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0;
    background:linear-gradient(145deg, var(--blue), var(--violet)); box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,.3);
    color:#fff;
  }
  .brand-text .brand-name { font-size:15.5px; font-weight:800; letter-spacing:-.01em; line-height:1.25; }
  .brand-text .brand-sub { font-size:11.5px; color:var(--text-muted); font-weight:500; }

  .steps { display:flex; align-items:center; gap:10px; }
  .step { display:flex; align-items:center; gap:8px; font-size:12.5px; font-weight:700; color:var(--text-muted); }
  .step .step-num {
    width:23px; height:23px; border-radius:999px; display:flex; align-items:center; justify-content:center;
    font-size:11.5px; background:var(--surface-2); border:1px solid var(--border); color:var(--text-muted);
    transition: all .25s ease;
  }
  .step.active { color:var(--text-primary); }
  .step.active .step-num { background:linear-gradient(135deg, var(--blue), var(--violet)); border-color:transparent; color:#fff; box-shadow:0 0 0 4px color-mix(in srgb, var(--blue) 18%, transparent); }
  .step.done .step-num { background:var(--aqua); border-color:var(--aqua); color:#fff; }
  .step-line { width:34px; height:1.5px; background:var(--border); }

  .status-chip { display:flex; align-items:center; gap:8px; font-size:12px; font-weight:700; color:var(--text-secondary);
    background:var(--surface-2); border:1px solid var(--border); padding:7px 14px; border-radius:999px; font-variant-numeric:tabular-nums; }
  .status-chip .dot { width:7px; height:7px; border-radius:999px; background:var(--aqua); box-shadow:0 0 0 3px color-mix(in srgb, var(--aqua) 25%, transparent); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  /* ---------- stage / screens ---------- */
  .stage { position:relative; overflow:hidden; border-radius:22px; box-shadow:var(--shadow-lg); background:var(--surface-1); border:1px solid var(--border); }
  .stage::before {
    content:''; position:absolute; top:0; left:0; right:0; height:4px; z-index:2;
    background:linear-gradient(90deg, var(--blue), var(--violet), var(--aqua));
  }
  .screens { display:flex; width:200%; transition: transform .5s cubic-bezier(.65,0,.35,1); }
  .screens.show-result { transform: translateX(-50%); }
  .screen { width:50%; padding: 34px 38px 40px; flex-shrink:0; }

  .screen-eyebrow { font-size:11.5px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--blue); margin-bottom:6px; }
  .screen h1 { font-size:22px; margin:0 0 6px; letter-spacing:-.01em; }
  .screen .lede { color:var(--text-secondary); font-size:13.5px; line-height:1.6; max-width:640px; margin:0 0 28px; }

  .section-label { display:flex; align-items:center; gap:7px; font-size:12px; font-weight:700; color:var(--text-secondary); margin: 22px 0 12px; }
  .section-label:first-of-type { margin-top:0; }
  .section-label svg { color:var(--blue); }

  .field { margin-bottom:14px; position:relative; }
  .field-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; }
  .field-row3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:14px; }
  label { display:block; font-size:12px; font-weight:600; color:var(--text-secondary); margin-bottom:6px; }
  .input-icon { position:absolute; left:12px; top:34px; color:var(--text-muted); pointer-events:none; }
  input, select {
    width:100%; padding:10px 12px; border-radius:10px; border:1.5px solid var(--border);
    background:var(--surface-2); color:var(--text-primary); font-size:13.5px; font-family:inherit;
    transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
  }
  input.with-icon { padding-left:36px; }
  input:hover, select:hover { border-color: color-mix(in srgb, var(--blue) 35%, var(--border)); }
  input:focus, select:focus {
    outline:none; border-color:var(--blue); background:var(--surface-1);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--blue) 14%, transparent);
  }
  details { margin: 4px 0 4px; border-top:1px dashed var(--border); padding-top: 14px; }
  summary { cursor:pointer; font-size:12.5px; font-weight:600; color:var(--text-muted); user-select:none; list-style:none; display:flex; align-items:center; gap:6px; }
  summary::-webkit-details-marker { display:none; }
  summary .chev { transition: transform .2s ease; }
  details[open] summary .chev { transform: rotate(90deg); }
  details .field-row { margin-top:14px; }

  button.primary {
    width:100%; padding:14px; border:none; border-radius:12px;
    background:linear-gradient(135deg, var(--blue), var(--blue-ink)); color:#fff;
    font-size:14.5px; font-weight:800; cursor:pointer; margin-top: 10px;
    display:flex; align-items:center; justify-content:center; gap:8px;
    box-shadow: 0 10px 24px -10px color-mix(in srgb, var(--blue) 70%, transparent);
    transition: transform .12s ease, box-shadow .12s ease, opacity .12s ease;
  }
  button.primary:hover { transform: translateY(-1px); box-shadow: 0 14px 30px -10px color-mix(in srgb, var(--blue) 75%, transparent); }
  button.primary:active { transform: translateY(0); }
  button.primary:disabled { opacity:.55; cursor:default; transform:none; }
  button.ghost {
    padding:9px 15px; border-radius:10px; border:1.5px solid var(--border); background:var(--surface-1);
    color:var(--text-secondary); font-size:12.5px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:6px;
    transition: all .15s ease;
  }
  button.ghost:hover { border-color: color-mix(in srgb, var(--blue) 40%, var(--border)); color:var(--blue); }

  /* ---------- fleet table ---------- */
  table.fleet { width:100%; border-collapse:separate; border-spacing:0 6px; }
  table.fleet th { text-align:left; font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:.03em; color:var(--text-muted); padding:0 8px 4px; }
  table.fleet td { padding:2px 6px; }
  table.fleet input { padding:8px 10px; font-size:12.5px; }
  .rmVeh { border:none;background:none;color:var(--text-muted);cursor:pointer;font-size:15px; width:26px; height:26px; border-radius:8px; }
  .rmVeh:hover { color:var(--red); background:color-mix(in srgb, var(--red) 10%, transparent); }

  /* ---------- screen 2 : results ---------- */
  .result-topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom: 22px; }
  .order-chip { display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text-secondary); background:var(--surface-2); border:1px solid var(--border); padding:7px 13px 7px 11px; border-radius:999px; }
  .order-chip b { color:var(--text-primary); font-weight:700; }
  .order-chip .arrow { color:var(--text-muted); }

  #screenResult { opacity:1; }
  #screenResult.reveal { animation: resultIn .55s cubic-bezier(.2,.7,.3,1) both; }
  @keyframes resultIn { from { opacity:0; transform:translateY(14px) scale(.985); } to { opacity:1; transform:translateY(0) scale(1); } }

  .hero {
    position:relative; overflow:hidden;
    display:flex; align-items:center; gap:34px; padding: 28px 32px; border-radius:18px; margin-bottom:26px;
    background:
      radial-gradient(480px 260px at 12% 15%, var(--tier-glow, transparent), transparent),
      radial-gradient(circle, color-mix(in srgb, var(--text-primary) 5%, transparent) 1px, transparent 1.4px) 0 0/16px 16px,
      var(--surface-2);
    border:1px solid var(--border);
  }
  .gauge-wrap { position:relative; width:172px; height:172px; flex-shrink:0; }
  .gauge-value { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
  .gauge-value .num { font-size:34px; font-weight:800; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
  .gauge-value .cap { font-size:10.5px; color:var(--text-muted); font-weight:600; margin-top:2px; }
  .hero-body { flex:1; min-width:0; }
  .tier-pill { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:999px; font-size:12.5px; font-weight:800; }
  .tier-action { margin-top:12px; font-size:14px; color:var(--text-primary); line-height:1.55; font-weight:500; }

  .stat-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin-bottom:24px; }
  .stat-tile { background:var(--surface-2); border:1px solid var(--border); border-radius:14px; padding:14px 16px; }
  .stat-tile { transition: transform .15s ease, box-shadow .15s ease; }
  .stat-tile:hover { transform: translateY(-2px); box-shadow: var(--shadow-sm); }
  .stat-tile .stat-label { font-size:11px; font-weight:600; color:var(--text-muted); display:flex; align-items:center; gap:7px; margin-bottom:10px; }
  .stat-tile .stat-icon { width:22px; height:22px; border-radius:7px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .stat-tile .stat-value { font-size:19px; font-weight:800; font-variant-numeric:tabular-nums; letter-spacing:-.01em; }

  .panel { margin-bottom: 22px; }
  .panel-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .panel-head h3 { font-size:13.5px; margin:0; font-weight:800; }
  .badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:10.5px; font-weight:800; letter-spacing:.02em; }

  .veh-card { display:flex; align-items:center; gap:13px; padding:12px 14px; border-radius:13px; background:var(--surface-2); border:1px solid var(--border); margin-bottom:8px; border-left-width:4px; border-left-style:solid; }
  .veh-rank { width:26px; height:26px; border-radius:999px; background:var(--surface-1); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; color:var(--text-secondary); flex-shrink:0; }
  .veh-info { flex:1; min-width:0; }
  .veh-info .veh-id { font-size:13.5px; font-weight:800; }
  .veh-info .veh-reason { font-size:11.5px; color:var(--text-muted); margin-top:2px; }
  .veh-idle { font-size:11px; color:var(--text-muted); font-weight:600; white-space:nowrap; }

  /* ---------- history ---------- */
  .history-panel { margin-top: 22px; background:var(--surface-1); border:1px solid var(--border); border-radius:18px; padding:22px 26px; box-shadow:var(--shadow-sm); }
  .history-panel h2 { font-size:13px; margin:0 0 14px; color:var(--text-secondary); font-weight:800; text-transform:uppercase; letter-spacing:.03em; }
  table.hist { width:100%; border-collapse:collapse; font-size:12.5px; }
  table.hist th,td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--grid); }
  table.hist th { color:var(--text-muted); font-weight:700; font-size:10.5px; text-transform:uppercase; letter-spacing:.03em; }
  table.hist td.num { text-align:right; font-variant-numeric:tabular-nums; font-weight:700; }

  .footnote { font-size:11.5px; color:var(--text-muted); margin-top:18px; padding:0 6px; line-height:1.6; }

  /* ---------- loading overlay ---------- */
  .loading-overlay {
    position:fixed; inset:0; background: color-mix(in srgb, var(--surface-0) 78%, transparent); backdrop-filter: blur(3px);
    display:flex; align-items:center; justify-content:center; z-index:100; opacity:0; pointer-events:none; transition:opacity .2s ease;
  }
  .loading-overlay.show { opacity:1; pointer-events:auto; }
  .loading-box { background:var(--surface-1); border:1px solid var(--border); border-radius:18px; padding:30px 40px; box-shadow:var(--shadow-lg); text-align:center; }
  .spinner { width:34px; height:34px; border-radius:999px; border:3px solid var(--border); border-top-color:var(--blue); margin:0 auto 14px; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-text { font-size:13px; font-weight:700; color:var(--text-secondary); }
  .loading-sub { font-size:11.5px; color:var(--text-muted); margin-top:4px; }

  /* ---------- 입력화면 2단 레이아웃 + 인사이트 사이드바 ---------- */
  .form-layout { display:grid; grid-template-columns: 1.5fr 1fr; gap:26px; align-items:start; }
  .insight-col { position:sticky; top:14px; display:flex; flex-direction:column; gap:16px; }
  .insight-card { background:var(--surface-2); border:1px solid var(--border); border-radius:16px; padding:16px 18px; }
  .insight-card h4 { font-size:12px; font-weight:800; margin:0 0 3px; display:flex; align-items:center; gap:6px; }
  .insight-card h4 svg { color:var(--blue); }
  .insight-card .insight-cap { font-size:10.5px; color:var(--text-muted); margin-bottom:12px; }

  .minimap-wrap { position:relative; border-radius:12px; overflow:hidden; background:
      linear-gradient(160deg, color-mix(in srgb, var(--blue) 10%, var(--surface-1)), color-mix(in srgb, var(--aqua) 6%, var(--surface-1)));
    border:1px solid var(--border); }
  .minimap-wrap svg { display:block; width:100%; height:auto; }
  .map-land { fill: color-mix(in srgb, var(--aqua) 13%, var(--surface-1)); stroke: color-mix(in srgb, var(--aqua) 30%, var(--border)); stroke-width:1.2; }
  .map-dot-ring { animation: ringPulse 2.4s ease-out infinite; transform-origin: center; transform-box: fill-box; }
  @keyframes ringPulse { 0% { opacity:.55; transform:scale(1); } 100% { opacity:0; transform:scale(2.4); } }
  .map-label { font-size:6.6px; font-weight:700; fill:var(--text-primary); }
  .map-label-sub { font-size:5.6px; fill:var(--text-muted); font-weight:600; }

  .map-legend { display:flex; align-items:center; gap:12px; margin-top:10px; font-size:10px; color:var(--text-secondary); flex-wrap:wrap; }
  .map-legend .item { display:flex; align-items:center; gap:5px; }
  .map-legend .sw { width:8px; height:8px; border-radius:999px; }

  .factor-bar { display:flex; height:11px; border-radius:999px; overflow:hidden; margin: 4px 0 12px; box-shadow: inset 0 0 0 1px var(--border); }
  .factor-bar span { height:100%; }
  .factor-legend { display:flex; flex-direction:column; gap:7px; }
  .factor-legend .frow { display:flex; align-items:center; justify-content:space-between; font-size:11.5px; }
  .factor-legend .frow .flabel { display:flex; align-items:center; gap:7px; color:var(--text-secondary); font-weight:600; }
  .factor-legend .frow .fdot { width:9px; height:9px; border-radius:3px; flex-shrink:0; }
  .factor-legend .frow .fpct { font-weight:800; font-variant-numeric:tabular-nums; }

  .mini-stat-row { display:flex; gap:10px; }
  .mini-stat { flex:1; background:var(--surface-1); border:1px solid var(--border); border-radius:12px; padding:10px 12px; text-align:center; }
  .mini-stat .mv { font-size:17px; font-weight:800; font-variant-numeric:tabular-nums; }
  .mini-stat .ml { font-size:9.5px; color:var(--text-muted); font-weight:700; margin-top:2px; }

  /* ---------- 결과화면 경로 미리보기 ---------- */
  .route-card { background:var(--surface-2); border:1px solid var(--border); border-radius:16px; padding:18px 22px; margin-bottom:20px; display:flex; align-items:center; gap:18px; }
  .route-pins { flex:1; display:flex; align-items:center; gap:10px; min-width:0; }
  .route-pin { display:flex; flex-direction:column; align-items:center; gap:6px; flex-shrink:0; max-width:130px; }
  .route-pin .pin-ic { width:34px; height:34px; border-radius:999px; display:flex; align-items:center; justify-content:center; color:#fff; box-shadow:var(--shadow-sm); }
  .route-pin .pin-label { font-size:11px; font-weight:800; text-align:center; line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:130px; }
  .route-pin .pin-sub { font-size:9.5px; color:var(--text-muted); font-weight:600; }
  .route-line { flex:1; position:relative; height:2px; background: repeating-linear-gradient(90deg, var(--border) 0 6px, transparent 6px 11px); min-width:40px; }
  .route-truck { position:absolute; top:50%; left:0; transform:translate(-50%,-50%); color:var(--blue); animation: driveAlong 2.6s ease-in-out infinite; }
  @keyframes driveAlong { 0% { left:6%; } 50% { left:94%; } 100% { left:6%; } }
  .route-meta { flex-shrink:0; text-align:right; font-size:11px; color:var(--text-muted); font-weight:600; border-left:1px solid var(--border); padding-left:16px; }
  .route-meta b { display:block; font-size:12.5px; color:var(--text-primary); font-weight:800; margin-bottom:2px; }

  @media (max-width: 760px) {
    .field-row, .field-row3, .stat-grid { grid-template-columns:1fr; }
    .form-layout { grid-template-columns:1fr; }
    .insight-col { position:static; }
    .steps { display:none; }
    .hero { flex-direction:column; text-align:center; }
    .route-card { flex-direction:column; }
    .route-meta { border-left:none; border-top:1px solid var(--border); padding-left:0; padding-top:12px; text-align:center; width:100%; }
    .screen { padding: 26px 20px 30px; }
  }
</style>
</head>
<body>
<div class="app-shell">

  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">
        <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 17h2m0 0V7a1 1 0 0 1 1-1h7v11H5Zm10 0h2.5l3-4V9a1 1 0 0 0-1-1H15v9Zm-8 3a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/>
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-name">배차 AI</div>
        <div class="brand-sub">공차 최소화 · 자차 배차 추천 시스템</div>
      </div>
    </div>
    <div class="steps">
      <div class="step active" id="stepDot1"><span class="step-num">1</span>오더 입력</div>
      <div class="step-line"></div>
      <div class="step" id="stepDot2"><span class="step-num">2</span>AI 판정 결과</div>
    </div>
    <div class="status-chip"><span class="dot"></span><span id="liveClock">-</span></div>
  </div>

  <div class="stage">
    <div class="screens" id="screens">

      <!-- ============ SCREEN 1 : 입력 ============ -->
      <section class="screen" id="screenForm">
        <div class="screen-eyebrow">신규 오더 판정</div>
        <h1>오더 정보를 입력하세요</h1>
        <p class="lede">AI 엔진이 과거 운행 데이터를 학습해, 이 오더가 용차로 빠질 확률과 가장 효율적인 자차 배정을 실시간으로 계산합니다.</p>

        <div class="form-layout">
        <div class="form-main">

        <div class="section-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg>
          화물 · 구간 정보
        </div>
        <div class="field">
          <label>상차지</label>
          <input list="dlTerminal" id="fTerminal" class="with-icon" placeholder="예: 인천항 인천E1" autocomplete="off">
          <span class="input-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg></span>
          <datalist id="dlTerminal">
            {% for t in terminals %}<option value="{{ t.name }}">{% endfor %}
          </datalist>
        </div>
        <div class="field">
          <label>하차지 <span style="font-weight:400;color:var(--text-muted)">(비우면 상차지와 동일로 간주)</span></label>
          <input id="fUnload" class="with-icon" placeholder="예: 경기도 화성시">
          <span class="input-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg></span>
        </div>
        <div class="field">
          <label>화주 <span style="font-weight:400;color:var(--text-muted)">(이력 없는 신규 화주면 비워두세요)</span></label>
          <input list="dlCustomer" id="fCustomer" class="with-icon" placeholder="예: 화주0288" autocomplete="off">
          <span class="input-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="7" height="11"/><rect x="14" y="4" width="7" height="17"/><path d="M6 14h1M6 17h1M17 8h1M17 11h1M17 14h1"/></svg></span>
          <datalist id="dlCustomer">
            {% for c in customers %}<option value="{{ c.name }}">{% endfor %}
          </datalist>
        </div>
        <div class="field-row">
          <div class="field">
            <label>수출입</label>
            <select id="fInOut"><option value="수입">수입</option><option value="수출">수출</option></select>
          </div>
          <div class="field">
            <label>컨테이너 타입</label>
            <select id="fType">
              <option value="40HC">40HC</option><option value="20DC">20DC</option><option value="40RF">40RF</option>
              <option value="20RF">20RF</option><option value="40DC">40DC</option><option value="ETC">기타</option>
            </select>
          </div>
        </div>
        <div class="field-row">
          <div class="field"><label>선사(라인, 선택)</label><input id="fLine" placeholder="예: KMD"></div>
          <div class="field"><label>중량 kg <span style="font-weight:400;color:var(--text-muted)">(모르면 비워두기)</span></label><input type="number" id="fWeight" step="500" placeholder="예: 18000"></div>
        </div>

        <div class="section-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>
          일정
        </div>
        <div class="field-row">
          <div class="field"><label>작업일자</label><input type="date" id="fDate"></div>
          <div class="field"><label>작업시간</label><input type="time" id="fTime" value="09:00"></div>
        </div>

        <details>
          <summary><svg class="chev" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m9 6 6 6-6 6"/></svg> 당일 실시간 운영정보 입력 (없으면 과거 평균으로 자동 대체)</summary>
          <div class="field-row">
            <div class="field"><label>오늘 총 접수 오더 수</label><input type="number" id="fDayN" placeholder="자동"></div>
            <div class="field"><label>오늘 가동 자차 대수</label><input type="number" id="fFleet" placeholder="자동"></div>
          </div>
          <div class="field-row">
            <div class="field"><label>오늘 이 터미널 물량(건)</label><input type="number" id="fTermN" placeholder="자동"></div>
            <div class="field"><label>같은 날 반대방향 오더 존재</label>
              <select id="fPair"><option value="">자동(과거 평균)</option><option value="1">있음</option><option value="0">없음</option></select>
            </div>
          </div>
        </details>

        <div class="section-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17h2m0 0V7a1 1 0 0 1 1-1h7v11H5Zm10 0h2.5l3-4V9a1 1 0 0 0-1-1H15v9Zm-8 3a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/></svg>
          오늘 대기 중인 자차 <span style="font-weight:500;color:var(--text-muted);text-transform:none;letter-spacing:0">(선택 — 입력하면 실제 차량 배정까지 추천)</span>
        </div>
        <table class="fleet" id="fleetTable">
          <thead><tr><th style="width:32%">차량 번호</th><th>최근 하차지</th><th style="width:18%">유휴(분)</th><th style="width:30px"></th></tr></thead>
          <tbody id="fleetBody"></tbody>
        </table>
        <button type="button" class="ghost" id="btnAddVehicle" style="margin-top:4px;">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg> 차량 추가
        </button>

        <button class="primary" id="btnScore">
          <span id="btnScoreLabel">AI 판정 시작</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>

        </div><!-- /form-main -->

        <div class="insight-col">
          <div class="insight-card">
            <h4><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg> 주요 거점 공차 현황</h4>
            <div class="insight-cap">점 크기 = 물량, 색 = 공차율(낮음 → 높음)</div>
            <div class="minimap-wrap">
              <svg viewBox="0 0 300 400" xmlns="http://www.w3.org/2000/svg">
                <path class="map-land" d="M128 14 C104 16 78 34 68 62 C58 88 66 108 60 132 C54 156 40 172 44 198 C48 224 62 236 58 258 C54 280 40 292 48 314 C56 336 78 352 96 372 C110 388 128 396 140 382 C148 372 146 356 158 348 C172 338 192 344 206 334 C222 322 224 302 214 286 C206 274 208 258 218 246 C230 232 236 214 226 198 C218 186 220 170 230 156 C240 140 234 118 218 104 C204 92 202 74 188 60 C174 46 172 28 152 18 C144 14 136 12 128 14 Z"/>
                {% for p in map_points %}
                <g>
                  <circle class="map-dot-ring" cx="{{ p.x }}" cy="{{ p.y }}" r="{{ p.r }}" fill="{{ p.color }}"></circle>
                  <circle cx="{{ p.x }}" cy="{{ p.y }}" r="{{ p.r }}" fill="{{ p.color }}" fill-opacity="0.9" stroke="var(--surface-1)" stroke-width="1.5"></circle>
                  <text class="map-label" x="{{ p.x + p.r + 5 }}" y="{{ p.y - 1 }}">{{ p.name }}</text>
                  <text class="map-label-sub" x="{{ p.x + p.r + 5 }}" y="{{ p.y + 7 }}">공차 {{ p.rate }}%</text>
                </g>
                {% endfor %}
              </svg>
            </div>
            <div class="map-legend">
              <span class="item"><span class="sw" style="background:var(--aqua)"></span>5% 미만</span>
              <span class="item"><span class="sw" style="background:var(--yellow)"></span>5~10%</span>
              <span class="item"><span class="sw" style="background:var(--red)"></span>10% 이상</span>
            </div>
          </div>

          <div class="insight-card">
            <h4><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18M7 15l4-5 3 3 5-7"/></svg> AI가 판정 시 보는 요인</h4>
            <div class="insight-cap">과거 데이터 학습 결과 기준 영향도</div>
            <div class="factor-bar">
              {% for f in factor_groups %}<span style="width:{{ f.pct }}%; background:{{ f.color }}"></span>{% endfor %}
            </div>
            <div class="factor-legend">
              {% for f in factor_groups %}
              <div class="frow"><span class="flabel"><span class="fdot" style="background:{{ f.color }}"></span>{{ f.label }}</span><span class="fpct">{{ f.pct }}%</span></div>
              {% endfor %}
            </div>
          </div>

          <div class="mini-stat-row">
            <div class="mini-stat"><div class="mv" id="miniSessCount">0</div><div class="ml">오늘 판정 건수</div></div>
            <div class="mini-stat"><div class="mv" id="miniSessAvg">-</div><div class="ml">평균 용차확률</div></div>
          </div>
        </div>
        </div><!-- /form-layout -->
      </section>

      <!-- ============ SCREEN 2 : 결과 ============ -->
      <section class="screen" id="screenResult">
        <div class="result-topbar">
          <button type="button" class="ghost" id="btnBack">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M11 18l-6-6 6-6M5 12h14"/></svg> 새 오더 입력
          </button>
        </div>

        <div class="route-card" id="routeCard">
          <div class="route-pins">
            <div class="route-pin">
              <div class="pin-ic" style="background:linear-gradient(135deg, var(--blue), var(--blue-ink))">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg>
              </div>
              <div class="pin-label" id="routeFrom">-</div>
              <div class="pin-sub">상차지</div>
            </div>
            <div class="route-line">
              <div class="route-truck">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17h2m0 0V7a1 1 0 0 1 1-1h7v11H5Zm10 0h2.5l3-4V9a1 1 0 0 0-1-1H15v9Z"/></svg>
              </div>
            </div>
            <div class="route-pin">
              <div class="pin-ic" style="background:linear-gradient(135deg, var(--violet), #3a2c8f)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg>
              </div>
              <div class="pin-label" id="routeTo">-</div>
              <div class="pin-sub">하차지</div>
            </div>
          </div>
          <div class="route-meta"><b id="routeWhen">-</b><span id="routeCustomer">-</span></div>
        </div>

        <div class="hero" id="heroBox">
          <div class="gauge-wrap">
            <svg width="172" height="172" viewBox="0 0 172 172" id="gaugeSvg"></svg>
            <div class="gauge-value">
              <span class="num" id="gaugeNum">0%</span>
              <span class="cap">예측 용차 확률</span>
            </div>
          </div>
          <div class="hero-body">
            <span class="tier-pill" id="tierPill"></span>
            <div class="tier-action" id="tierAction"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head"><h3>판정 근거</h3></div>
          <div class="stat-grid" id="statGrid"></div>
        </div>

        <div class="panel">
          <div class="panel-head"><h3>차량 배정 추천</h3><span class="badge" id="vehModeBadge"></span></div>
          <div id="vehicleList"></div>
        </div>
      </section>

    </div>
  </div>

  <div class="history-panel">
    <h2>이번 세션 판정 이력</h2>
    <table class="hist" id="histTable">
      <thead><tr><th>시각</th><th>상차지</th><th>화주</th><th>확률</th><th>등급</th></tr></thead>
      <tbody id="histBody"><tr><td colspan="5" style="color:var(--text-muted)">아직 판정 기록이 없습니다.</td></tr></tbody>
    </table>
  </div>

  <div class="footnote">© 2026 에이아이로직스 · 배차 AI · 이번 판정 이력은 이 브라우저에만 저장됩니다</div>
</div>

<div class="loading-overlay" id="loadingOverlay">
  <div class="loading-box">
    <div class="spinner"></div>
    <div class="loading-text">AI가 판정 중입니다</div>
    <div class="loading-sub">용차 확률 · 최적 차량 계산 중…</div>
  </div>
</div>

<script>
const NS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs){ const e=document.createElementNS(NS,tag); for(const k in attrs) e.setAttribute(k, attrs[k]); return e; }
function polarToCartesian(cx,cy,r,angleDeg){ const a=angleDeg*Math.PI/180; return {x:cx+r*Math.cos(a), y:cy+r*Math.sin(a)}; }
function describeArc(cx,cy,r,startAngle,endAngle){
  if (endAngle - startAngle >= 359.999) endAngle = startAngle + 359.999;
  const start = polarToCartesian(cx,cy,r,startAngle), end = polarToCartesian(cx,cy,r,endAngle);
  const large = endAngle-startAngle<=180?0:1;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
}
function tierMeta(prob){
  if (prob>=0.667) return {label:'상위 위험군', color:'var(--red)', glow:'color-mix(in srgb, var(--red) 16%, transparent)', action:'자차 최우선 배정을 권고합니다 — 이 조합의 실측 용차 전환율이 매우 높습니다.'};
  if (prob>=0.499) return {label:'중상위 위험군', color:'var(--yellow)', glow:'color-mix(in srgb, var(--yellow) 16%, transparent)', action:'가능하면 자차를 우선 배정하고, 여의치 않으면 조기에 용차를 확보하세요.'};
  if (prob>=0.31)  return {label:'평균 수준', color:'var(--text-muted)', glow:'transparent', action:'통상적인 배차 프로세스로 진행해도 무방합니다.'};
  return {label:'저위험군', color:'var(--aqua)', glow:'color-mix(in srgb, var(--aqua) 16%, transparent)', action:'자차 캐파가 부족하면 이 건을 용차로 돌려도 전체 영향이 작습니다.'};
}

document.getElementById('fDate').value = new Date().toISOString().slice(0,10);

// ---- 대기 자차 목록 행 관리 ----
function addVehicleRow(veh, drop, idle) {
  const tbody = document.getElementById('fleetBody');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" class="vVeh" placeholder="12가1234" value="${veh||''}"></td>
    <td><input list="dlTerminal" type="text" class="vDrop" placeholder="최근 하차지" value="${drop||''}"></td>
    <td><input type="number" class="vIdle" placeholder="0" value="${idle||''}"></td>
    <td><button type="button" class="rmVeh">×</button></td>
  `;
  tr.querySelector('.rmVeh').addEventListener('click', () => tr.remove());
  tbody.appendChild(tr);
}
document.getElementById('btnAddVehicle').addEventListener('click', () => addVehicleRow());
addVehicleRow();

// ---- 상단 실시간 시계 ----
function tickClock() {
  const el = document.getElementById('liveClock');
  if (el) el.textContent = new Date().toLocaleString('ko-KR', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', weekday:'short'});
}
tickClock();
setInterval(tickClock, 1000 * 30);

function collectVehicles() {
  const rows = document.querySelectorAll('#fleetBody tr');
  const out = [];
  rows.forEach(tr => {
    const veh = tr.querySelector('.vVeh').value.trim();
    const drop = tr.querySelector('.vDrop').value.trim();
    const idle = tr.querySelector('.vIdle').value;
    if (veh) out.push({차량: veh, 최근하차지: drop, 유휴시간_분: idle ? parseFloat(idle) : 0});
  });
  return out;
}

// ---- 화면 전환 ----
function goToResult() {
  document.getElementById('screens').classList.add('show-result');
  document.getElementById('stepDot1').classList.remove('active'); document.getElementById('stepDot1').classList.add('done');
  document.getElementById('stepDot2').classList.add('active');
  const resEl = document.getElementById('screenResult');
  resEl.classList.remove('reveal'); void resEl.offsetWidth; resEl.classList.add('reveal');
}
function goToForm() {
  document.getElementById('screens').classList.remove('show-result');
  document.getElementById('stepDot2').classList.remove('active');
  document.getElementById('stepDot1').classList.remove('done'); document.getElementById('stepDot1').classList.add('active');
}
document.getElementById('btnBack').addEventListener('click', goToForm);

function showLoading(show) {
  document.getElementById('loadingOverlay').classList.toggle('show', show);
}

document.getElementById('btnScore').addEventListener('click', async () => {
  const btn = document.getElementById('btnScore');
  const terminal = document.getElementById('fTerminal').value.trim();
  if (!terminal) { document.getElementById('fTerminal').focus(); document.getElementById('fTerminal').style.borderColor = 'var(--red)'; return; }
  btn.disabled = true;
  showLoading(true);
  const startedAt = Date.now();
  const payload = {
    상차지: terminal,
    하차지: document.getElementById('fUnload').value.trim(),
    화주: document.getElementById('fCustomer').value.trim(),
    작업일자: document.getElementById('fDate').value,
    작업시간: document.getElementById('fTime').value,
    수출입: document.getElementById('fInOut').value,
    타입: document.getElementById('fType').value,
    라인: document.getElementById('fLine').value.trim(),
    중량: document.getElementById('fWeight').value,
    day_order_n: document.getElementById('fDayN').value,
    own_fleet_capacity: document.getElementById('fFleet').value,
    terminal_day_n: document.getElementById('fTermN').value,
    pair_available: document.getElementById('fPair').value,
    available_vehicles: collectVehicles(),
  };
  try {
    const res = await fetch('/api/score', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const data = await res.json();
    if (data.error) { alert('오류: ' + data.error); return; }
    const elapsed = Date.now() - startedAt;
    const minDelay = Math.max(0, 550 - elapsed); // 판정 중 연출을 위한 최소 표시시간
    await new Promise(r => setTimeout(r, minDelay));
    renderResult(payload, data);
    addHistory(payload, data);
    goToResult();
  } catch (e) {
    alert('요청 실패: ' + e.message);
  } finally {
    showLoading(false);
    btn.disabled = false;
  }
});

function animateGauge(targetProb, color) {
  const svg = document.getElementById('gaugeSvg');
  svg.innerHTML = '';
  const cx=86, cy=86, r=72;
  svg.appendChild(svgEl('circle', {cx, cy, r, fill:'none', stroke:'var(--grid)', 'stroke-width':14}));
  const fg = svgEl('path', {fill:'none', stroke:color, 'stroke-width':14, 'stroke-linecap':'round'});
  svg.appendChild(fg);
  const numEl = document.getElementById('gaugeNum');

  const setFrame = (val) => {
    const angle = -90 + 360 * Math.min(0.9995, Math.max(0.0005, val));
    fg.setAttribute('d', describeArc(cx, cy, r, -90, angle));
    numEl.textContent = Math.round(val*100) + '%';
  };

  // 최종값을 먼저 동기적으로 그려둔다 — 탭이 백그라운드라 requestAnimationFrame이
  // 억제되더라도(브라우저의 일반적인 절전 동작) 결과가 항상 정확하게 표시되도록 하기 위함.
  setFrame(targetProb);

  // 화면이 실제로 보이는 상태일 때만 스윕 애니메이션 연출을 얹는다.
  if (document.visibilityState === 'visible') {
    const start = performance.now();
    const dur = 800;
    function frame(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1-t, 3);
      setFrame(targetProb * eased);
      if (t < 1) requestAnimationFrame(frame); else setFrame(targetProb);
    }
    requestAnimationFrame(frame);
  }
}

function renderResult(payload, data) {
  const prob = data['용차_확률'];
  const meta = tierMeta(prob);

  document.getElementById('heroBox').style.setProperty('--tier-glow', meta.glow);
  document.getElementById('gaugeNum').style.color = meta.color;
  animateGauge(prob, meta.color);

  const pill = document.getElementById('tierPill');
  pill.textContent = meta.label;
  pill.style.background = `color-mix(in srgb, ${meta.color} 16%, transparent)`;
  pill.style.color = meta.color;
  document.getElementById('tierAction').textContent = meta.action;

  document.getElementById('routeFrom').textContent = payload.상차지;
  document.getElementById('routeTo').textContent = payload.하차지 || payload.상차지;
  document.getElementById('routeWhen').textContent = `${payload.작업일자} · ${payload.작업시간}`;
  document.getElementById('routeCustomer').textContent = payload.화주 || '신규/기타 화주';

  const f = data.참고_피처;
  const stats = [
    {icon:'pin', label:'상차지 이력 용차율', value:(f.te_상차지*100).toFixed(1)+'%'},
    {icon:'building', label:'화주 이력 용차율', value:(f.te_화주*100).toFixed(1)+'%'},
    {icon:'clock', label:'화주 최근30일 용차율', value:(f.화주_최근30일용차율*100).toFixed(1)+'%'},
    {icon:'gauge', label:'당일 부하(오더수÷자차대수)', value:f.load_ratio.toFixed(2)},
    {icon:'swap', label:'반대방향 오더 존재확률', value:(f.pair_available*100).toFixed(0)+'%'},
    {icon:'truck', label:'컨테이너 타입', value:f.타입_cat},
  ];
  const ICONS = {
    pin: '<path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/>',
    building: '<rect x="3" y="10" width="7" height="11"/><rect x="14" y="4" width="7" height="17"/><path d="M6 14h1M6 17h1M17 8h1M17 11h1M17 14h1"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    gauge: '<path d="M12 22a9 9 0 1 1 0-18 9 9 0 0 1 0 18Z"/><path d="M12 12 8 9M12 6v2"/>',
    swap: '<path d="m17 2 4 4-4 4M3 6h18M7 22l-4-4 4-4M21 18H3"/>',
    truck: '<rect x="1" y="7" width="13" height="10"/><path d="M14 10h4l3 3v4h-7z"/><circle cx="6" cy="19" r="1.6"/><circle cx="17.5" cy="19" r="1.6"/>',
  };
  const ICON_COLORS = ['var(--blue)','var(--violet)','var(--aqua)','var(--yellow)','var(--red)','var(--blue)'];
  const grid = document.getElementById('statGrid');
  grid.innerHTML = stats.map((s,i) => `<div class="stat-tile">
      <div class="stat-label"><span class="stat-icon" style="background:color-mix(in srgb, ${ICON_COLORS[i%ICON_COLORS.length]} 14%, transparent); color:${ICON_COLORS[i%ICON_COLORS.length]}"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">${ICONS[s.icon]||''}</svg></span>${s.label}</div>
      <div class="stat-value">${s.value}</div>
    </div>`).join('');

  renderVehicleRec(data.차량배정);
}

function renderVehicleRec(vr) {
  const listEl = document.getElementById('vehicleList');
  const badge = document.getElementById('vehModeBadge');
  if (!vr || !vr.추천 || vr.추천.length === 0) {
    badge.textContent = ''; badge.style.background = 'transparent';
    listEl.innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);padding:10px 2px">${(vr && vr.안내) || '추천할 자차 이력이 없습니다.'}</div>`;
    return;
  }
  const isLive = vr.모드.startsWith('실시간');
  badge.textContent = isLive ? '실시간 매칭' : '이력 참고용';
  badge.style.background = isLive ? 'color-mix(in srgb, var(--aqua) 16%, transparent)' : 'color-mix(in srgb, var(--text-muted) 16%, transparent)';
  badge.style.color = isLive ? 'var(--aqua)' : 'var(--text-secondary)';

  const borderColor = (v) => {
    if (v.점수 === 2) return 'var(--aqua)';
    if (v.점수 === 1) return 'var(--yellow)';
    if (v.점수 === 0) return 'var(--border)';
    return 'var(--blue)';
  };
  listEl.innerHTML = vr.추천.slice(0,5).map((v, i) => {
    const sub = v.사유 || `이력 ${v.이력_운행횟수}회 · 최근 ${v.마지막_이력상_하차지 || '-'}`;
    const idle = (v.유휴시간_분 !== undefined && v.유휴시간_분 !== null && v.사유) ? `대기 ${v.유휴시간_분}분` : '';
    return `<div class="veh-card" style="border-left-color:${borderColor(v)}">
      <div class="veh-rank">${i+1}</div>
      <div class="veh-info"><div class="veh-id">${v.차량}</div><div class="veh-reason">${sub}</div></div>
      <div class="veh-idle">${idle}</div>
    </div>`;
  }).join('');
}

let histCount = 0;
let probSum = 0;
function addHistory(payload, data) {
  histCount++;
  probSum += data['용차_확률'];
  const tbody = document.getElementById('histBody');
  if (histCount === 1) tbody.innerHTML = '';
  const meta = tierMeta(data['용차_확률']);
  const tr = document.createElement('tr');
  const now = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit'});
  tr.innerHTML = `<td>${now}</td><td>${payload.상차지 || '(미입력)'}</td><td>${payload.화주 || '신규/기타'}</td>
    <td class="num">${Math.round(data['용차_확률']*100)}%</td>
    <td><span class="badge" style="background:color-mix(in srgb, ${meta.color} 16%, transparent); color:${meta.color}">${meta.label}</span></td>`;
  tbody.prepend(tr);

  const cEl = document.getElementById('miniSessCount');
  const aEl = document.getElementById('miniSessAvg');
  if (cEl) cEl.textContent = histCount;
  if (aEl) aEl.textContent = Math.round(probSum / histCount * 100) + '%';
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, terminals=TERMINALS[:250], customers=CUSTOMERS,
                                   map_points=MAP_POINTS, factor_groups=FACTOR_GROUPS)


@app.route("/api/score", methods=["POST"])
def api_score():
    body = request.get_json(force=True)
    try:
        order = {
            "상차지_전처리": body.get("상차지") or None,
            "하차지_전처리": body.get("하차지") or body.get("상차지") or None,
            "화주": body.get("화주") or None,
            "라인": body.get("라인") or None,
            "타입": body.get("타입") or "ETC",
            "중량": float(body["중량"]) if body.get("중량") not in (None, "") else None,
            "수출입": body.get("수출입") or "수입",
            "작업일자": body.get("작업일자") or None,
            "작업시간": body.get("작업시간") or "09:00",
        }
        context = {}
        for k in ("day_order_n", "own_fleet_capacity", "terminal_day_n"):
            v = body.get(k)
            if v not in (None, ""):
                context[k] = float(v)
        if body.get("pair_available") not in (None, ""):
            context["pair_available"] = float(body["pair_available"])

        if not order["상차지_전처리"]:
            return jsonify({"error": "상차지를 입력해주세요."}), 400

        available_vehicles = body.get("available_vehicles") or None

        result = scorer.score_new_order(order, context, available_vehicles)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("신규 오더 판정 웹앱 실행 중")
    print("브라우저에서 http://127.0.0.1:5000 접속하세요")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
