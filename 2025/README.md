# 2025 · AegisSign: AI 기반 자필 서명 진위 판별

🏆 2025 K-DATA SCIENCE 해커톤 **창의상** (본선 26개 팀, 팀명 미운네살)

## 문제와 접근

서명 위·변조 범죄가 늘고 있지만, 정교하게 따라 쓴 서명은 **이미지 유사도만으로 구분하기 어렵습니다.** 필기 속도, 필압, 궤적 같은 **행동 정보는 이미지에 남지 않습니다.** 그래서 성격이 다른 두 정보를 독립적으로 검증하는 **이중 인증 구조**를 제안했습니다.

- **이미지 검증:** Siamese Network(CNN)로 서명 이미지 사이의 시각적 유사도를 비교합니다.
- **행동 검증:** 필기 시계열(속도·필압·궤적)을 RNN 계열로 분석합니다.
- 한쪽이 뚫려도 다른 쪽이 걸러내도록 설계해 오탐과 미탐을 함께 줄이는 것이 목표입니다.

## 구성

```text
notebooks/
  01_crop_and_pair_preprocessing.ipynb    손글씨 이미지를 단어 영역으로 잘라 사용자별로 정리하고 Siamese 학습용 쌍을 구성
  02_siamese_cnn_bilstm_keras.ipynb       이미지 시퀀스를 TimeDistributed CNN + BiLSTM으로 임베딩하고 contrastive loss로 학습 (Keras)
  03_siamese_resnet18_pytorch.ipynb       ResNet18 인코더, 기준 서명 5장의 평균 임베딩과 코사인 유사도로 동일인 여부를 판별 (PyTorch)
backend/    FastAPI 서버 (기준 서명 등록, 이미지·필기 검증 API)
web/        React + TypeScript + Vite + Tailwind 웹 화면 (기준 서명 등록, 검증, 결과 리포트)
```

### 모델 실험 요약

- `03`: 사용자(ID) 단위로 학습·검증을 나눕니다. 같은 ID의 서명 쌍은 1, 다른 ID의 쌍은 0으로 두고 BCE loss로 학습하며, 정확도와 AUC로 평가합니다.
- `02`: 같은 사람의 서로 다른 자세 쌍을 positive, 본인 필기와 모사 필기의 같은 자세 쌍을 negative로 구성합니다.

### API (backend)

```text
POST /enroll/image   기준 서명 이미지 등록
GET  /enroll/status  등록된 기준 서명 수 조회
POST /verify/image   이미지 검증 → { similarities[], final, verdict }
POST /verify/pen     필기 시계열(CSV) 검증 → { similarities[], final, verdict }
GET  /health
```

## 실행 방법

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# web
cd web
cp .env.example .env     # API 주소 등을 채웁니다
npm install
npm run dev
```

## 참고 사항

- 학습된 모델 가중치는 포함하지 않았습니다. 서버의 검증 로직은 노트북에서 추출한 전처리 함수로 특징을 만들고 기준 서명과의 **코사인 유사도에 임계값**을 적용하는 **데모 구조**입니다.
- 학습 데이터, 시연 영상, 등록된 사용자 서명 파일은 포함하지 않았습니다.
- 사용 데이터: AI Hub 「개인 특정을 위한 자필과 모사 필기체 데이터」, 「대용량 손글씨 OCR 데이터」
