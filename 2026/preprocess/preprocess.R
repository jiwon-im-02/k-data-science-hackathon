library(readxl)
library(dplyr)
library(readr)
library(stringr)
library(lubridate)
library(purrr)
library(tibble)
library(hms)
library(lubridate)
library(openxlsx)


setwd("./contest/2026 해커톤")
data <- read_excel("해커톤_자료(마스킹)_에이아이로직스.xlsx")
str(data)
###########################################################
# 지역 변수 중 상하차지가 존재하지 않거나 값이 이상한 경우 삭제
###########################################################
# 삭제할 지역 값 목록
remove_values <- c(
  "14센터", "20엠티직송", "20직송", "20풀직송",
  "4023 엠티직송", "4463 HMM 복화", "4463 HMM 컨", "5671 HMM 컨사용",
  "CFS 작업료등", "CFS작업", "E/T 반납", "대리반납(7379)",
  "데미지 회차", "동원 -> E1", "미정", "반입셔틀",
  "반출", "보관", "보관 / 엠티반납", "보관 / 엠티직송",
  "보관료", "복화", "복화 (2654)", "복화정산오류",
  "상차료대납", "상하차비", "상하차비용", "서류마감1/6오전",
  "선광 -> 덕창", "선광신항", "선반입", "선반입권",
  "선반입대납", "선반입대행", "선픽업", "세컨작업",
  "야간반입 / 엠티반납", "엠티반납", "엠티반납(7379)", "엠티이적",
  "엠티이적(6735)", "엠티직송", "엠티직송(2475)", "엠티직송(3270)",
  "이고", "이적", "작업캔슬보관", "장치료",
  "재반입", "재작업", "중부", "중부CY",
  "직송", "취소회차", "풀반입", "풀직송",
  "풀컨반납", "풀컨이적", "회수", "회차",
  "회차건"
)



# 해당 값을 가지는 행 삭제
data_clean_1 <- data %>% filter(!(지역 %in% remove_values))




###########################################################
# 상차지 또는 하차지가 비어있거나, 숫자로만 구성되거나, '기타복화'인 경우 삭제
###########################################################
# 숫자로만 구성된 문자열인지 확인하는 함수
is_numeric_str <- function(x) !is.na(x) & grepl("^[0-9]+$", x)

# 삭제 조건: 상차지 or 하차지 중 하나라도 비어있거나 / 숫자만 / '기타복화'
cond_delete <- is.na(data_clean_1$상차지) | is.na(data_clean_1$하차지) |
  is_numeric_str(data_clean_1$상차지) | is_numeric_str(data_clean_1$하차지) |
  data_clean_1$상차지 == "기타복화" | data_clean_1$하차지 == "기타복화"

cond_delete[is.na(cond_delete)] <- FALSE



# 조건에 해당하는 행 삭제
data_clean_2 <- data_clean_1 %>% filter(!cond_delete)



###########################################################
# 지역 or 작업시간 or 차량이 NA인 경우 삭제
###########################################################
# 지역 또는 작업시간이 NA인 행 삭제
data_clean_3 <- data_clean_2 %>% filter(!is.na(지역) & !is.na(작업시간) & !is.na(차량))



###########################################################
# 수출입이 'LCL' 또는 '카고'인 경우 삭제 (수출과 수입만 남김!)
###########################################################
# 수출입이 LCL 또는 카고인 행 삭제
data_clean_4 <- data_clean_3 %>% filter(!(수출입 %in% c("LCL", "카고")))



############################################################
# 상차지 전처리
############################################################
df <- data_clean_4

