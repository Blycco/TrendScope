# Algorithm Evolution Log

TrendScope 의 클러스터링·키워드 추출 알고리즘이 어떻게 변해 왔는지, 왜 바꿨는지, **각 시점마다 데이터가 어떤 순서로 처리되었는지**를 기록. 파라미터 수치 튜닝·불용어 추가·DB 설정화·성능 최적화·버그픽스는 기록하지 않음. 알고리즘의 **구조**가 바뀐 시점만 등록.

> **관찰 예시 주의** — 각 버전 끝의 "관찰 예시" 는 알고리즘 거동 이해를 돕기 위한 **가상의 예** 이며, 실제 운영 DB 질의 결과가 아님.

각 버전은 다음 고정 포맷으로 기술.

- **문제** — 이전 버전의 한계
- **변경** — 구조적으로 무엇이 바뀌었는가
- **데이터 흐름** — 입력 → step-by-step 처리 → 출력
- **구조 스냅샷** — 그 시점 알고리즘의 블록 다이어그램
- **효과** — 어떤 종류의 오류가 해소됐는가
- **참고** — 근거 논문·기법
- **코드** — 영향받은 파일/함수

---

## 버전별 전체 파이프라인 서술

### Pipeline V1 (2026-03-17, `c6a18fc`) — 초기 버전

**TL;DR**
- 바뀐 것 : 최초 구현 (기준점)
- 바꾼 이유 : —

**흐름도**
```
① 기사 수집
      크롤러가 뉴스 제목·본문·출처·발행 시각을 긁어 옴
      ↓
② 똑같은 기사 걸러내기 (Dedupe)
      같은 뉴스가 여러 번 들어오면 한 건만 남기고 버림
      ↓
③ 글 다듬기 (Normalize)
      HTML 찌꺼기·링크·이메일·"ㅋㅋㅋㅋ" 같은 반복 글자를
      지워 깨끗한 문장만 남김
      ↓
④ 광고·도배글 제거 (SpamFilter)
      "△△ 할인", "↗↗ 클릭" 같은 스팸 탈락
      ↓
⑤ 핵심 단어 뽑기 (KeywordExtract)
      한글·영어 단어를 정규식으로 잘라냄
      → 불용어 제거 (은/는/the/and 등)
      → TF-IDF × BM25 점수 계산
        ("많이 나오면서 드문 단어" 일수록 고득점)
      → 상위 k 개 선정
      ↓
⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)
      이미 만들어진 트렌드 그룹과 키워드가 겹치는 기사는
      그 그룹에 흡수
      ↓
⑦ 새 주제끼리 묶기 (Cluster)
      남은 기사들을 한 건씩 훑으며
      기존 묶음의 대표 기사와 "키워드가 얼마나 겹치나"
      (Jaccard 유사도) 를 측정해 많이 겹치면 합류,
      아니면 새 묶음 개설 (그리디 single-linkage)
      ↓
⑧ 점수·요약·저장·캐시 데우기
      (Score → Summarize → Save → Warm cache)
      묶음에 중요도 점수와 요약문을 붙여
      트렌드 테이블에 저장하고 캐시에 올림
```

**쉬운 말로 풀어 쓴 처리 과정**

- **① 기사 수집**
  크롤러가 뉴스 사이트에서 제목·본문·출처·발행 시각을 묶어 가져온다.
- **② 똑같은 기사 걸러내기 (Dedupe)**
  같은 기사가 여러 번 들어왔을 때 한 건만 남기고 나머지는 버린다.
- **③ 글 다듬기 (Normalize)**
  본문 속 HTML 태그·링크·이메일·반복 자모 같은 지저분한 부분을 깨끗이 지운다.
- **④ 광고·도배글 제거 (SpamFilter)**
  광고성·도배성 글을 걸러낸다.
- **⑤ 핵심 단어 뽑기 (KeywordExtract)**
  한글·영어 단어를 정규식으로 잘라내고 "은/는/the/and" 같은 의미 없는 단어를 제외한 뒤, "이 기사에 많이 나오면서 다른 기사에는 드문 단어" 일수록 높은 점수를 주는 방식(TF-IDF × BM25) 으로 상위 단어를 뽑아 기사에 붙인다.
- **⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)**
  이미 살아 있는 트렌드 그룹과 키워드가 겹치는 기사를 먼저 그 그룹에 흡수시킨다.
- **⑦ 새 주제끼리 묶기 (Cluster)**
  남은 기사들을 한 건씩 훑으면서 이미 만들어진 묶음의 대표 기사와 키워드가 얼마나 겹치는지(Jaccard 유사도) 보고, 많이 겹치면 같은 묶음에 합류시키고 아니면 새 묶음을 연다 (그리디 single-linkage).
- **⑧ 점수·요약·저장·캐시 데우기**
  묶음마다 중요도 점수와 요약문을 붙여 트렌드 테이블에 저장하고, 대시보드용 캐시를 데운다.

**효과** — 파이프라인 골격이 자리 잡음. 키워드가 거의 일치하는 뉴스들은 한 묶음으로 잘 들어감.

**이 버전이 만든 새 문제** — "겹치는 단어" 에만 의존하기 때문에 **표현만 다를 뿐 같은 사건** 인 뉴스들이 서로 다른 묶음으로 흩어진다.

**관찰 예시 (가상)**
- 기사 A : "한은 금리 0.25%p 인상"
- 기사 B : "한국은행 기준금리 상향"
- V1 결과 : 두 기사의 키워드 교집합이 작아 **다른 묶음** 으로 분리

---

### Pipeline V2 (2026-04-06, `9f0e1c7`, #130) — 문장 의미를 이해하기 시작

**TL;DR**
- 바뀐 것 : 기사 본문을 한국어 문장 AI(KR-SBERT) 로 숫자 벡터화한 뒤, 키워드 겹침 외에 문장 의미·시각·매체까지 4요소 가중합으로 묶음 판단
- 바꾼 이유 : "표현만 다를 뿐 같은 사건" 을 V1 이 갈라놓는 문제를 해소

**흐름도**
```
① 기사 수집
      ↓
② 똑같은 기사 걸러내기 (Dedupe)
      ↓
③ 글 다듬기 (Normalize)
      ↓
④ 광고·도배글 제거 (SpamFilter)
      ↓
⑤ 핵심 단어 뽑기 (KeywordExtract)
      한글·영어 단어를 정규식으로 잘라냄
      → 불용어 제거 (은/는/the/and 등)
      → TF-IDF × BM25 점수 계산
        ("많이 나오면서 드문 단어" 일수록 고득점)
      → 상위 k 개 선정
      ↓
⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)
      ↓
★ ⑦ 기사 문장의 "의미" 를 숫자로 바꾸기 (Encode, 신규)
      기사 본문을 한국어 AI 문장 모델
      (KR-SBERT) 에 한꺼번에 태워
      "이 기사의 의미" 를 숫자 벡터로 붙임
      ↓
★ ⑧ 새 주제끼리 묶기 (Cluster) — 기준이 달라짐
      묶을지 말지를 네 가지 기준을 섞어 판단:
        · 키워드 겹침 (Jaccard, 가볍게 먼저 거름)
        · 문장 의미 유사도 (cosine)
        · 발행 시각 차이 (가까울수록 가점)
        · 같은 매체인지 여부
      네 점수를 가중 평균한 최종 유사도로
      "많이 비슷하면 합류, 아니면 새 묶음" 판단
      ↓
⑨ 점수·요약·저장·캐시 데우기
```

**쉬운 말로 풀어 쓴 처리 과정**

