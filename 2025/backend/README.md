# AegisSign Backend (FastAPI)

Python 모델을 React 홈페이지에서 호출하기 위한 FastAPI 서버.
업로드된 notebook(`전처리.ipynb`)에서 **function/class 정의**만 추출 → `user_preprocess.py`.

## Quickstart
cd aegissign_backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

## 엔드포인트
POST /verify/image (refs[], probe) -> { similarities[], final, verdict }
POST /verify/pen   (refs[], probe) -> { similarities[], final, verdict }
GET  /health -> { ok: true }