# ============================================================
# 상차지명 전처리 함수
# ============================================================
clean_loading_place <- function(x, use_longest_match = TRUE) {
  
  # 원본 보존
  original_x <- as.character(x)
  x <- as.character(x)
  
  # ----------------------------------------------------------
  # 0. 기본 문자열 정리
  # ----------------------------------------------------------
  x <- str_squish(x)              # 연속 공백을 1칸으로 통일
  x[x == ""] <- NA_character_
  
  # 괄호 앞뒤의 불필요한 공백 정리
  x <- str_replace_all(x, "\\s+\\(", "(")
  x <- str_replace_all(x, "\\(\\s+", "(")
  x <- str_replace_all(x, "\\s+\\)", ")")
  
  # 괄호가 열려 있으나 닫히지 않은 일부 값 보정
  # 예: 부산북항 BPT감만(BIT
  x <- case_when(
    x == "부산북항 BPT감만(BIT" ~ "부산북항 BPT감만(BIT)",
    TRUE ~ x
  )
  
  # ----------------------------------------------------------
  # 1. 띄어쓰기만 다른 값 통일
  #
  # 현재 데이터 내에서 공백을 제거했을 때 같은 값이면,
  # 해당 그룹에서 가장 자주 등장하는 표기를 대표값으로 사용
  # 빈도가 같으면 글자 수가 긴 값을 사용
  # ----------------------------------------------------------
  make_space_dictionary <- function(v) {
    
    temp <- tibble(
      value = v,
      no_space = str_remove_all(v, "\\s+")
    ) %>%
      filter(!is.na(value)) %>%
      count(no_space, value, name = "n") %>%
      group_by(no_space) %>%
      arrange(desc(n), desc(nchar(value)), value, .by_group = TRUE) %>%
      slice(1) %>%
      ungroup() %>%
      select(no_space, representative = value)
    
    temp
  }
  
  space_dictionary <- make_space_dictionary(x)
  
  x <- tibble(
    value = x,
    no_space = str_remove_all(x, "\\s+")
  ) %>%
    left_join(space_dictionary, by = "no_space") %>%
    transmute(
      value = if_else(
        !is.na(representative),
        representative,
        value
      )
    ) %>%
    pull(value)
  
  # ----------------------------------------------------------
  # 2. 삭제 대상
  # ----------------------------------------------------------
  # 7번과 9번 규칙을 합친 목록
  remove_values <- c(
    "공동물류",
    "공용",
    "공용야드",
    "공장 온그라운드",
    "기타 복화",
    "대우보관소",
    "멀티",
    "복화",
    "합동물류",
    "비포장주차장",
    "엠피콘", "엠피콘 상차",
    "영진CY",
    "인터지스상차",
    "천일1기지",
    "천일1기지야드",
    "포유에서복화",
    "한타CY",
    "한타장비",
    "한타야드",
    "부곡재고없으면인천",
    "부곡지정중",
    "세방세차",
    "세방야드",
    "신창물류",
    "동부야드",
    "동부야드F2", "동부야드상차", 
    "동우물류",
    "동원야드",
    "태양산업", "천경야드", "중부CY 서연중부CY"
  )
  
  x[x %in% remove_values] <- NA_character_
  
  # ----------------------------------------------------------
  # 3. 명시적 표기 통일
  # ----------------------------------------------------------
  exact_map <- c(
    
    # 의왕
    "2터미널 GTC창고" = "의왕 2터미널 GTC창고",
    
    "승진기업" = "승진CY",
    
    # 1. FM 관련
    "FM" = "인천항 인천FM CY",
    "FM CY" = "인천항 인천FM CY",
    "FMCY" = "인천항 인천FM CY",
    "인천 FM" = "인천항 인천FM CY",
    "인천 FM CY" = "인천항 인천FM CY",
    "인천FM" = "인천항 인천FM CY",
    "인천FM CY" = "인천항 인천FM CY",
    "인천항 인천FM" = "인천항 인천FM CY",
    "인천항 인천FMCY" = "인천항 인천FM CY",
    
    # 2. ICT, IGFC
    "ICT" = "인천항 인천ICT",
    "인천 ICT" = "인천항 인천ICT",
    "인천ICT" = "인천항 인천ICT",
    
    "IGFC" = "인천항 IGFC",
    "인천IGFC" = "인천항 IGFC",
    
    # 3. KWCT
    "KWCT" = "광양 KWCT",
    
    # 6. 고려종합보관소
    "고려종합보관소" = "부산신항 고려종합보관소",
    "고려종합 보관소" = "부산신항 고려종합보관소",
    "부산신항 고려종합 보관소" = "부산신항 고려종합보관소",
    
    # 8. 라인올구항
    "구항 라인올" = "인천항 라인올구항CY",
    "라인올" = "인천항 라인올구항CY",
    "라인올구항" = "인천항 라인올구항CY",
    "라인올구항CY" = "인천항 라인올구항CY",
    "인천 라인올구항" = "인천항 라인올구항CY",
    
    # 10. 보관소
    "디알보관소" = "부산신항 디알보관소",
    "범영보관소" = "부산신항 범영보관소",
    
    # 13. 부곡상차
    "부곡상차" = "부곡",
    
    # 15. 괄호 누락
    "부산북항 BPT감만(BIT" = "부산북항 BPT감만(BIT)",
    "부산북항 BPT감만(BIT)" = "부산북항 BPT감만(BIT)",
    
    # 16. 베스트우암
    "베트스우암" = "부산북항 베스트우암보관소",
    "베스트우암" = "부산북항 베스트우암보관소",
    "부산북항 베스트우암" = "부산북항 베스트우암보관소",
    "부산북항 베스트우암보관소" = "부산북항 베스트우암보관소",
    
    # 17. 확인된 포함관계
    "부산신항 대야기업" = "부산신항 대야기업보관소",
    "부산신항 대영보관소" = "부산신항 대영엘씨보관소",
    
    # 19. 대한통운세방
    "부산신항 대한통운SB" = "부산신항 대한통운세방",
    "부산신항 대한통훈세방" = "부산신항 대한통운세방",
    "부산신항 대한통운 세방" = "부산신항 대한통운세방",
    
    # 20. 동원로엑스
    "부산신항 동원로엑스" = "부산신항 동원로엑스보관소",
    "부산신항 동원로엑스보관소" = "부산신항 동원로엑스보관소",
    
    # 23~25. 중부 CY
    "중부 인주CY" = "아산 중부 인주CY",
    "중부CY 보승천안CY" = "천안 중부CY 보승천안CY",
    "중부CY 한타청원CY" = "청주 중부CY 한타청원CY",
    
    "인천14센터 : 인천광역시 중구 축항대로165번길 20" = "인천14센터",
    "인천신국제" = "인천신항 신국제",
    "인천 동주월드CY" = "인천항 동주월드CY",
    "인천공동물류" = "인천항 공동물류",
    "인천" = "인천항",
    "인천승진CY" = "인천항 승진CY",
    
    "부산 대영보관소" = "부산북항 대영보관소",
    
    "인천한진신항 엠티이적으로 상차 예정" = "인천신항 인천한진신항",
    "부산" = "부산북항"
  )
  
  index <- !is.na(x) & x %in% names(exact_map)
  x[index] <- unname(exact_map[x[index]])
  
  # ----------------------------------------------------------
  # 4. 지정된 값 앞에 지역명 추가
  # ----------------------------------------------------------
  
  # 신선대 ISO 데포의 내부 띄어쓰기 통일
  x[x == "신선대 ISO 데포"] <- "신선대 ISO데포"
  
  # 부산 추가
  busan_values <- c(
    "SKS복화",
    "뉴대원CY",
    "동명무역",
    "세양물류CY",
    "신부영",
    "신부영보관소",
    "신부영상차",
    "신선대 ISO데포",
    "천일용당",
    "삼익야드",
    "한솔야드",
    "세방상차"
  )
  
  x <- if_else(
    !is.na(x) & x %in% busan_values,
    paste("부산북항", x),
    x
  )
  
  busan_values <- c(
    "한타송정CY"
  )
  
  x <- if_else(
    !is.na(x) & x %in% busan_values,
    paste("부산신항", x),
    x
  )
  
  
  # 선광 2 / 선광2 통일
  x[x %in% c("선광 2", "선광2")] <- "선광2"
  
  # 인천 추가
  incheon_values <- c(
    "경원물산",
    "대부CY",
    "대야기업",
    "덕창야드",
    "빅로드야드",
    "서해물류",
    "스카이국제운송",
    "티지코리아야드",
    "승진CY",
    "인천14센터"
  )
  
  x <- if_else(
    !is.na(x) & x %in% incheon_values,
    paste("인천항", x),
    x
  )
  
  incheon_values <- c(
    "인천신국제",
    "신국제",
    "선광2",
    "선광종합",
    "선광종합(동주월드)"
  )
  
  x <- if_else(
    !is.na(x) & x %in% incheon_values,
    paste("인천신항", x),
    x
  )
  
  # ----------------------------------------------------------
  # 5. 북항 / 신항으로 시작하는 값에 부산 추가
  # 부산북항, 부산신항은 붙여쓰기
  # ----------------------------------------------------------
  x <- case_when(
    !is.na(x) & str_detect(x, "^북항\\s*") ~
      str_replace(x, "^북항\\s*", "부산북항 "),
    
    !is.na(x) & str_detect(x, "^신항\\s*") ~
      str_replace(x, "^신항\\s*", "부산신항 "),
    
    TRUE ~ x
  )
  
  # 북항멀티, 북항보관소처럼 공백이 없던 경우
  x <- case_when(
    !is.na(x) & str_detect(x, "^부산북항멀티$") ~
      "부산북항 멀티",
    
    !is.na(x) & str_detect(x, "^부산북항보관소$") ~
      "부산북항 보관소",
    
    TRUE ~ x
  )
  
  # ----------------------------------------------------------
  # 6. 부곡으로 시작하되 의왕이 없는 경우 의왕 추가
  # ----------------------------------------------------------
  x <- case_when(
    !is.na(x) &
      str_detect(x, "^부곡") &
      !str_detect(x, "^의왕\\s") ~
      paste("의왕", x),
    
    TRUE ~ x
  )
  
  # ----------------------------------------------------------
  # 7. 의왕으로 시작하면 뒤의 중복 (의왕) 제거
  # 예: 의왕 부곡고려(의왕) → 의왕 부곡고려
  #
  # (의왕B)는 내용이 다르므로 제거하지 않음
  # ----------------------------------------------------------
  index_uiwang <- !is.na(x) & str_detect(x, "^의왕\\s")
  x[index_uiwang] <- str_remove_all(x[index_uiwang], "\\(의왕\\)")
  
  # 괄호 제거 후 다시 공백 정리
  x <- str_squish(x)
  
  # ----------------------------------------------------------
  # 8. 인천신국제 중복 정리
  # ----------------------------------------------------------
  x <- case_when(
    x == "인천신국제 인천신국제" ~ "인천 신국제",
    x == "인천신국제" ~ "인천 신국제",
    TRUE ~ x
  )
  
  # ----------------------------------------------------------
  # 9. ooo / oooCY / ooo야드 / ooo보관소 통일
  # ----------------------------------------------------------
  unify_cy_yard_storage <- function(v) {
    
    non_missing <- unique(na.omit(v))
    
    if (length(non_missing) == 0) {
      return(v)
    }
    
    dictionary <- tibble(
      value = non_missing,
      
      # 끝에 붙은 CY, 야드, 보관소를 제거한 기본 명칭
      base = str_remove(
        non_missing,
        "(?:\\s*CY|\\s*야드|\\s*보관소)$"
      ),
      
      suffix = case_when(
        str_detect(non_missing, "CY$")     ~ "CY",
        str_detect(non_missing, "보관소$") ~ "보관소",
        str_detect(non_missing, "야드$")   ~ "야드",
        TRUE                               ~ "none"
      )
    ) %>%
      group_by(base) %>%
      mutate(
        n_variant = n_distinct(suffix),
        
        representative = case_when(
          any(suffix == "CY") ~
            value[which(suffix == "CY")[1]],
          
          any(suffix == "보관소") ~
            value[which(suffix == "보관소")[1]],
          
          any(suffix == "none") ~
            value[which(suffix == "none")[1]],
          
          TRUE ~ value[1]
        )
      ) %>%
      ungroup() %>%
      select(
        value,
        n_variant,
        representative
      )
    
    tibble(value = v) %>%
      left_join(dictionary, by = "value") %>%
      mutate(
        value = if_else(
          !is.na(n_variant) & n_variant >= 2,
          representative,
          value
        )
      ) %>%
      pull(value)
  }
  
  x <- unify_cy_yard_storage(x)
  
  # ----------------------------------------------------------
  # 10. 일반적인 '가장 긴 명칭' 통일
  #
  # 같은 지역 접두어를 가진 값 중 한 값이 다른 값에 완전히 포함되면
  # 더 긴 값을 대표값으로 사용
  #
  # 예:
  # 부산신항 대영보관소
  # → 부산신항 대영엘씨보관소
  # ----------------------------------------------------------
  longest_name_unify <- function(v) {
    
    unique_values <- unique(na.omit(v))
    
    # 비교 시 공백 제거
    compact_values <- str_remove_all(unique_values, "\\s+")
    
    # 자동 통일 금지 대상
    # 동원로엑스 냉장투/투보관소가 일반 동원로엑스로 합쳐지는 것 방지
    protected_values <- c(
      "부산신항 동원로엑스냉장투",
      "부산신항 동원로엑스투보관소"
    )
    
    result_map <- setNames(unique_values, unique_values)
    
    for (i in seq_along(unique_values)) {
      
      current <- unique_values[i]
      
      if (current %in% protected_values) {
        next
      }
      
      current_compact <- compact_values[i]
      
      # 첫 번째 지역 구분자가 동일한 값끼리만 비교
      current_region <- case_when(
        str_detect(current, "^부산신항") ~ "부산신항",
        str_detect(current, "^부산북항") ~ "부산북항",
        str_detect(current, "^인천항") ~ "인천항",
        str_detect(current, "^인천신항") ~ "인천신항",
        str_detect(current, "^인천") ~ "인천",
        str_detect(current, "^의왕") ~ "의왕",
        str_detect(current, "^광양") ~ "광양",
        str_detect(current, "^평택항") ~ "평택항",
        str_detect(current, "^양산") ~ "양산",
        TRUE ~ NA_character_
      )
      
      if (is.na(current_region)) {
        next
      }
      
      candidate_index <- which(
        unique_values != current &
          str_starts(unique_values, current_region) &
          str_detect(compact_values, fixed(current_compact)) &
          nchar(compact_values) > nchar(current_compact)
      )
      
      if (length(candidate_index) == 0) {
        next
      }
      
      candidate_values <- unique_values[candidate_index]
      
      # 보호 대상이 후보가 되어 일반 명칭을 흡수하지 않도록 제외
      candidate_values <- setdiff(candidate_values, protected_values)
      
      if (length(candidate_values) == 0) {
        next
      }
      
      # 가장 긴 후보를 선택
      candidate_values <- candidate_values[
        order(
          nchar(str_remove_all(candidate_values, "\\s+")),
          decreasing = TRUE
        )
      ]
      
      result_map[current] <- candidate_values[1]
    }
    
    unname(result_map[v])
  }
  
  if (isTRUE(use_longest_match)) {
    x <- longest_name_unify(x)
  }
  
  # ----------------------------------------------------------
  # 11. 가장 긴 명칭 처리 후 예외와 명시적 규칙 재적용
  # ----------------------------------------------------------
  
  # 동원로엑스 일반형만 보관소로 통일
  x[x == "부산신항 동원로엑스"] <-
    "부산신항 동원로엑스보관소"
  
  # 아래 두 값은 절대로 일반형과 합치지 않음
  x[x == "부산신항 동원로엑스냉장투"] <-
    "부산신항 동원로엑스냉장투"
  
  x[x == "부산신항 동원로엑스투보관소"] <-
    "부산신항 동원로엑스투보관소"
  
  # 베스트우암 최종 통일
  x[x %in% c(
    "부산북항 베스트우암",
    "부산북항 베스트우암보관소",
    "베트스우암",
    "베스트우암"
  )] <- "부산북항 베스트우암보관소"
  
  # 대한통운세방 최종 통일
  x[x %in% c(
    "부산신항 대한통운SB",
    "부산신항 대한통훈세방",
    "부산신항 대한통운 세방"
  )] <- "부산신항 대한통운세방"
  
  # BPT감만 괄호 최종 보정
  x[x %in% c(
    "부산북항 BPT감만(BIT",
    "부산북항 BPT감만(BIT)"
  )] <- "부산북항 BPT감만(BIT)"
  
  
  # 마지막 공백 정리
  x <- str_squish(x)
  
  # 언급되지 않은 값은 위 조건에 걸리지 않으면 원래 값 유지
  x
}