- **① 기사 수집**
  크롤러가 뉴스 사이트에서 제목·본문·출처·발행 시각을 묶어 가져온다.
- **② 똑같은 기사 걸러내기 (Dedupe)**
  같은 기사가 여러 번 들어왔을 때 한 건만 남기고 나머지는 버린다.
- **③ 글 다듬기 (Normalize)**
  본문 속 HTML 태그·링크·이메일·반복 자모 같은 지저분한 부분을 깨끗이 지운다.
- **④ 광고·도배글 제거 (SpamFilter)**
  광고성·도배성 글을 걸러낸다.
- **⑤ 핵심 단어 뽑기 (KeywordExtract)**
  한글·영어 단어를 정규식으로 잘라내고 "은/는/the/and" 같은 의미 없는 단어를 제외한 뒤, "이 기사에 많이 나오면서 다른 기사에는 드문 단어" 일수록 높은 점수를 주는 방식(TF-IDF × BM25) 으로 상위 단어를 뽑아 기사에 붙인다.
- **⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)**
  이미 살아 있는 트렌드 그룹과 키워드가 겹치는 기사를 먼저 그 그룹에 흡수시킨다.
- **★ ⑦ 기사 문장의 "의미" 를 숫자로 바꾸기 (Encode, 신규)**
  살아남은 기사의 본문을 한국어 문장 AI 모델(처음엔 다국어 MiniLM, 이후 한국어 성능 문제로 `snunlp/KR-SBERT-V40K-klueNLI-augSTS` 로 교체) 에 한꺼번에 태워, 각 기사마다 "이 문장의 의미" 를 나타내는 숫자 묶음(임베딩 벡터) 을 붙여 준다.
- **★ ⑧ 새 주제끼리 묶기 (Cluster) — 기준이 달라짐**
  - **판단 기준 4요소 가중합 (신규)**
    묶을지 말지를 네 점수의 가중합으로 판단한다 — 키워드 겹침(Jaccard) · 문장 의미 유사도(cosine) · 발행 시각 근접도(temporal) · 같은 매체 여부(source).
  - **조기 필터 (Jaccard 먼저, 신규)**
    "키워드 겹침" 을 먼저 싸게 계산해 많이 다른 쌍은 AI(임베딩) 계산 없이 걸러내고, 통과한 쌍만 cosine·temporal·source 점수를 더해 최종 유사도를 낸다.
  - **묶음 할당 방식**
    한 건씩 훑으며 가장 비슷한 묶음에 합류시키는 그리디 single-linkage 자체는 V1 과 동일.
- **⑨ 점수·요약·저장·캐시 데우기**
  묶음마다 중요도 점수와 요약문을 붙여 트렌드 테이블에 저장하고 대시보드용 캐시를 데운다.

**효과** — **표현이 달라도 뜻이 같은 뉴스** 가 같은 묶음으로 모이기 시작. 조기 필터로 SBERT 비용도 절감.

**이 버전이 만든 새 문제** — 여전히 그리디 할당이라 **입력 순서에 따라 결과가 달라지고**, 느슨한 연결로 서로 먼 주제들이 한 묶음에 이어 붙는 chaining 이 발생.

**관찰 예시 (가상)**
- 기사 A : "한은 금리 0.25%p 인상" / 기사 B : "한국은행 기준금리 상향"
- V1 결과 : 다른 묶음
- V2 결과 : cosine 유사도 0.8 이상 → **같은 묶음**, 대표는 먼저 들어온 A

---

### Pipeline V3 (2026-04-07, `126cbc2`·`b34b915`·`bd22fa8`·`5f69c84`, #134·#142·#136·#140) — 한국어 품사 분석 + 밀도 기반 묶기

**TL;DR**
- 바뀐 것 : 키워드 추출을 한국어 형태소 분석기(kiwi POS) + bigram 으로 교체, 묶음 알고리즘을 밀도 기반(HDBSCAN) 으로 교체 + centroid σ 후처리
- 바꾼 이유 : V2 의 조사·어미 오염 키워드와 입력 순서 의존·chaining 문제를 동시에 해소

**흐름도**
```
① 기사 수집
      ↓
② 똑같은 기사 걸러내기 (Dedupe)
      ↓
③ 글 다듬기 (Normalize)
      ↓
④ 광고·도배글 제거 (SpamFilter)
      ↓
★ ⑤ 핵심 단어 뽑기 (KeywordExtract) — 내부가 바뀜
      ★ 단어 잘라내는 방식 교체:
          1순위: 한국어 형태소 분석기로
                 "명사만" 골라냄 (kiwipiepy POS)
          2순위: 통계 기반 단어 분석기 (soynlp)
          3순위: 옛날 정규식 (마지막 수단)
      ↓
      불용어 제거 → 단어 점수 매기기 (TF-IDF × BM25)
      ↓
      ★ 두 단어 붙은 표현 뽑기 (Bigram):
          "아이폰 출시" "금리 인상" 처럼 자주 붙어
          나오는 쌍(2번 이상)을 합쳐 하나의 키워드로
          (점수는 각 단어 점수 평균의 절반)
      ↓
      한 단어 + 두 단어 합쳐 상위 k 개 선정
      ↓
⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)
      ↓
⑦ 문장 의미 숫자화 (Encode, KR-SBERT)
      ↓
★ ⑧ 새 주제끼리 묶기 (Cluster) — 엔진 교체
      네 가지 유사도 점수를 "거리" 로 뒤집어
      기사 사이 전체 거리표(N×N) 를 만들고
      ★ 밀도 기반 알고리즘(HDBSCAN) 이
          "서로 빽빽이 모여 있는 기사들" 을 한꺼번에 묶음
      · 같은 묶음 → 한가운데 가장 가까운 기사를 대표로
      · 어디에도 안 속한 "외톨이" (noise) → 각자 1건 묶음
      ↓
      ★ 이질 멤버 떼어내기 (Refine):
          묶음의 평균 중심과 너무 동떨어진 기사는
          묶음에서 빼서 1건 묶음으로 분리
      ↓
      (기사가 너무 적거나 HDBSCAN 실패 → V2 방식으로 폴백)
      ↓
⑨ 점수·요약·저장·캐시 데우기
```

**쉬운 말로 풀어 쓴 처리 과정**

- **① 기사 수집**
  크롤러가 뉴스 사이트에서 제목·본문·출처·발행 시각을 묶어 가져온다.
- **② 똑같은 기사 걸러내기 (Dedupe)**
  같은 기사가 여러 번 들어왔을 때 한 건만 남긴다.
- **③ 글 다듬기 (Normalize)**
  HTML 태그·링크·이메일·반복 자모 같은 지저분한 부분을 지운다.
- **④ 광고·도배글 제거 (SpamFilter)**
  광고성·도배성 글을 걸러낸다.
- **★ ⑤ 핵심 단어 뽑기 (KeywordExtract) — 내부가 바뀜**
  - **단어 잘라내는 방식 (3단 폴백, 신규)**
    이전의 정규식은 조사·어미를 구분하지 못해 "성장하고·발전했다·있지만" 같은 것이 키워드로 올라오던 문제가 있었음. 이를 고치기 위해:
    - 1순위: 한국어 형태소 분석기 (kiwipiepy) 로 보통명사·고유명사·의존명사·외래어 같은 **"명사류" 만** 골라냄.
    - 2순위: (1순위 실패 시) 통계 기반 분석기 (soynlp).
    - 3순위: (둘 다 실패 시) 옛날 정규식.
  - **불용어 제거**
    영·한 불용어 사전을 거쳐 "은/는/the/and" 같은 흔하지만 의미 없는 단어를 제외.
  - **단어 점수 매기기**
    V1~V2 와 동일한 TF-IDF × BM25. "이 기사에 많이 나오면서 다른 기사엔 드문 단어" 일수록 높은 점수.
  - **Bigram 단계 (신규)**
    "아이폰_출시", "금리_인상" 처럼 **두 단어가 자주 붙어 나오는 표현** 을 2번 이상 등장한 경우만 뽑아, 부분 단어 점수들의 평균에 0.5 를 곱한 점수로 키워드 목록에 합친다.
  - **정렬·top-k**
    한 단어 + 두 단어 합쳐 점수순으로 상위 k 개 선정.
