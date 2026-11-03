library(readxl)
yes <- read_xlsx("./df_embedding_yes.xlsx")
no <- read_xlsx("./df_embedding_no.xlsx")
data <- rbind(yes, no)
head(data)



library(tidyverse)
library(purrr)

# 벡터 길이 확인 및 자르기
min_length <- min(sapply(data, function(col) {
  lengths <- map(col, ~ length(str_extract_all(.x, "-?\\d+\\.?\\d*")[[1]]))
  min(unlist(lengths))
}))

# 가장 짧은 벡터 길이에 맞춰 벡터 자르기 후 숫자 변환
data_processed <- data %>%
  mutate(across(everything(), ~ map(.x, ~ as.numeric(str_extract_all(.x, "-?\\d+\\.?\\d*")[[1]][1:min_length])))) %>%
  unnest(cols = everything())

# PCA와 k-means 클러스터링을 수행할 준비가 된 데이터
head(data_processed)

# 모든 칼럼을 숫자형으로 변환
data_processed_numeric <- data_processed %>%
  mutate(across(everything(), ~ as.numeric(.x)))

# PCA 실행
pca_result <- prcomp(data_processed_numeric, center = TRUE, scale. = TRUE)



# PCA 결과에서 첫 번째와 두 번째 주성분 추출 (데이터프레임으로 변환)
pca_scores <- as.data.frame(pca_result$x[, 1:2])

# k-means 클러스터링 (2개의 클러스터)
set.seed(42)
kmeans_result <- kmeans(pca_scores, centers = 2, nstart = 25)

# 클러스터링 결과 추가
pca_scores$cluster <- as.factor(kmeans_result$cluster)

# 시각화
library(ggplot2)

ggplot(pca_scores, aes(x = PC1, y = PC2, color = cluster)) +
  geom_point(size = 3) +
  labs(title = "PCA with k-means clustering", x = "PC1", y = "PC2") +
  scale_color_manual(values = c("red2", "skyblue2")) +
  theme_minimal()

#-----------------------------------------------------------------------------
# PCA 수행
pca_result <- prcomp(data_processed, center = TRUE, scale. = TRUE)

# 주성분 중 필요한 차원만큼 선택
# 예를 들어 첫 3개의 주성분을 사용 (필요에 따라 조정 가능)
pca_scores <- pca_result$x[, 1:3]  # 첫 3개의 주성분 사용

# k-means clustering 수행 (2개의 클러스터로 설정)
set.seed(42)  # 재현 가능성을 위해 시드 설정
kmeans_result <- kmeans(pca_scores, centers = 2)

# PCA 결과와 클러스터 결과 결합
data_clustered <- as.data.frame(pca_scores) %>%
  mutate(cluster = factor(kmeans_result$cluster))  # 클러스터 결과 추가

# 시각화
library(ggplot2)

ggplot(data_clustered, aes(x = PC1, y = PC2, color = cluster)) +
  geom_point(size = 3) +
  labs(title = "PCA with k-means clustering", x = "PC1", y = "PC2") +
  scale_color_manual(values = c("red2", "skyblue2")) +
  theme_minimal()

# -------------------------------------------------------------------------------------------
  
daaa <- read_xlsx("./data_Answer.xlsx")
head(daaa)
# 필요한 패키지 로드
library(dplyr)
library(ggplot2)

# 위기단계가 '응급'인 사람 중 '유형구분'이 '학대경험 아동'인 행의 수
emergency_abuse_count <- nrow(daaa %>% filter(위기단계 == "응급" & 유형구분 == "학대경험 아동"))

# 위기단계가 '정상군'인 사람 중 '유형구분'이 '학대경험 아동'인 행의 수
normal_abuse_count <- nrow(daaa %>% filter(위기단계 == "정상군" & 유형구분 == "학대경험 아동"))

# 두 값을 DataFrame으로 결합
count_data <- data.frame(
  위기단계 = c("응급", "정상군"),
  학대경험_아동_수 = c(emergency_abuse_count, normal_abuse_count)
)

# 막대 그래프 시각화
ggplot(count_data, aes(x = 위기단계, y = 학대경험_아동_수, fill = 위기단계)) +
  geom_bar(stat = "identity", color = "black") +
  labs(title = "위기단계별 학대경험 아동 수", x = "위기단계", y = "학대경험 아동 수") +
  scale_fill_manual(values = c("응급" = "red2", "정상군" = "skyblue2")) +
  theme_minimal()

# 고급 막대 그래프 시각화
ggplot(count_data, aes(x = 위기단계, y = 학대경험_아동_수, fill = 위기단계)) +
  geom_bar(stat = "identity", color = "white", width = 0.7) +
  scale_fill_manual(values = c("응급" = "#FF6F61", "정상군" = "#4E79A7")) +
  theme_minimal(base_size = 16) +
  theme(
    plot.title = element_text(size = 20, face = "bold", hjust = 0.5),
    axis.title = element_text(size = 14),
    axis.text = element_text(size = 12),
    legend.position = "none"
  ) +
  labs(
    title = "위기단계별 학대경험 아동 수",
    x = "위기단계",
    y = "학대경험 아동 수"
  ) +
  geom_text(aes(label = 학대경험_아동_수), vjust = -0.5, size = 6, color = "black")


# ---------------------------------------------------------------------------
# 필요한 라이브러리 로드
library(ggplot2)
library(dplyr)

# 데이터 필터링 (위기단계가 '응급' 또는 '정상군'인 데이터만 선택)
data_filtered <- daaa %>%
  filter(위기단계 %in% c("응급", "정상군")) %>%
  select(위기단계, 합계점수, 학대의심)  # 필요한 변수만 선택

# 1. 위기단계에 따른 합계점수 박스플롯
ggplot(data_filtered, aes(x = 위기단계, y = 합계점수, fill = 위기단계)) +
  geom_boxplot() +
  labs(title = "위기단계에 따른 합계점수 분포", x = "위기단계", y = "합계점수") +
  scale_fill_manual(values = c("red2", "skyblue2")) +  # '응급'을 빨간색, '정상군'을 파란색
  theme_minimal()