class(df)

df_clean <- df %>%
  mutate(
    상차지_원본_보존 = 상차지,
    상차지_전처리 = clean_loading_place(
      상차지,
      use_longest_match = TRUE
    )
  )

df_clean_removed <- df_clean %>%
  filter(!is.na(상차지_전처리))


comparison_table <- df_clean %>%
  count(
    상차지_원본_보존,
    상차지_전처리,
    name = "빈도"
  ) %>%
  arrange(
    is.na(상차지_전처리),
    상차지_원본_보존
  )

print(comparison_table, n = Inf)


############################################################
# 하차지 전처리
############################################################

clean_unloading_place <- function(x, use_longest_match = TRUE) {
  
  x <- as.character(x)
  
  # ----------------------------------------------------------
  # 0. 기본 문자열 정리
  # ----------------------------------------------------------
  
  # 앞뒤 공백 제거 + 연속 공백을 한 칸으로 통일
  x <- str_squish(x)
  
  # 빈 문자열은 NA
  x[x == ""] <- NA_character_
  
  # 괄호 주변 불필요한 공백 제거
  x <- str_replace_all(x, "\\s+\\(", "(")
  x <- str_replace_all(x, "\\(\\s+", "(")
  x <- str_replace_all(x, "\\s+\\)", ")")
  
  
  # ----------------------------------------------------------
  # 1. 띄어쓰기만 다른 값 통일
  #
  # 공백을 제거했을 때 글자가 동일한 값끼리 통일
  # 가장 많이 등장한 표기를 대표값으로 사용
  # 빈도가 같으면 더 긴 표기를 사용
  # ----------------------------------------------------------
  make_space_dictionary <- function(v) {
    
    tibble(
      value = v,
      no_space = str_remove_all(v, "\\s+")
    ) %>%
      filter(!is.na(value)) %>%
      count(no_space, value, name = "n") %>%
      group_by(no_space) %>%
      arrange(
        desc(n),
        desc(nchar(value)),
        value,
        .by_group = TRUE
      ) %>%
      slice(1) %>%
      ungroup() %>%
      select(
        no_space,
        representative = value
      )
  }
  
  space_dictionary <- make_space_dictionary(x)
  
  x <- tibble(
    value = x,
    no_space = str_remove_all(x, "\\s+")
  ) %>%
    left_join(space_dictionary, by = "no_space") %>%
    transmute(
      value = coalesce(representative, value)
    ) %>%
    pull(value)
  
  
  # ----------------------------------------------------------
  # 2. 삭제 대상
  # ----------------------------------------------------------
  remove_values <- c(
    "CMK",
    "CSS우암",
    "SNC",
    "극동엠이에스",
    "기타 복화",
    "공동물류",
    "동원로엑스",
    "동원로엑스냉장",
    "디알",
    "디알 하차",
    "디알하차",
    "리즈벤",
    "멀티",
    "미정",
    "밥테일",
    "신부영",
    "엠피콘 보관소",
    "영진CY",
    "에스엠 CY",
    "온그라운드",
    "청암CY",
    "태광하차",
    "티지야드",
    "티지코리아 야드",
    "티지코리아야드",
    "한진이나한타",
    "한타1CY"
  )
  
  x[x %in% remove_values] <- NA_character_
  
  
  # ----------------------------------------------------------
  # 3. 명시적인 값 통일
  # ----------------------------------------------------------
  exact_map <- c(
    
    # 6. 삽교역
    "삽교역" = "예산 삽교역",
    
    # 8. 에이엠에스하양공장
    "에이엠에스하양공장" = "경산 에이엠에스하양공장",
    
    # 9. 엘지화학대산공장
    "엘지화학대산공장" = "서산 엘지화학대산공장",
    
    # 10. 우암보관소
    "우암보관소" = "부산북항 베스트우암보관소",
    
    # 이미 일부 지역명이 붙어 있는 경우도 통일
    "부산 우암보관소" = "부산북항 베스트우암보관소",
    "부산북항 우암보관소" = "부산북항 베스트우암보관소",
    
    # 11. 우암하차예정
    "우암하차예정" = "부산북항 우암CY",
    "부산 우암하차예정" = "부산북항 우암CY",
    "부산북항 우암하차예정" = "부산북항 우암CY",
    
    # 4. 기타 세방부곡 CY
    "기타 세방부곡 CY" = "의왕 기타 세방부곡 CY",
    "기타 세방부곡CY" = "의왕 기타 세방부곡 CY",
    
    # 12. 청주 추가
    "중부CY 서연중부CY" =
      "청주 중부CY 서연중부CY",
    
    "중부CY 인터지스중부CY" =
      "청주 중부CY 인터지스중부CY",
    
    "중부CY 한진중부CY" =
      "청주 중부CY 한진중부CY",
    
    "중부CY 한타청원CY" =
      "청주 중부CY 한타청원CY",
    
    "인천14센터 : 인천광역시 중구 축항대로165번길 20" = "인천14센터",
    "인천 신국제" = "인천신항 신국제",
 
    "인천" = "인천항",
    "인천 승진CY" = "인천항 승진CY",
    "인천 라인올CY" = "인천신항 라인올CY",
    
    "부산보관" ="부산북항 부산보관",
    "부산" = "부산북항",
    
    "인천국제 인천국제" = "인천신항 인천국제"
  )
  
  index <- !is.na(x) & x %in% names(exact_map)
  
  x[index] <- unname(
    exact_map[x[index]]
  )
  
  
  # ----------------------------------------------------------
  # 4. 지정된 값 앞에 인천 추가
  # ----------------------------------------------------------
  incheon_values <- c(
    "FMCY",
    "FM CY",
    "IGFC",
    "IGFC밥테일",
    "IGFC 밥테일",
    "대부CY",
    "덕창야드",
    "서광창고",
    "인천14센터"
  )
  
  x <- if_else(
    !is.na(x) &
      x %in% incheon_values &
      !str_detect(x, "^인천\\s"),
    paste("인천항", x),
    x
  )
  
  
  incheon_values <- c(
    "신국제",
    "신여객",
    "한진인천컨테이너터미널"
  )
  
  x <- if_else(
    !is.na(x) &
      x %in% incheon_values &
      !str_detect(x, "^인천\\s"),
    paste("인천신항", x),
    x
  )
  
  
  # ----------------------------------------------------------
  # 5. 지정된 값 앞에 부산 추가
  # ----------------------------------------------------------
  busan_values <- c(
    "세양물류 자성대CY",
    "세양물류자성대CY",
    "이지스 우암",
    "이지스우암",
    "이지스우암CY",
    "이지콘 우암CY",
    "이지콘우암CY",
    "하차지 북항 멀티"
  )
  
  x <- if_else(
    !is.na(x) &
      x %in% busan_values &
      !str_detect(x, "^부산\\s"),
    paste("부산북항", x),
    x
  )
  
  busan_values <- c(
    "라인올신항",
    "이지스녹산CY",
    "한타송정CY"
  )
  
  x <- if_else(
    !is.na(x) &
      x %in% busan_values &
      !str_detect(x, "^부산\\s"),
    paste("부산신항", x),
    x
  )
  
  
  # ----------------------------------------------------------
  # 6. 북항 또는 신항으로 시작하면 부산북항 / 부산신항
  # ----------------------------------------------------------
  x <- case_when(
    
    !is.na(x) &
      str_detect(x, "^북항\\s*") ~
      str_replace(
        x,
        "^북항\\s*",
        "부산북항 "
      ),
    
    !is.na(x) &
      str_detect(x, "^신항\\s*") ~
      str_replace(
        x,
        "^신항\\s*",
        "부산신항 "
      ),
    
    TRUE ~ x
  )
  
  
  # 혹시 '부산 북항', '부산 신항' 형태가 있다면 붙여쓰기
  x <- str_replace(
    x,
    "^부산\\s+북항\\s*",
    "부산북항 "
  )
  
  x <- str_replace(
    x,
    "^부산\\s+신항\\s*",
    "부산신항 "
  )
  
  
  # ----------------------------------------------------------
  # 7. 부곡으로 시작하면 의왕 추가
  # ----------------------------------------------------------
  x <- case_when(
    
    !is.na(x) &
      str_detect(x, "^부곡") ~
      paste("의왕", x),
    
    TRUE ~ x
  )
  
  
  # '기타 세방부곡 CY'는 부곡으로 시작하지 않으므로 별도 보정
  x[x %in% c(
    "기타 세방부곡 CY",
    "기타 세방부곡CY"
  )] <- "의왕 기타 세방부곡 CY"
  
  
  # ----------------------------------------------------------
  # 8. 의왕으로 시작하고 끝에 (의왕)이 있으면 제거
  # ----------------------------------------------------------
  index_uiwang <- !is.na(x) &
    str_detect(x, "^의왕\\s")
  
  x[index_uiwang] <- str_remove(
    x[index_uiwang],
    "\\(의왕\\)$"
  )
  
  x <- str_squish(x)
  
  
  # ----------------------------------------------------------
  # 9. ooo / oooCY / ooo야드 통일
  #
  # 실제로 둘 이상의 형태가 같이 존재하는 경우에만 통일
  # CY가 존재하면 CY를 대표값으로 사용
  # CY가 없고 일반형이 있으면 일반형 사용
  # ----------------------------------------------------------
  unify_cy_yard_storage <- function(v) {
    
    non_missing <- unique(na.omit(v))
    
    if (length(non_missing) == 0) {
      return(v)
    }
    
    dictionary <- tibble(
      value = non_missing,
      
      # 값 끝의 CY, 야드, 보관소 제거하여 기본 명칭 생성
      base = str_remove(
        non_missing,
        "(?:\\s*CY|\\s*야드|\\s*보관소)$"
      ),
      
      suffix = case_when(
        str_detect(non_missing, "CY$")     ~ "CY",
        str_detect(non_missing, "보관소$") ~ "보관소",
        str_detect(non_missing, "야드$")   ~ "야드",
        TRUE                               ~ "none"
      )
    ) %>%
      group_by(base) %>%
      mutate(
        n_variant = n_distinct(suffix),
        
        representative = case_when(
          
          # CY가 있으면 CY로 통일
          any(suffix == "CY") ~
            value[which(suffix == "CY")[1]],
          
          # CY가 없고 보관소가 있으면 보관소
          any(suffix == "보관소") ~
            value[which(suffix == "보관소")[1]],
          
          # 일반형이 있으면 일반형
          any(suffix == "none") ~
            value[which(suffix == "none")[1]],
          
          # 그 외에는 야드
          TRUE ~ value[1]
        )
      ) %>%
      ungroup() %>%
      select(
        value,
        n_variant,
        representative
      )
    
    tibble(value = v) %>%
      left_join(dictionary, by = "value") %>%
      mutate(
        value = if_else(
          !is.na(n_variant) & n_variant >= 2,
          representative,
          value
        )
      ) %>%
      pull(value)
  }
  
  x <- unify_cy_yard_storage(x)
  
  
  # ----------------------------------------------------------
  # 10. 포함 관계이면 가장 긴 명칭으로 통일
  #
  # 예:
  # 부산북항 스타부경CY
  # 부산북항 스타부경물류CY
  #
  # → 부산북항 스타부경물류CY
  # ----------------------------------------------------------
  longest_name_unify <- function(v) {
    
    unique_values <- unique(na.omit(v))
    
    if (length(unique_values) == 0) {
      return(v)
    }
    
    # 공백을 제외하고 비교
    compact_values <- str_remove_all(
      unique_values,
      "\\s+"
    )
    
    result_map <- setNames(
      unique_values,
      unique_values
    )
    
    # 지역 접두어 판별 함수
    get_region <- function(value) {
      
      case_when(
        str_detect(value, "^부산신항") ~ "부산신항",
        str_detect(value, "^부산북항") ~ "부산북항",
        str_detect(value, "^인천신항") ~ "인천신항",
        str_detect(value, "^인천항") ~ "인천항",
        str_detect(value, "^의왕") ~ "의왕",
        str_detect(value, "^청주") ~ "청주",
        str_detect(value, "^부산") ~ "부산",
        str_detect(value, "^인천") ~ "인천",
        str_detect(value, "^예산") ~ "예산",
        str_detect(value, "^경산") ~ "경산",
        str_detect(value, "^서산") ~ "서산",
        TRUE ~ NA_character_
      )
    }
    
    regions <- vapply(
      unique_values,
      get_region,
      character(1)
    )
    
    for (i in seq_along(unique_values)) {
      
      current <- unique_values[i]
      current_compact <- compact_values[i]
      current_region <- regions[i]
      
      # 지역 구분이 없는 값은 자동 통일하지 않음
      if (is.na(current_region)) {
        next
      }
      
      candidate_index <- which(
        
        unique_values != current &
          
          regions == current_region &
          
          # 현재 문자열이 후보 문자열 안에 포함됨
          str_detect(
            compact_values,
            fixed(current_compact)
          ) &
          
          # 후보가 더 긴 경우만
          nchar(compact_values) >
          nchar(current_compact)
      )
      
      if (length(candidate_index) == 0) {
        next
      }
      
      candidate_values <-
        unique_values[candidate_index]
      
      # 가장 긴 후보 선택
      candidate_lengths <- nchar(
        str_remove_all(
          candidate_values,
          "\\s+"
        )
      )
      
      longest_candidate <-
        candidate_values[
          which.max(candidate_lengths)
        ]
      
      result_map[current] <-
        longest_candidate
    }
    
    unname(result_map[v])
  }
  
  if (isTRUE(use_longest_match)) {
    x <- longest_name_unify(x)
  }
  
  
  # ----------------------------------------------------------
  # 11. 자동 통일 이후 중요 규칙 재적용
  # ----------------------------------------------------------
  
  # 우암보관소
  x[x %in% c(
    "우암보관소",
    "부산 우암보관소",
    "부산북항 우암보관소"
  )] <- "부산북항 베스트우암보관소"
  
  # 우암하차예정
  x[x %in% c(
    "우암하차예정",
    "부산 우암하차예정",
    "부산북항 우암하차예정"
  )] <- "부산북항 우암CY"
  
  x[x == "부산신항 이지스녹산CY"] <- "부산신항 이지녹산CY"
  x[x == "부산신항 보관소(디앤피)"] <- "부산신항 디앰피보관소"
  x[x == "부산신항 보관소(태광)"] <- "부산신항 태광신항보관소"
  x[x == "부산신항 보관소(행운)"] <- "부산신항 행운디앤씨보관소"
  
  x[x %in% c(
    "부산신항 태준안골CY",
    "부산신항 태준보관소"
  )] <- "부산신항 태준안골보관소"
  
  # 마지막 공백 정리
  x <- str_squish(x)
  
  x
}