- **⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)**
  이미 살아 있는 트렌드 그룹과 키워드가 겹치는 기사를 먼저 그 그룹에 흡수시킨다.
- **⑦ 기사 문장의 "의미" 를 숫자로 바꾸기 (Encode)**
  살아남은 기사의 본문을 한국어 문장 AI 모델(KR-SBERT) 에 한꺼번에 태워 "이 문장의 의미" 를 나타내는 숫자 묶음(임베딩 벡터) 을 붙인다.
- **★ ⑧ 새 주제끼리 묶기 (Cluster) — 엔진 교체**
  - **거리표 만들기**
    네 가지 유사도 점수(키워드 겹침·문장 의미·시간 근접·매체 일치) 를 "거리 = 1 − 유사도" 로 뒤집어 기사 사이 전체 거리표(N×N) 를 만든다.
  - **묶기 알고리즘 교체 (신규)**
    V2 의 "한 건씩 훑어 가장 비슷한 묶음에 넣기" 방식에서 **"기사들이 서로 빽빽이 모여 있는 영역을 한꺼번에 찾아내는 밀도 기반 알고리즘 (HDBSCAN)"** 으로 교체.
  - **같은 묶음 대표 뽑기**
    한가운데 좌표에 가장 가까운 기사를 대표로.
  - **외톨이 기사 (노이즈)**
    어디에도 속하지 않는 기사는 각자 1건짜리 묶음으로 배출.
  - **이질 멤버 떼어내기 (Refine, 신규 후처리)**
    묶음 한가운데와 너무 동떨어진 기사를 묶음에서 빼내 1건짜리 묶음으로 분리.
  - **폴백**
    기사가 3건도 안 되거나 HDBSCAN 자체가 동작 못 하면 V2 의 "한 건씩 훑기" 방식으로 자동 전환.
- **⑨ 점수·요약·저장·캐시 데우기**
  묶음마다 중요도 점수와 요약문을 붙여 트렌드 테이블에 저장하고 대시보드 캐시를 데운다.

**효과** — "합성명사를 한 단어처럼 다루는 키워드" 와 "기사 순서에 흔들리지 않는 밀도 기반 묶기" 가 동시에 자리 잡음.

**이 버전이 만든 새 문제** — HDBSCAN 의 noise(어디에도 속하지 않는 기사) 가 모두 1건짜리 묶음으로 승격돼 **저품질 기사가 독립 트렌드를 만들어 대시보드가 어지러움**.

**관찰 예시 (가상)**
- 기사 A : "아이폰 신제품 출시" / 기사 B : "애플, 아이폰 출시 발표"
- V2 결과 : "아이폰", "출시" 등 단일 단어 위주 → 같은 묶음은 되지만 태그 가독성 낮음
- V3 결과 : "아이폰_출시" 가 bigram 으로 상위 태그 → **같은 묶음 + 의미 있는 합성 태그**

---

### Pipeline V4 (2026-04-13, `7da3b7c`, #221·#224) — 제목 우대 + 품질 낮은 외톨이 버리기 (현행)

**TL;DR**
- 바뀐 것 : 키워드 추출에서 제목/본문을 분리 입력하고 제목 단어에 빈도 배율(title_boost) 적용, HDBSCAN noise 에 품질 게이트(본문 ≥ 20자 AND 키워드 ≥ 3) 추가
- 바꾼 이유 : 장문 본문의 배경 단어에 진짜 토픽이 묻히는 문제와, 저품질 외톨이가 독립 트렌드로 올라오는 문제를 해소

**흐름도**
```
① 기사 수집
      ↓
② 똑같은 기사 걸러내기 (Dedupe)
      ↓
③ 글 다듬기 (Normalize)
      ↓
④ 광고·도배글 제거 (SpamFilter)
      ↓
★ ⑤ 핵심 단어 뽑기 (KeywordExtract) — 입력이 나뉨
      ★ 제목과 본문을 따로 받음
          본문은 너무 길면 앞쪽만 사용 (body_max_chars)
      ↓
      제목 / 본문 각각 V3 의 토큰화 체인 통과
      (kiwi → soynlp → regex)
      ↓
      ★ 제목에 나온 단어의 빈도에 배율을 곱함
          (title_boost, 예: 3배)
          → 제목에 있던 토픽이 본문 배경 단어에
            묻히지 않고 상위로 올라옴
      ↓
      합쳐진 빈도표로 TF-IDF×BM25 점수 + Bigram 결합
      → 상위 k 개
      ↓
⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)
      ↓
⑦ 문장 의미 숫자화 (Encode, KR-SBERT)
      ↓
★ ⑧ 새 주제끼리 묶기 (Cluster) — 외톨이 처리만 달라짐
      네 가지 유사도(키워드 겹침·문장 의미·시간 근접·
      매체 일치) 를 "거리 = 1 − 유사도" 로 뒤집어
      기사 사이 전체 거리표(N×N) 를 만들고
      밀도 기반 알고리즘(HDBSCAN) 이
      "서로 빽빽이 모여 있는 기사들" 을 한꺼번에 묶음
      · 같은 묶음 → 한가운데 좌표에 가장 가까운 기사를 대표로
      · 외톨이(noise) → ★ 품질 게이트 통과한 것만 살림
              조건: 본문 길이 ≥ 20자 AND 키워드 ≥ 3개
              → 통과 : 1건짜리 묶음으로 승격
              → 탈락 : 아예 묶음을 안 만들고 버림
      ↓
      이질 멤버 떼어내기 (Refine):
          묶음의 평균 중심과 너무 동떨어진 기사는
          묶음에서 빼서 1건 묶음으로 분리
      ↓
      (기사가 너무 적거나 HDBSCAN 실패 → V2 방식으로 폴백)
      ↓
⑨ 점수·요약·저장·캐시 데우기
```

**쉬운 말로 풀어 쓴 처리 과정**

- **① 기사 수집**
  크롤러가 뉴스 사이트에서 제목·본문·출처·발행 시각을 묶어 가져온다.
- **② 똑같은 기사 걸러내기 (Dedupe)**
  같은 기사가 여러 번 들어왔을 때 한 건만 남긴다.
- **③ 글 다듬기 (Normalize)**
  HTML 태그·링크·이메일·반복 자모 같은 지저분한 부분을 지운다.
- **④ 광고·도배글 제거 (SpamFilter)**
  광고성·도배성 글을 걸러낸다.
