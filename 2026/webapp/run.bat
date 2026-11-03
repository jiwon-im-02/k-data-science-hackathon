@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Python 가상환경을 생성합니다.
  python -m venv .venv
  call .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo [2/3] 모델 데이터 연결을 확인합니다.
if not exist "data\runtime\model_dataset.json" call .venv\Scripts\python.exe -m model.data_builder_revised
echo [3/3] ROUTE:ONE을 시작합니다: http://127.0.0.1:5000
call .venv\Scripts\python.exe app.py