df_clean2 <- df_clean %>%
  mutate(
    하차지_원본_보존 = 하차지,
    하차지_전처리 = clean_unloading_place(
      하차지,
      use_longest_match = TRUE
    )
  )



comparison_table <- df_clean2 %>%
  count(
    하차지,
    하차지_전처리,
    name = "빈도"
  ) %>%
  arrange(
    is.na(하차지_전처리),
    하차지
  )

print(comparison_table, n = Inf)

sort(unique(df_clean2$하차지_전처리))



data2 <- df_clean2 %>% 
  filter(!is.na(하차지_전처리))
df <- data2 %>% 
  filter(!is.na(상차지_전처리))


df$상차지 == df$상차지_원본_보존

df <- df %>%
  select(-c(상차지, 하차지))

colnames(df)

###########################################################
# 중량: 1,2,3,4,5(톤 단위) → kg 단위로 변환
# 232020, 100000(이상치) 행 삭제
###########################################################
# 중량이 1~5인 행은 톤 단위로 잘못 입력된 것 -> ×1000 해서 kg 단위로 변환
df <- df %>%
  mutate(중량 = ifelse(중량 %in% c(1, 2, 3, 4, 5), 중량 * 1000, 중량))

# 이상치(232020, 100000) 행 삭제
df <- df %>%
  filter(!(중량 %in% c(232020, 100000)))