- **★ ⑤ 핵심 단어 뽑기 (KeywordExtract) — 입력이 나뉨**
  - **제목과 본문을 따로 받기 (신규)**
    그동안 "제목·본문을 한 덩어리" 로 취급하던 것을 바꿔 별도 입력으로 받는다. 본문이 너무 길면 앞쪽 일정 글자수(body_max_chars) 까지만 쓰고 뒤쪽은 버려, 장문 기사가 배경 단어로 결과를 흐리는 일을 줄인다.
  - **토큰화 체인**
    제목·본문 각각을 V3 의 분석기 체인 (1순위 kiwi 명사 필터 → 2순위 soynlp → 3순위 regex) 에 통과시켜 단어를 뽑는다.
  - **불용어 제거**
    영·한 불용어 사전으로 의미 없는 단어 제외 (V1 이후 동일).
  - **제목 가중치 적용 (title_boost, 신규)**
    **제목에서 나온 단어 빈도에 배율(예: 3배)** 을 곱해 본문 단어 빈도표와 합친다. 기자가 제목에 뽑아놓은 진짜 토픽이 본문 속 흔한 단어에 묻히지 않고 상위로 올라온다.
  - **단어 점수 매기기**
    합쳐진 빈도표 위에서 TF-IDF × BM25 실행.
  - **Bigram 결합**
    "아이폰_출시", "금리_인상" 처럼 두 단어가 2번 이상 자주 붙어 나오는 표현을 뽑아 부분 단어 점수 평균 × 0.5 점수로 키워드 목록에 합친다.
  - **정렬·top-k**
    한 단어 + 두 단어 합쳐 점수순으로 상위 k 개 선정.
- **⑥ 기존 트렌드에 붙이기 (MatchExistingGroups)**
  이미 살아 있는 트렌드 그룹과 키워드가 겹치는 기사를 먼저 그 그룹에 흡수시킨다.
- **⑦ 기사 문장의 "의미" 를 숫자로 바꾸기 (Encode)**
  기사 본문을 KR-SBERT 에 한꺼번에 태워 "이 문장의 의미" 를 나타내는 숫자 묶음(임베딩 벡터) 을 붙인다.
- **★ ⑧ 새 주제끼리 묶기 (Cluster) — 외톨이 처리만 달라짐**
  - **거리표 만들기**
    네 가지 유사도(키워드 겹침·문장 의미·시간 근접·매체 일치) 를 "거리 = 1 − 유사도" 로 뒤집어 기사 사이 전체 거리표를 만든다.
  - **밀도 기반 묶기 (HDBSCAN)**
    기사들이 빽빽이 모여 있는 영역을 한꺼번에 찾아 묶음으로 만든다.
  - **같은 묶음 대표 뽑기**
    한가운데 좌표에 가장 가까운 기사를 대표로.
  - **외톨이 기사 (노이즈) 의 품질 게이트 (신규)**
    V3 은 외톨이를 모두 1건짜리 묶음으로 올렸고, 그 결과 저품질 기사(제목 짧고 키워드 빈약) 까지 독립 트렌드가 되어 대시보드가 어지러웠음. V4 는 조건을 건다:
    - **본문 길이 ≥ 20자 AND 키워드 ≥ 3개** → 통과한 외톨이만 1건짜리 묶음으로 승격.
    - 그 외 외톨이 → 아예 묶음을 만들지 않고 파이프라인에서 버림.
  - **이질 멤버 떼어내기 (Refine)**
    묶음 한가운데와 너무 동떨어진 기사를 묶음에서 빼내 1건짜리 묶음으로 분리 (V3 에서 들어온 후처리 유지).
  - **폴백**
    기사가 3건도 안 되거나 HDBSCAN 자체가 동작 못 하면 V2 의 "한 건씩 훑기" 방식으로 자동 전환.
- **⑨ 점수·요약·저장·캐시 데우기**
  묶음마다 중요도 점수와 요약문을 붙여 트렌드 테이블에 저장하고 대시보드 캐시를 데운다.

**효과** — 제목에 등장한 토픽 단어가 본문에 묻히지 않고 상위로 올라오고, 저품질 외톨이가 파이프라인에서 걸러져 대시보드가 정돈됨.

**현재 상태** — 이 설계가 현재 운영 중인 파이프라인이다.

**관찰 예시 (가상)**
- 기사 : 제목 "금리 인상" / 본문 2000자 중 "금리" 3회, "경제" 12회, "성장" 10회
- V3 결과 : 본문 TF 에 밀려 "경제", "성장" 이 상위 → 실제 토픽 "금리" 가 뒤로 밀림
- V4 결과 : title_boost=2.0 으로 제목의 "금리" 빈도 2배 가산 → **"금리" 가 상위 키워드로 부상**
- 추가 : 본문 15자·키워드 1개뿐인 스텁 기사 → V3 은 1건 묶음 승격, V4 는 품질 게이트 탈락으로 **버림**

---

## Clustering

### V1 — Greedy Jaccard 단일-링크 (2026-03-17, `c6a18fc`)

**문제** — 없음 (최초 구현).

**변경** — 각 아이템을 순차적으로 훑으면서 이미 만들어진 클러스터 대표와의 Jaccard(키워드 집합) 유사도만 계산, threshold 이상이면 합류시키는 그리디 single-linkage. 유사도는 키워드 교집합/합집합 비율 하나.

**데이터 흐름**
```
입력: list[ClusterItem{ item_id, keywords: set[str] }]
  │
  ├─ Step 1. items 순회: 현재 아이템 X
  │     └─ 기존 clusters 각각의 대표 R 에 대해 Jaccard(X.keywords, R.keywords) 계산
  │
  ├─ Step 2. best_sim = max 유사도, best_cluster = argmax
  │
  ├─ Step 3. best_sim ≥ threshold ?
  │     ├─ Yes → best_cluster.members.append(X)
  │     └─ No  → new Cluster(representative=X) 생성 후 append
  │
출력: list[Cluster]
```

**구조 스냅샷**
```
[items iter] → [Jaccard vs existing reps] → [assign to best OR new cluster]
```

**한계로 드러난 것** — 어휘 일치에만 의존해서 "동의어·유사 표현·의미가 같은 다른 문장" 이 분리됨. 뉴스에선 매체별로 표현이 다른 같은 사건이 별개 클러스터로 흩어짐.

**참고** — Jaccard similarity (Paul Jaccard, 1901). Single-linkage greedy clustering.

**코드** — `backend/processor/shared/semantic_clusterer.py`, `backend/processor/stages/cluster.py`

---

### V2 — KR-SBERT 임베딩 + 4요소 가중합 유사도 (2026-04-06, `9f0e1c7`, #130)

**문제** — V1 은 같은 사건을 어휘 표현이 다르다는 이유로 갈라놓음. 의미 단위 비교 도구(임베딩)와, 단일 유사도가 포착 못 하는 축(시간·매체)이 필요.

**변경** — 문장 임베딩 모델을 파이프라인에 도입(`MiniLM-L6-v2` → 한국어 성능 문제로 `snunlp/KR-SBERT-V40K-klueNLI-augSTS` 교체). 유사도 식을 단일 Jaccard 에서 **4요소 가중합**으로 확장. Jaccard 는 cosine 계산 전 **조기 필터**로 재배치해 저유사 쌍의 SBERT 계산을 스킵.

**데이터 흐름**
```
입력: list[ClusterItem{ item_id, text, keywords, published_at, source_type }]
  │
  ├─ Step 1. 배치 인코딩: encode_texts([item.text ...]) → item.embedding: list[float]
  │                (단일 forward pass 로 N개 임베딩, 5-10x 속도)
  │
  ├─ Step 2. items 순회: 현재 아이템 X
  │     └─ 기존 clusters 각각의 대표 R 에 대해:
  │           (2-a) Jaccard(X.keywords, R.keywords) 계산
  │           (2-b) Jaccard < early_filter AND 임베딩 부재 → skip (sim = jac·w_jac)
  │           (2-c) cosine = cos(X.embedding, R.embedding)
  │           (2-d) temporal = exp(-Δhours / decay_hours)
  │           (2-e) source  = 1.0 if same source_type else 0.0
  │           (2-f) sim = w_cos·cosine + w_jac·jaccard + w_tmp·temporal + w_src·source
  │
  ├─ Step 3. best_sim/best_cluster 선택 → V1 그리디 할당 규칙 동일
  │
출력: list[Cluster]
```

