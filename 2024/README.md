# 2024 · 사회적 고립 해소를 위한 네트워크 기반 감정 분석

🏆 2024 K-DATA SCIENCE 해커톤 **창의상** (본선 26개 팀)

## 문제와 접근

대화 한 건 한 건의 속성만 보지 않고, **대화 사이의 연결 구조**를 변수로 활용해 감정 예측력을 높이는 것이 아이디어입니다.

1. AI Hub 감성 대화 말뭉치에서 감정 대분류(기쁨·당황·분노·불안·상처·슬픔)별로 200건씩 뽑아 약 1,200건을 구성합니다.
2. 문장을 한국어 BERT(KR-BERT)로 임베딩하고 PCA로 차원을 줄입니다. TF-IDF 특징을 이어 붙여 문장 표현을 만듭니다.
3. 문장 사이의 유사도(Cosine, Manhattan, **Soft Cosine**)를 계산해 유사도 그래프를 만듭니다.
4. 그래프를 GraphSAGE에 입력해 감정을 분류합니다.

## 포함된 코드

`preliminary/` (예선 단계: 감성 대화 말뭉치)

| 파일 | 내용 |
| --- | --- |
| `01_embedding_similarity_matrix.ipynb` | 문장 임베딩과 유사도 행렬 |
| `02_tfidf_processing.ipynb` | 형태소 분석(soynlp) 기반 TF-IDF 전처리 |
| `03_hierarchical_clustering.ipynb` | 임베딩의 계층적 군집 분석(HAC) |
| `04_krbert_pca_tfidf_soft_cosine.ipynb` | KR-BERT + PCA + TF-IDF 결합, 유사도 행렬 요약, Soft Cosine 구현 |

`finals/` (본선 단계: 아동·청소년 상담 데이터)

| 파일 | 내용 |
| --- | --- |
| `01_counseling_json_to_dataframe.ipynb` | 상담 JSON에서 문항별 질문·응답을 표로 추출 |
| `02_counseling_crisis_level_text.ipynb` | 위기 단계별 대화문 구성 |
| `03_embedding_pca_kmeans.R` | 임베딩의 PCA와 k-means 군집 시각화 |

## 포함되지 않은 것

- 데이터 전체(AI Hub 감성 대화 말뭉치, 아동·청소년 상담 데이터)
- 이 폴더의 코드는 **임베딩과 유사도 그래프를 만드는 단계까지**입니다. GraphSAGE 분류 단계의 코드는 포함되어 있지 않습니다.

## 사용 데이터

- AI Hub 「감성 대화 말뭉치」
- AI Hub 「아동·청소년 상담 데이터」