###########################################################
# 타입: 20T/K, 40O/T에서 '/' 제거, NA 행 삭제
###########################################################
# 타입 값에서 '/' 제거 
df <- df %>%
  mutate(타입 = gsub("/", "", 타입))
n_before6 <- nrow(df)

# 타입이 NA인 행 삭제
df <- df %>%
  filter(!is.na(타입))



###########################################################
# 컨테이너 앞 4자리(prefix)만 남김
###########################################################
df <- df %>%
  mutate(컨테이너 = substr(컨테이너, 1, 4))





###########################################################
# 지역 변수 추가 전처리
###########################################################
df <- df %>%
  mutate(
    지역 = str_replace(
      지역,
      "^강원도",
      "강원특별자치도"
    )
  )

df <- df %>%
  mutate(
    지역 = str_replace(지역, "^강원도", "강원특별자치도"),
    지역 = str_replace(지역, "^전라북도", "전북특별자치도"),
    지역 = str_replace(지역, "^경남\\s+", "경상남도 "),
    지역 = str_replace(지역, "^경북\\s+", "경상북도 "),
    지역 = str_replace(지역, "^아산시\\s+", "충청남도 아산시 "),
    지역 = str_replace(지역, "^서산시\\s+", "충청남도 서산시 "),
    지역 = str_replace(지역, "^화성시\\s+", "경기도 화성시zkz "),
    지역 = str_replace(지역, "^대구시\\s+", "대구광역시 "),
    지역 = str_replace(지역, "^울산시\\s+", "울산광역시 "),
    지역 = str_replace(지역, "^인천\\s+", "인천광역시 "),
    지역 = str_replace(지역, "^부산시\\s+", "부산광역시 "),
    지역 = str_replace(지역, "^부산\\s+", "부산광역시 "),
    지역 = str_replace(지역, "동동$", "동"),
    지역 = str_replace(지역, "^세종특별자치시 세종시", "세종특별자치시")
  )