**구조 스냅샷**
```
[encode_texts (KR-SBERT)]
        │
        ▼
[pairwise 4-weighted sim]  ← [Jaccard early filter]
        │
        ▼
[greedy assign (V1 loop)]
```

**효과** — 표현이 다른 같은 이슈가 한 클러스터로 수렴. 시간적으로 멀거나 같은 매체끼리 편중되는 경향이 가중치로 조절 가능해짐. 여전히 그리디 할당이라 입력 순서 의존성·chaining 문제는 남음.

**참고** — Sentence-BERT (Reimers & Gurevych 2019). KR-SBERT 는 한국어 KLUE-NLI / KorSTS augment 학습.

**코드** — `semantic_clusterer.py::{encode_texts, compute_similarity, ClusterConfig}`

---

### V3 — Centroid σ Outlier 후처리 스테이지 추가 (2026-04-07, `bd22fa8`, #136)

**문제** — V2 는 single-linkage 성질상 **chaining** 발생 — 느슨히 연결된 멤버 몇 개 때문에 실제로는 거리가 먼 두 서브그룹이 한 클러스터로 이어짐. 대표와는 유사한데 나머지 멤버와는 먼 "꼬리" 아이템이 클러스터 품질 저하.

**변경** — 클러스터 형성 직후 실행되는 **후처리 스테이지 `refine_clusters()`** 추가. centroid 대비 유사도가 낮은 멤버를 추방해 singleton 으로 재배치.

**데이터 흐름**
```
입력: V2 결과 list[Cluster]
  │
  ├─ Step 1. 각 cluster C 에 대해 centroid_C = mean([m.embedding for m in C.members])
  │
  ├─ Step 2. 각 member m 에 대해 sim(m, centroid_C) 계산
  │     ├─ m.embedding 있음 → cosine(m.embedding, centroid_C)
  │     └─ 임베딩 없음     → Jaccard(m.keywords, centroid-kws) fallback
  │
  ├─ Step 3. sims 분포에서 mean(μ)·std(σ) 산출 → threshold_refine = μ − σ
  │
  ├─ Step 4. sim(m) < threshold_refine 인 m 를 C 에서 제거
  │          → 새 singleton Cluster(representative=m) 로 분리
  │
출력: list[Cluster] (이질 멤버가 singleton 으로 분리된 상태)
```

**구조 스냅샷**
```
[encode_texts]
        │
        ▼
[pairwise 4-weighted sim]
        │
        ▼
[greedy assign]
        │
        ▼
[refine_clusters (centroid μ−σ eviction)]   ← 신규 스테이지
```

**효과** — chaining 으로 잘못 연결된 꼬리 멤버가 분리되어 클러스터 내부 밀도가 균질해짐. 다만 애초 그리디 할당이 잘못 엮어놓은 것을 **post-hoc 으로만** 정정하는 한계는 남음.

**코드** — `semantic_clusterer.py::{refine_clusters, _compute_centroid}`, `stages/cluster.py` 에서 `cluster_items()` 직후 호출

---

### V4 — HDBSCAN 밀도 기반 클러스터링 (2026-04-07, `5f69c84`, #140)

**문제** — V2+V3 조합도 본질은 그리디 — 입력 순서에 따라 결과가 달라지고, 전역 threshold 하나로는 **밀도가 제각각인 소·대 토픽**을 동시에 잘 잡지 못함. 작은 소토픽 보존하려 threshold 를 낮추면 대토픽이 chaining, 높이면 소토픽이 죽음.

**변경** — 클러스터링 엔진을 **HDBSCAN(밀도 기반, 계층적)** 으로 교체. 4요소 가중합 유사도를 그대로 활용하되 **precomputed distance matrix** 로 제공. 노이즈 포인트(`label == -1`) 는 일단 모두 singleton 클러스터로 배출. V3 의 `refine_clusters` 후처리는 유지. HDBSCAN 불가 혹은 아이템 3 미만일 때 V2 그리디로 폴백.

**데이터 흐름**
```
입력: list[ClusterItem] (with embeddings)
  │
  ├─ Step 1. N×N 거리행렬 D 구성
  │     └─ D[i][j] = max(0, 1 − sim(items[i], items[j]))
  │                  (sim 은 V2 의 4요소 가중합 그대로)
  │
  ├─ Step 2. model = HDBSCAN(metric="precomputed", min_cluster_size=2)
  │          labels = model.fit_predict(D)     → ndarray[int]
  │
  ├─ Step 3. labels 로 그룹핑
  │     ├─ label ≥ 0 : 같은 label 끼리 묶어 멤버 모음
  │     │            → centroid 최근접 아이템 = representative, 나머지 = members
  │     └─ label == −1 (noise) : 각각 singleton Cluster
  │
  ├─ Step 4. refine_clusters(clusters)  ← V3 단계 유지
  │
  ├─ Fallback 분기
  │     if (len(items) < 3) or (HDBSCAN import 실패) or (fit_predict 예외)
  │         → _cluster_greedy(items) 로 V2 경로 재실행
  │
출력: list[Cluster]
```

**구조 스냅샷**
```
[encode_texts]
        │
        ▼
[pairwise 4-weighted sim → distance matrix D]
        │                                           ┐
        ▼                                           │
[HDBSCAN (precomputed, min_cluster_size=2)]        │ fallback 경로
        │                                           │
        ▼                                           ▼
[label grouping  +  noise → singleton]       [greedy assign (V2)]
        │                                           │
        └──────────────┬────────────────────────────┘
                       ▼
              [refine_clusters (V3)]
```

**효과** — 입력 순서 의존성 제거. 밀도 편차 큰 뉴스 분포에서 소·대 토픽이 각자 자연스러운 density 로 묶임. noise label 덕분에 "어디에도 속하지 못하는 아이템" 이 자동 식별됨.

**참고** — Campello et al. 2013, *Density-Based Clustering Based on Hierarchical Density Estimates*. BERTopic 의 pipeline 구성(SBERT → clustering → topic repr) 을 그대로 차용하진 않았지만 같은 철학.

**코드** — `semantic_clusterer.py::{_cluster_hdbscan, _cluster_greedy, cluster_items, _pick_representative}`

---

### V5 — HDBSCAN Noise 품질 게이트 (2026-04-13, `75e36b0` / `7da3b7c`, #221·#224)

**문제** — V4 의 "noise 는 무조건 singleton 으로" 정책이 저품질 뉴스(짧은 제목·키워드 빈약)까지 전부 독립 트렌드로 만들어냄. 대시보드에 의미 없는 1건짜리 트렌드가 난립.

**변경** — label == −1 의 singleton 승격 단계에 **품질 게이트** 삽입. 텍스트 길이와 키워드 개수 둘 다 임계를 넘을 때만 singleton 으로 올리고, 아니면 클러스터 자체를 생성하지 않음(파이프라인에서 탈락).