df <- df %>%
  mutate(
    지역 = recode(
      지역,
      "경기 화성시 팔탄면" = "경기도 화성시 팔탄면",
      "경기도 고양시 일산동구 문원길 148" = "경기도 고양시 일산동구",
      "경기도 부천시 오정동" = "경기도 부천시 오정구 오정동",
      "경기도 성남시 분당구 금곡동" = "경기도 성남시 금곡동",
      "보령" = "충청남도 보령시",
      "중구 축항대로" = "인천광역시 중구 축항대로",
      "창원시 성산구 완암로" = "경상남도 창원시 성산구",
      "창원시 진해구 행암로" = "경상남도 창원시 진해구",
      "고령군 쌍림면" = "경상북도 고령군 쌍림면",
      "고양시 일산동구" = "경기도 고양시 일산동구",
      "과천시 광창로" = "경기도 과천시 광창로",
      "구미시 장천면" = "경상북도 구미시 장천면",
      "군산시 옥산면" = "전북특별자치도 군산시 옥산면",
      "금산군 복수면" = "충청남도 금산군 복수면",
      "김포시 통진읍" = "경기도 김포시 통진읍",
      "남동구 논현로" = "인천광역시 남동구 논현로",
      "남동구 능허대로" = "인천광역시 남동구 능허대로",
      "논산시 벌곡면" = "충청남도 논산시 벌곡면",
      "천안" = "충청남도 천안시",
      "천안시 동남구 수신면" = "충청남도 천안시 동남구 수신면",
      "충남 천안시 서북구" = "충청남도 천안시 서북구",
      "충남 홍성군 광천읍" = "충청남도 홍성군 광천읍",
      "충북 제천시" = "충청북도 제천시",
      "동교로" = "인천광역시 중구 동교로",
      "목포시" = "전라남도 목포시",
      "보령시 남포면" = "충청남도 보령시 남포면",
      "봉산" = "충청남도 예산군 봉산면",
      "아산" = "충청남도 아산시 음봉면",
      "안산시 단원구" = "경기도 안산시 단원구",
      "양산시 유산동" = "경상남도 양산시 유산동",
      "양지수 남면" = "강원특별자치도 양구군 남면",
      "원주군 소양면" = "강원특별자치도 원주시 소초면",
      "서천" = "충청남도 서천군",
      "아산 대진" = "충청남도 아산시 음봉면",
      "의왕ICD" = "경기도 의왕시 부곡동",
      "인천광역시 중구 운서동 3166-1 에이엠비" = "인천광역시 중구 운서동",
      "재작업" = "경기도 의왕시",
      "홍성" = "충청남도 홍성군",
      "홍성군 광천읍" = "충청남도 홍성군 광천읍",
      "세종특별자치시 세종시 부강면" = "세종특별자치시 부강면",
      "제천시 왕암동" = "충청북도 제천시 왕암동",
      "제천시 용두동" = "충청북도 제천시 용두동",
      "중구 연안부두로" = "인천광역시 중구 연안부두로",
      "천안시 서북구 직산읍 부송상덕길 5-14" = "충청남도 천안시 서북구 직산읍",
      "청주시 월명로" = "충청북도 청주시 월명로",
      "초일동" = "경기도 하남시 초일동",
      "충북 청주시" = "충청북도 청주시",
      "충주시 엄정면" = "충청북도 충주시 엄정면",
      "파주" = "경기도 파주시",
      "평택시 추팔" = "경기도 평택시 추팔산업단지",
      "홍성군 은하면" = "충청남도 홍성군 은하면",
      "신흥동3가" = "인천광역시 중구 신흥동3가",
      "완주군 소양면" = "전북특별자치도 완주군 소양면",
      "서구 길주로" = "인천광역시 서구 길주로",
      "서구 원창동" = "인천광역시 서구 원창동",
      "제친시 용두동" = "충청북도 제천시 용두동",
      "천안시 서북구 직산읍" = "충청남도 천안시 서북구 직산읍",
      .default = 지역
    )
  )