**데이터 흐름**
```
입력: list[ClusterItem] (with embeddings)
  │
═══ Step 1 ~ 2 : V4 와 동일 ══════════════════════════════════════════
  │
  ├─ Step 1. N×N 거리행렬 D 구성
  │     └─ D[i][j] = max(0, 1 − sim(items[i], items[j]))
  │                  (sim 은 V2 의 4요소 가중합 그대로)
  │
  ├─ Step 2. model = HDBSCAN(metric="precomputed", min_cluster_size=2)
  │          labels = model.fit_predict(D)     → ndarray[int]
  │
═══ ★ Step 3 : V5 에서 noise 분기 교체 ═══════════════════════════════
  │
  ├─ Step 3. labels 로 그룹핑
  │     │
  │     ├─ label ≥ 0  (묶음 멤버)   ← V4 와 동일
  │     │      └─ 같은 label 끼리 묶어 멤버 모음
  │     │         → centroid 최근접 아이템 = representative
  │     │         → 나머지 = members
  │     │
  │     └─ label == −1  (noise)    ← ★ V5 신규: 품질 게이트
  │            각 아이템 n 에 대해
  │            len(n.text) >= 20  AND  len(n.keywords) >= 3 ?
  │                ├─ Yes → singleton Cluster 로 승격
  │                └─ No  → drop (클러스터 미생성, 파이프라인 탈락)
  │            (V4 까지는 조건 없이 모두 singleton 으로 승격했음)
  │
═══ Step 4 ~ Fallback : V4 와 동일 ═══════════════════════════════════
  │
  ├─ Step 4. refine_clusters(clusters)   ← V3 의 centroid μ−σ eviction 유지
  │
  ├─ Fallback 분기
  │     if (len(items) < 3) or (HDBSCAN import 실패) or (fit_predict 예외)
  │         → _cluster_greedy(items) 로 V2 경로 재실행
  │
출력: list[Cluster]
```

**구조 스냅샷**
```
[encode_texts]
        │
        ▼
[pairwise 4-weighted sim → distance matrix D]
        │                                           ┐
        ▼                                           │
[HDBSCAN (precomputed, min_cluster_size=2)]        │ fallback 경로
        │                                           │
        ▼                                           │
[label grouping]                                    │
    │                                               │
    ├─ label ≥ 0  → [members → centroid-closest rep]│
    │                                               │
    │   ══════════════════════════════════════════  │
    │   ★ V5 신규: noise quality gate              │
    └─ label == −1 → [len(text)≥20 AND len(kw)≥3]? │
                          Yes → [singleton]         │
                          No  → [drop]              │
    │   ══════════════════════════════════════════  │
        │                                           ▼
        │                                    [greedy assign (V2)]
        │                                           │
        └──────────────────┬────────────────────────┘
                           ▼
                  [refine_clusters (V3)]
```

**효과** — 1건짜리 무의미 트렌드 대폭 감소. 이후 운영 중 threshold 수치(15자 → 20자, kw 2 → 3) 튜닝이 이어졌으나 그건 파라미터 조정 범주라 이 문서에 기록하지 않음.

**코드** — `semantic_clusterer.py::_cluster_hdbscan` 의 noise 분기 (`line ~346`)

---

## Keyword Extraction

### V1 — TF-IDF × BM25 + Regex Tokenizer (2026-03-17, `c6a18fc`)

**문제** — 없음 (최초 구현).

**변경** — 정규식 토크나이저 + TF-IDF × BM25 점수.

**데이터 흐름**
```
입력: text: str
  │
  ├─ Step 1. 정규식 추출
  │     ├─ [가-힣]{2,}  → 한국어 토큰 리스트
  │     └─ [a-zA-Z]{2,} → 영어 토큰 리스트 (lowercase)
  │
  ├─ Step 2. 토큰 필터
  │     ├─ 길이 2~30
  │     ├─ 영어 불용어(63) 제거
  │     └─ 한국어 불용어(62) 제거
  │
  ├─ Step 3. Counter(tokens) → term_counts, doc_length = len(tokens)
  │
  ├─ Step 4. corpus_stats.update(tokens, doc_length)
  │          (doc_count, avg_doc_length, doc_freq 누적)
  │
  ├─ Step 5. 각 term 에 대해 score 계산
  │     ├─ tf   = term_counts[term] / doc_length
  │     ├─ idf  = log((N − df + 0.5) / (df + 0.5) + 1)
  │     ├─ bm25 = idf · tf·(k1+1) / (tf + k1·(1−b + b·dl/avg_dl))
  │     └─ score = tf·idf · bm25   (TF-IDF × BM25 곱)
  │
  ├─ Step 6. 정렬 desc, top-k slice
  │
출력: list[Keyword{term, score, frequency}]
```

**구조 스냅샷**
```
[regex tokenize (KO+EN)] → [stopwords filter] → [corpus stats update]
                                        │
                                        ▼
                          [per-term TF-IDF × BM25 scoring]
                                        │
                                        ▼
                            [sort desc → top-k]
```

**한계로 드러난 것** — 정규식은 품사 무시 → "기술이", "성장하고", "발전했다" 같은 조사·어미 붙은 어절이 그대로 키워드로 뽑힘. 복합명사·신조어는 쪼개지거나 누락.

**코드** — `keyword_extractor.py::{_tokenize_simple, _compute_tf, _compute_idf, _compute_bm25, extract_keywords}`

---

### V2 — kiwipiepy POS 명사 필터 + 토크나이저 폴백 체인 (2026-04-07, `126cbc2`, #134)

**문제** — V1 regex 가 한국어 형태소를 무시. 조사·어미가 키워드로 오염.

**변경** — V1 의 Step 1 (토큰 추출) 단계를 **3단 폴백 체인**으로 교체. 이후 Step 2~6 은 동일.

**데이터 흐름**
```
입력: text: str
  │
═══ ★ Step 1 : V2 에서 교체 (토크나이저 체인) ════════════════════════
  │
  ├─ Step 1. 토크나이저 체인 (앞 단계 실패 시 다음으로 폴백)
  │     │
  │     ├─ 1-a) kiwi = _get_kiwi()
  │     │       tokens = kiwi.tokenize(text)
  │     │       └─ 품사 필터: token.tag ∈ {NNG, NNP, NNB, SL} 만 남김
  │     │
  │     ├─ 1-b) (kiwi 결과가 None) → soynlp LTokenizer.tokenize(text)
  │     │
  │     └─ 1-c) (둘 다 실패) → V1 의 regex 경로
  │              [가-힣]{2,} + [a-zA-Z]{2,}
  │     (V1 은 이 단계가 처음부터 regex 하나뿐이었음)
  │
═══ Step 2 ~ 6 : V1 과 동일 ══════════════════════════════════════════
  │
  ├─ Step 2. 토큰 필터
  │     ├─ 길이 2~30
  │     ├─ 영어 불용어(63) 제거
  │     └─ 한국어 불용어(62) 제거
  │
  ├─ Step 3. Counter(tokens) → term_counts, doc_length = len(tokens)
  │
  ├─ Step 4. corpus_stats.update(tokens, doc_length)
  │          (doc_count, avg_doc_length, doc_freq 누적)
  │
  ├─ Step 5. 각 term 에 대해 score 계산
  │     ├─ tf   = term_counts[term] / doc_length
  │     ├─ idf  = log((N − df + 0.5) / (df + 0.5) + 1)
  │     ├─ bm25 = idf · tf·(k1+1) / (tf + k1·(1−b + b·dl/avg_dl))
  │     └─ score = tf·idf · bm25   (TF-IDF × BM25 곱)
  │
  ├─ Step 6. 정렬 desc, top-k slice
  │
출력: list[Keyword{term, score, frequency}]
```