###########################################################
# 중복행 제거
###########################################################
df <- df %>% distinct()



###########################################################
# 작업시간이 문자(숫자로 변환 불가)인 행 제외
# 작업시간이 0,1,2,3,4,5인 거 제거
# 1130 1400 -> 값 맞추기
###########################################################


df <- df %>%
  mutate(작업시간 = suppressWarnings(as.numeric(작업시간))) %>%
  
  # 숫자로 변환 안 되는 행 제거
  filter(!is.na(작업시간)) %>%
  
  # 값이 정확히 0,1,2,3,4,5인 경우만 제거
  filter(!(작업시간 %in% 0:5)) %>%
  
  # 1130, 1400만 기존 형식으로 변환
  mutate(
    작업시간 = case_when(
      작업시간 == 1130 ~ 0.4791667,
      작업시간 == 1400 ~ 0.5833333,
      TRUE ~ 작업시간
    )
  )



###########################################################
# 작업시간(소수) -> HH:MM 형태로 복원
###########################################################

library(hms)
df$작업시간 <- as_hms(as.numeric(df$작업시간) * 86400)  # 하루=86400초
df$작업시간 <- format(df$작업시간, "%H:%M")

# 앞뒤 공백 제거 + 앞 5글자(HH:MM)만 남기기
df$작업시간 <- substr(trimws(df$작업시간), 1, 5)

###########################################################
# 작업일자 + 작업시간을 합쳐 작업일시 생성,
# 차량별 정렬 후 연속 작업 간 간격(공차 후보 구간) 계산
###########################################################
df$작업일시 <- as.POSIXct(
  paste(format(df$작업일자, "%Y-%m-%d"), df$작업시간),
  format = "%Y-%m-%d %H:%M",
  tz = "UTC"
)

# 차량 단위로 시간순 정렬
df <- df %>% arrange(차량, 작업일시)

# 같은 차량 내 연속 작업 간 간격(=공차 후보 구간) 계산
df <- df %>%
  group_by(차량) %>%
  mutate(
    이전작업일시 = lag(작업일시),
    이전하차지   = lag(하차지_전처리),
    공차시간_분  = as.numeric(difftime(작업일시, 이전작업일시, units = "mins"))
  ) %>%
  ungroup()




###################################################################################



# 중복 제거 
df_filtered <- df %>%
  distinct(across(-c(용차, 중량, 이전작업일시, 이전하차지, 공차시간_분, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 중량, 화주, 지역, 컨테이너, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 라인, 중량, 화주, 용차, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 화주, 용차, 지역, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 중량, 용차, 지역, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 화주, 중량, 용차, 지역, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 중량, 용차, 지역, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 타입, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 라인, 화주, 컨테이너, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 컨테이너, 타입, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE) %>% 
  distinct(across(-c(이전작업일시, 이전하차지, 공차시간_분, 컨테이너, 타입, 화주, 상차지_원본_보존, 하차지_원본_보존)), .keep_all = TRUE)

duplicated_rows <- df_filtered %>%
  group_by(차량, 작업일자, 작업시간, 상차지_전처리, 하차지_전처리) %>%
  filter(n() > 1) %>%
  arrange(차량, 작업일자, 작업시간) %>%
  ungroup()




df_filtered <- df_filtered %>%
  group_by(차량) %>%
  mutate(차량작업건수 = n()) %>%
  ungroup() %>%
  arrange(차량, 작업일자, 작업시간) %>%
  group_by(차량) %>%
  mutate(
    이전작업일시 = lag(작업일시),
    이전하차지 = lag(하차지_전처리),
    공차시간_시간 = as.numeric(
      difftime(작업일시, 이전작업일시, units = "hours")
    ),
    
    상차지_문자 = trimws(as.character(상차지_전처리)),
    하차지_문자 = trimws(as.character(하차지_전처리)),
    이전하차지_문자 = trimws(as.character(이전하차지)),
    
    상차지_앞2 = substr(상차지_문자, 1, 2),
    하차지_앞2 = substr(하차지_문자, 1, 2),
    이전하차지_앞2 = substr(이전하차지_문자, 1, 2),
    
    상차지_항만구분 = sub(
      "\\s.*$", "",
      trimws(substr(상차지_문자, 3, nchar(상차지_문자)))
    ),
    하차지_항만구분 = sub(
      "\\s.*$", "",
      trimws(substr(하차지_문자, 3, nchar(하차지_문자)))
    ),
    이전하차지_항만구분 = sub(
      "\\s.*$", "",
      trimws(substr(이전하차지_문자, 3, nchar(이전하차지_문자)))
    ),
    
    # 현재 상차지와 현재 하차지가 같은 지역이지만 다른 항만인지
    동일지역_다른항만 =
      상차지_앞2 == 하차지_앞2 &
      상차지_항만구분 %in% c("항", "신항", "북항") &
      하차지_항만구분 %in% c("항", "신항", "북항") &
      상차지_항만구분 != 하차지_항만구분,
    
    # 이전 하차지와 현재 상차지가 서로 다른 위치인지
    이전하차지_상차지_다름 =
      이전하차지_앞2 != 상차지_앞2 |
      (
        이전하차지_앞2 == 상차지_앞2 &
          이전하차지_항만구분 %in% c("항", "신항", "북항") &
          상차지_항만구분 %in% c("항", "신항", "북항") &
          이전하차지_항만구분 != 상차지_항만구분
      ),
    
    # 1단계
    추정공차 = if_else(
      상차지_앞2 != 하차지_앞2 | 동일지역_다른항만,
      "O",
      "X"
    )
  ) %>%
  mutate(
    추정공차 = case_when(
      추정공차 == "O" &
        차량작업건수 == 1 ~ "O",
      
      추정공차 == "O" &
        차량작업건수 > 1 &
        이전하차지_상차지_다름 &
        공차시간_시간 >= 0 &
        공차시간_시간 <= 12 ~ "O",
      
      추정공차 == "O" &
        차량작업건수 > 1 ~ "X",
      
      TRUE ~ 추정공차
    )
  ) %>%
  ungroup() %>%
  select(
    -상차지_문자,
    -하차지_문자,
    -이전하차지_문자,
    -상차지_앞2,
    -하차지_앞2,
    -이전하차지_앞2,
    -상차지_항만구분,
    -하차지_항만구분,
    -이전하차지_항만구분,
    -동일지역_다른항만,
    -이전하차지_상차지_다름
  )

write.xlsx(df_filtered, "전처리_데이터.xlsx")

data <- df_filtered %>%
  filter(추정공차 == "O") %>%
  select(-추정공차)

write_xlsx(data, "공차_최종_전처리_데이터.xlsx")






###################################################################################
###################################################################################
###################################################################################
###################################################################################