**구조 스냅샷**
```
══════════════════════════════════════
★ V2 신규: tokenize fallback chain
[kiwi POS (NNG/NNP/NNB/SL)]
        │  fail
        ▼
[soynlp LTokenizer]
        │  fail
        ▼
[regex (V1)]
══════════════════════════════════════
        │
        ▼
[stopwords filter]
        │
        ▼
[corpus stats update]
        │
        ▼
[per-term TF-IDF × BM25 scoring]
        │
        ▼
[sort desc → top-k]
```

**효과** — 조사·어미 어절("성장하고", "발전했다", "있지만") 제거. 키워드가 "명사 중심" 으로 정화됨. soynlp 는 신조어·비등록 복합명사 백업.

**참고** — kiwipiepy (Korean morphological analyzer, Kiwi 엔진). soynlp LTokenizer (통계 기반, 사전 불필요).

**코드** — `keyword_extractor.py::{_try_kiwi_tokenize, _try_soynlp_tokenize, _tokenize_simple, _get_kiwi}`

---

### V3 — Co-occurrence Bigram 확장 (2026-04-07, `b34b915`, #142)

**문제** — unigram 만 다뤄 "아이폰 출시", "금리 인상" 같은 합성 개념이 쪼개짐. 결합된 토픽이 사라져 클러스터 태그 가독성 저하.

**변경** — unigram 스코어링 완료 뒤에 **bigram 추출·점수·병합 단계**를 추가.

**데이터 흐름**
```
입력: text: str
  │
═══ Step 1 ~ 5 : V2 와 동일 (unigram 경로) ═══════════════════════════
  │
  ├─ Step 1. 토크나이저 체인 (kiwi → soynlp → regex 폴백)
  │     ├─ 1-a) kiwi POS 필터 (NNG/NNP/NNB/SL)
  │     ├─ 1-b) soynlp LTokenizer
  │     └─ 1-c) regex ([가-힣]{2,} + [a-zA-Z]{2,})
  │
  ├─ Step 2. 토큰 필터 (길이 2~30, 영·한 불용어 제거)
  │
  ├─ Step 3. Counter(tokens) → term_counts, doc_length = len(tokens)
  │
  ├─ Step 4. corpus_stats.update(tokens, doc_length)
  │
  ├─ Step 5. 각 term 의 unigram 점수 계산
  │     └─ score = tf·idf · bm25
  │        unigram_scores 로 보관 (Step 8 에서 재사용)
  │
═══ ★ Step 6 ~ 9 : V3 신규 (bigram 병합 경로) ═══════════════════════
  │
  ├─ Step 6. 인접 토큰 쌍 집계 (Step 1 에서 얻은 tokens 시퀀스 재활용)
  │     for i in range(len(tokens) − 1):
  │         bigram_str = tokens[i] + "_" + tokens[i+1]
  │         bigram_counts[bigram_str] += 1
  │
  ├─ Step 7. min_freq 필터
  │     bigram_counts = {bg: cnt for bg, cnt in bigram_counts.items() if cnt >= 2}
  │
  ├─ Step 8. bigram 점수 계산
  │     parts = bigram.split("_")
  │     avg   = mean([ unigram_scores[p] for p in parts ])
  │     bigram_score = avg × 0.5
  │
  ├─ Step 9. unigram + bigram 병합 → 점수 desc 정렬 → top-k slice
  │          (V2 에서는 Step 5 결과를 바로 정렬·슬라이스 했음)
  │
출력: list[Keyword] — term 에 "_" 가 있으면 bigram, 없으면 unigram
```

**구조 스냅샷**
```
[tokenize chain (kiwi → soynlp → regex)]
        │
        ▼
[stopwords filter]
        │
        ▼
[corpus stats update]
        │
        ▼
[per-term TF-IDF × BM25 scoring (unigram)]
        │
        └─► unigram_scores: dict
        │
══════════════════════════════════════════════════════════════
★ V3 신규: bigram 파이프라인 병합
        │
        ▼
[bigram pair extract (인접 쌍)]
        │
        ▼
[min_freq=2 filter]
        │
        ▼
[score = mean(unigram_parts) × 0.5]
        │
        ▼
[merge unigram + bigram]
══════════════════════════════════════════════════════════════
        │
        ▼
[sort desc → top-k]
```

**효과** — "아이폰_출시", "머신_러닝" 같은 합성 개념이 상위 키워드로 부상. 클러스터 태그에 의미 있는 합성어 노출.

**코드** — `keyword_extractor.py::{_extract_bigrams, extract_keywords}` 끝부분 bigram 병합

---

### V4 — Title/Body Split + Title Boost (2026-04-13, `7da3b7c`, #224)

**문제** — 지금까지 제목·본문이 한 덩어리. 뉴스의 핵심 토픽은 제목에 압축되는데, 장문 본문의 배경 단어 TF 에 밀려 실제 토픽이 상위에서 빠지는 현상. 본문이 길면 IDF·BM25 계산에도 노이즈 기여.

**변경** — `extract_keywords()` 의 입력 시그니처를 `(text: str)` → `(title: str, body: str)` 로 분리 지원 (기존 text 파라미터는 backward-compat 유지). 내부에서 **title·body 각각 토큰화** 후 title 토큰 빈도에 **title_boost 배율** 곱해서 merge. body 는 `body_max_chars` 로 선절단.

**데이터 흐름**
```
입력: title: str, body: str (또는 legacy text: str)
  │
  ├─ Step 0. 입력 정규화
  │     if use_split:
  │         body_text = body[:body_max_chars]    ← 본문 길이 상한
  │         title_text = title
  │     else:
  │         raw_text = text (단일 경로 — V3 동일)
  │
  ├─ Step 1. title / body 각각 V2 토크나이저 체인 실행
  │     title_tokens = tokenize_chain(title_text)
  │     body_tokens  = tokenize_chain(body_text)
  │     ※ 둘 다 V2 의 kiwi → soynlp → regex + stopwords 필터까지 동일 적용
  │
  ├─ Step 2. Counter 합성
  │     title_counter = Counter(title_tokens)
  │     body_counter  = Counter(body_tokens)
  │     merged        = Counter()
  │     for term, cnt in title_counter.items():
  │         merged[term] += int(cnt * title_boost)   ← title 가중
  │     for term, cnt in body_counter.items():
  │         merged[term] += cnt
  │
  ├─ Step 3. merged 를 기반으로 V1~V3 의 스코어링 + bigram 병합 실행
  │     (corpus_stats.update, TF-IDF × BM25, bigram 추출 모두 merged 기준)
  │
출력: list[Keyword] — 제목 단어 가중으로 실제 토픽이 상위에 노출
```

**구조 스냅샷 변화** — 입구에 split + boost 경로 추가.
```
[ (title, body) split ]
        │                     │
        ▼                     ▼
[title → tokenize chain]  [body[:body_max_chars] → tokenize chain]
        │                     │
        ▼                     ▼
[Counter(title) × title_boost] ─┐
                                ├─► [merged Counter]
         [Counter(body)] ───────┘
                                │
                                ▼
           [TF-IDF×BM25 scoring  +  bigram 병합 (V3)]
                                │
                                ▼
                        [sort desc → top-k]
```

**효과** — 제목에 등장한 토픽 명사가 본문 배경 단어에 묻히지 않고 상위로 올라옴. body_max_chars 로 장문 기사 편향 억제. title_boost 는 admin_settings 로 노출되어 운영 튜닝 가능.

**코드** — `keyword_extractor.py::extract_keywords` 의 `use_split` 분기 (title_text / body_text / merged Counter 구간)

---

## Current Architecture (V5 / V4 기준, 2026-04-14)

### 전체 파이프라인 위치 (`backend/processor/pipeline.py::process_articles`)

```
Stage 1.  Dedupe                        (stage_dedupe)
Stage 2.  Normalize                     (stage_normalize)
Stage 3.  SpamFilter                    (stage_spam_filter)
Stage 4.  KeywordExtract      ← V4      (stage_extract_keywords)
Stage 4.5 Match existing groups         (stage_match_existing_groups)
Stage 5.  SemanticClusterer   ← V5      (stage_cluster)
Stage 6.  Score                         (stage_score)
Stage 6.5 Summarize                     (stage_summarize)
Stage 7.  Save                          (stage_save)
Stage 8.  Warm cache                    (stage_warm_cache)
```

### Clustering 내부 (V5, Stage 5)
```
[articles with keywords + text + published_at + source_type]
        │
        ▼
[batch encode_texts → item.embedding]
        │
        ▼
[pairwise 4-weighted sim (cos + jac + tmp + src) → distance matrix]
        │                                                  ┐
        ▼                                                  │ fallback
[HDBSCAN(metric="precomputed", min_cluster_size=2)]       │
        │                                                  ▼
[label grouping]                                   [_cluster_greedy]
    │                                                      │
    ├─ label ≥ 0  → [members → centroid-closest rep]       │
    └─ label == −1 → [len(text)≥20 AND len(kw)≥3] ?        │
                          Yes → [singleton]                │
                          No  → [drop]                     │
        │                                                  │
        └──────────────────────┬───────────────────────────┘
                               ▼
                    [refine_clusters (μ−σ eviction)]
                               │
                               ▼
                      [list[Cluster] → Stage 6]
```

### Keyword Extraction 내부 (V4, Stage 4)
```
[article with (title, body)]
        │
        ├─ title ──► [tokenize chain: kiwi→soynlp→regex + stopwords]
        │                  │
        │                  ▼
        │           [Counter × title_boost]
        │                  │
        └─ body[:body_max_chars] ──► [tokenize chain] → [Counter]
                                                │
                ┌───────────────────────────────┘
                ▼
        [merged Counter]
                │
                ▼
        [corpus stats update → TF·IDF·BM25 per term]
                │
                ▼
        [bigram extract → min_freq=2 → score × 0.5]
                │
                ▼
        [merge unigram + bigram → sort desc → top-k]
                │
                ▼
        [list[Keyword] → 기사에 부착 → Stage 4.5]
```

### 현행 파라미터 (2026-04-14 기준)

| 위치 | 파라미터 | 값 | 비고 |
|---|---|---|---|
| Clustering V5 | `min_cluster_size` (HDBSCAN) | 2 | 고정 |
| Clustering V5 | noise 게이트 `text_len` | 20 | 하드코드 (`_cluster_hdbscan` 내부) |
| Clustering V5 | noise 게이트 `kw_count` | 3 | 하드코드 |
| Clustering V3 | σ-refine 계수 | 기본값 1.0 (admin_settings `outlier_sigma` 로 덮어쓰기 가능) | μ−σ 컷오프 |
| Clustering V2 | `cosine_weight` | 기본값 0.50 (admin_settings 로 덮어쓰기 가능) | 4요소 중 문장 의미 |
| Clustering V2 | `jaccard_weight` | 기본값 0.25 (admin_settings 로 덮어쓰기 가능) | 4요소 중 키워드 겹침 |
| Clustering V2 | `temporal_weight` | 기본값 0.15 (admin_settings 로 덮어쓰기 가능) | 4요소 중 시간 |
| Clustering V2 | `source_weight` | 기본값 0.10 (admin_settings 로 덮어쓰기 가능) | 4요소 중 매체 |
| Clustering V2 | `jaccard_early_filter` | 기본값 0.10 (admin_settings 로 덮어쓰기 가능) | 이 값 미만이면 cosine 스킵 |
| Clustering V2 | `threshold` (그리디 폴백) | 기본값 0.55 (admin_settings 로 덮어쓰기 가능) | 폴백 경로에서만 사용 |
| Clustering V2 | `temporal_decay_hours` | 기본값 24.0 (admin_settings 로 덮어쓰기 가능) | 시간 점수 감쇠 |
| Keyword V4 | `title_boost` | 기본값 2.0 (admin_settings 로 덮어쓰기 가능) | 제목 토큰 빈도 배율 |
| Keyword V4 | `body_max_chars` | 기본값 500 (admin_settings 로 덮어쓰기 가능) | 본문 선절단 길이 |
| Keyword V3 | bigram `min_freq` | 2 | 고정 |
| Keyword V3 | bigram score 계수 | 0.5 | 고정 |
| Keyword V1 | BM25 `k1`, `b` | 1.5, 0.75 | 고정 |

### 다음 구조적 변경 후보 (미채택, 참고용)
- **임베딩 pooling 명시**: 기본 mean pooling 외 last-4-layer max concat 실험
- **UMAP 차원 축소** 후 HDBSCAN (BERTopic 전체 파이프라인 패턴)
- **계층적 병합**: 타이트 threshold 로 fine-grained 먼저 만든 뒤 centroid 간 거리로 merge
- **KeyBERT + MMR**: 문서 임베딩 vs n-gram 후보 임베딩 cosine 으로 의미적 핵심구 추출, MMR 로 중복 억제
- **LLM post-hoc refinement**: 클러스터 형성 후 LLM 이 이질 멤버 지적·추방, 자동 토픽 라벨 생성

각 후보는 별도 PR 로 도입되며, 채택 시 이 문서에 새 섹션으로 추가.

---

## 용어 사전

- **임베딩 (embedding)** — 문장을 수백 차원 실수 벡터로 바꾼 표현. 의미가 비슷한 문장은 벡터 공간에서 가까이 놓임.
- **TF-IDF × BM25** — 한 단어가 그 문서에 많이 나오면서(TF) 다른 문서에는 드물수록(IDF) 높은 점수를 주는 방식. BM25 는 문서 길이로 정규화한 개선형.
- **Jaccard 유사도** — 두 집합의 교집합 크기를 합집합 크기로 나눈 비율. 여기선 두 기사의 키워드 집합 겹침 측정용.
- **cosine 유사도** — 두 벡터가 이루는 각도의 cosine. 1 에 가까울수록 같은 방향(= 의미 유사).
- **centroid / μ−σ eviction** — 묶음 멤버 임베딩의 평균 좌표(centroid) 와 각 멤버 유사도 분포의 평균(μ)·표준편차(σ) 를 구한 뒤 `sim < μ − σ` 인 멤버를 묶음에서 빼 singleton 으로 분리.
- **HDBSCAN** — 밀도 기반 계층적 클러스터링. 점이 빽빽이 모인 영역을 클러스터로 인정하고, 드문 영역의 점은 noise(label −1) 로 표시.
- **noise (label −1)** — HDBSCAN 이 "어떤 클러스터에도 속하지 않는다" 고 판정한 점. V4 까지는 전부 singleton 으로 승격, V5 부터는 품질 게이트 통과한 것만 승격.
- **single-linkage / chaining** — 가장 가까운 한 쌍만 봐서 합치는 방식 → 서로 먼 두 서브그룹이 중간 점 하나로 이어 붙는 chaining 현상이 발생하기 쉬움.
- **bigram / min_freq** — 인접한 두 단어를 하나의 키워드로 취급(예: `아이폰_출시`). `min_freq` 이상으로 등장한 쌍만 채택.
- **title_boost / body_max_chars** — 제목 단어 빈도에 곱하는 배율 / 본문을 앞쪽 몇 글자까지만 쓸지의 상한. 둘 다 admin_settings 로 런타임 조정.
