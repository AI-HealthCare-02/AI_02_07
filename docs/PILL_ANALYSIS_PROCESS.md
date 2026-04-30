# 💊 알약 분석 시스템 — 전체 프로세스 문서

> 담당: 안은지  
> 최종 업데이트: v5.1

---

## 1. 전체 흐름 요약

```
사용자 이미지 업로드 (최대 2장: 앞면 / 뒷면)
        ↓
[전처리] 리사이즈 + EXIF 보정 (최대 1024px)
        ↓
[OCR] Clova OCR — 원본 + 180도 회전 병합
        ↓
[1단계] GPT Vision (detail:high) — 각인/색상/모양/분할선 추출
        ↓
[v5 보정] color 정규화 + multiple_pills 보정 + confidence 보정
        ↓
[2단계] imprint RAG 검색
  ├─ 모든 query variant로 vector 검색 (item_seq 기준 merge)
  ├─ metadata exact match (앞면/뒷면/swapped)
  ├─ 마크 hypothesis metadata fallback (v5.1)
  └─ rerank 점수 계산
        ↓
[조건부 2차 VLM] ENABLE_SECOND_PASS=true 시
  ├─ 희미한 각인 재판독
  ├─ 십자분할선 재확인
  ├─ 마크 재검사
  └─ candidate visual verification (마크 후보 발견 시)
        ↓
[매칭 실패 판단] 점수/색상/모양 조건 체크
        ↓
[3단계] 허가정보 DB 조회 + LLM 정제
        ↓
DB 저장 → 프론트 응답
```

---

## 2. 사용 기술 스택

| 구분 | 기술 | 용도 |
|---|---|---|
| OCR | Naver Clova OCR | 각인 텍스트 사전 추출 |
| Vision LLM | GPT-4o (detail:high) | 각인/색상/모양/분할선 판독 |
| Embedding | text-embedding-3-small | 검색 쿼리 벡터화 |
| Vector DB | PostgreSQL + pgvector | 코사인 유사도 검색 |
| Metadata | PostgreSQL JSONB | 각인/색상/모양 exact match |
| 정제 LLM | GPT-4o-mini | 허가정보 원문 → 사용자 친화적 요약 |

---

## 3. 단계별 상세 설명

### 3-1. 이미지 전처리

- 최대 5MB 제한
- 최대 1024px로 리사이즈 (비율 유지)
- EXIF 회전 정보 자동 보정
- JPEG quality=90으로 저장

### 3-2. Clova OCR

각인 텍스트를 사전에 추출해 GPT Vision의 참고값으로 제공.

**원본 + 180도 회전 병합:**
- 분할선 기준으로 한쪽 각인이 뒤집혀 있을 때 한쪽만 잡히는 문제 완화
- 두 결과를 토큰 단위로 중복 제거 후 병합

**OCR 힌트 약화:**
- 1글자 이하, 기호만인 경우 GPT에 전달하지 않음
- 전달 시 "OCR은 참고값이며 이미지가 우선" 명시

**앞뒤 swap 로직:**
- OCR 앞면이 숫자만이고 뒷면이 영문자면 자동 swap

### 3-3. GPT Vision 1차 분석

**모델:** GPT-4o, `detail:high`, `max_tokens=700`, `temperature=0`

**추출 항목:**
- `print_front` / `print_back`: 각인 문자 (마크/로고는 "마크")
- `score_line_front/back_type`: 없음 / 분할선 / 십자분할선 / 판독불가
- `front/back_left/right/top/bottom_text`: 분할선 영역별 각인
- `color`: 알약 본체 색상
- `shape`: 원형 / 타원형 / 장방형 / 삼각형 / 사각형 / 기타
- `dosage_form_hint`: 정제 / 경질캡슐 / 연질캡슐
- `imprint_confidence` / `color_confidence` / `shape_confidence`

**주요 판독 규칙:**
- 분할선 양쪽 각인을 left/right/top/bottom으로 분리 기록
- 마크/로고는 "마크"로 기록 (5, S, JS처럼 보여도 불확실하면 "마크")
- 반점/얼룩은 각인이 아님 → color_detail에만 기록
- 한 이미지에 앞뒷면이 함께 있을 때 각 면의 각인이 서로 다른 각도로 회전될 수 있음
  - 각 면을 독립적으로 0/90/180/270도 회전하며 판독
  - 회전 혼동 문자: `4↔7`, `6↔9`, `2↔5`, `d↔0`, `n↔u`, `M↔W`

### 3-4. v5 보정 (1단계 완료 직후)

**색상 정규화:**
```
녹색 → 초록, 흰색 → 하양, 노란색 → 노랑 등
```

**multiple_pills 보정:**
- 동일 색상/모양의 알약 앞뒷면이 한 이미지에 찍힌 경우
- `multiple_pills=True`이지만 색상/모양/각인이 일관되면 `False`로 보정

**confidence 보정 (calibrate_vlm_confidence):**
- 반점/점박이 알약: imprint_confidence 상한 0.65, color_confidence 상한 0.75
- 반점 색상을 기본색으로 오인 시: color_confidence 상한 0.55
- JS/5/S/15 등 마크 오인 가능 문자: imprint_confidence 상한 0.65
- 전체 confidence 상한: 0.95 (1.0 과신 방지)

### 3-5. 2단계 imprint RAG 검색

#### 검색 쿼리 생성 (build_rag_query_variants)

기본 variants:
```
[앞면 뒷면 색상 모양]
[뒷면 앞면 색상 모양]
[앞면 색상 모양]
[뒷면 색상 모양]
[색상 모양]
```

마크 hypothesis variants (v5.1 — JS/5/S 등 감지 시):
```
[마크 뒷면 색상 모양]
[뒷면 마크 색상 모양]
[마크 색상 모양]
```

#### 검색 방식

1. **모든 variant로 vector 검색** — item_seq 기준 merge/deduplicate
2. **metadata exact match** — `front_norm AND back_norm` 조건
3. **swapped match** — 앞뒤 바뀐 경우 대응
4. **마크 metadata fallback** (v5.1) — 마크+stable각인+색상+모양 SQL 직접 검색

#### 각인 정규화 (_normalize_imprint)

- 비ASCII → ASCII 변환 (Λ→A, 그리스 문자 등)
- 분할선/십자분할선 제거
- 대문자화, 공백/특수문자 제거
- "마크"/"로고"는 보존

---

## 4. Rerank 점수 계산

### 4-1. 점수 배분표

| 항목 | 조건 | 점수 |
|---|---|---|
| **각인 앞면** | exact match | +35 |
| **각인 뒷면** | exact match | +35 |
| **각인 (마크)** | query="마크" + DB=마크 | +35 |
| **각인 (마크 오인)** | query=JS/5/S + DB=마크 | +20 |
| **각인** | query=null → unknown | 0 (감점 없음) |
| **십자분할선** | 양쪽 모두 십자분할선 | +12 |
| **십자분할선** | 쿼리=십자, DB=일반분할선 | +6 |
| **분할선** | 양쪽 모두 분할선 있음 | +8 |
| **색상** | 토큰 세트 완전 일치 | +8 |
| **색상** | 토큰 일부 겹침 | +4 |
| **모양** | 정확 일치 | +8 |
| **모양** | 타원형 ↔ 장방형 | +5 |
| **모양** | 원형 ↔ 타원형 | +3 |
| **vector similarity** | 보조 점수 | `similarity × 10` |

**최종 점수:**
```
rerank_score = rerank_base + vector_similarity × 10
```

**앞뒤 swapped 비교:**
- direct(앞=앞, 뒤=뒤)와 swapped(앞=뒤, 뒤=앞) 중 높은 값 사용

---

## 5. 매칭 성공/실패 기준

### 5-1. 실패 조건 (하나라도 해당하면 실패)

| 조건 | 실패 이유 |
|---|---|
| `rerank_score < 45` | 최종 매칭 점수가 낮음 |
| `imprint_conf < 0.45` AND `color_conf < 0.6` AND `shape_conf < 0.6` | 이미지 특징이 전반적으로 불명확함 |
| 1위-2위 점수 차 `< 5` AND `imprint_conf < 0.6` | 상위 후보 간 점수 차이가 작고 각인 불명확 |
| 뒷면 각인 불일치 AND 색상 명확히 다른 그룹 | 각인+색상 동시 불일치 |
| 색상 명확히 다른 그룹 AND 모양 완전 불일치 | 색상+모양 동시 불일치 |
| RAG 후보 없음 | 임베딩 미구축 |

### 5-2. 색상 유사 그룹

같은 그룹 내 색상은 불일치로 보지 않음 (GPT 오인식 허용):

| 그룹 | 포함 색상 |
|---|---|
| 흰계열 | 하양, 아이보리 |
| 노란계열 | 노랑, 연노랑, 아이보리, 갈색, 주황 |
| 붉은계열 | 분홍, 빨강, 주황 |
| 초록계열 | 초록, 연두 |
| 파란계열 | 파랑, 보라 |
| 무채색계열 | 회색, 검정, 하양 |

---

## 6. 매칭 예시

### ✅ 매칭 성공 케이스

**케이스 1: 각인 양쪽 일치**
```
쿼리: 앞면=SCD, 뒷면=C6, 색상=하양, 모양=장방형
DB:   앞면=SCD, 뒷면=C6, 색상=하양, 모양=장방형

점수: 35 + 35 + 8(색상) + 8(모양) = 86점 → 성공
```

**케이스 2: 앞뒤 swap**
```
쿼리: 앞면=C6, 뒷면=SCD (사용자가 뒤집어 업로드)
DB:   앞면=SCD, 뒷면=C6

점수: swapped 35 + 35 = 70점 → 성공
```

**케이스 3: 마크 각인**
```
쿼리: 앞면=마크, 뒷면=10, 색상=초록, 모양=원형
DB:   앞면=마크, 뒷면=10, 색상=초록, 모양=원형

점수: 35(마크) + 35 + 8(색상) + 8(모양) = 86점 → 성공
```

**케이스 4: 마크 오인 (JS → 마크)**
```
쿼리: 앞면=JS, 뒷면=10, 색상=초록, 모양=원형
DB:   앞면=마크, 뒷면=10, 색상=초록, 모양=원형

점수: 20(JS vs 마크) + 35 + 8(색상) + 8(모양) = 71점 → 성공
```

**케이스 5: 색상 유사 그룹 허용**
```
쿼리: 앞면=ABC, 뒷면=123, 색상=갈색, 모양=장방형
DB:   앞면=ABC, 뒷면=123, 색상=노랑, 모양=장방형

색상: 갈색 ↔ 노랑 → 같은 그룹(노란계열) → 불일치 아님
점수: 35 + 35 + 4(색상 일부) + 8(모양) = 82점 → 성공
```

**케이스 6: 분할선 각인**
```
쿼리: 앞면=1 3 (분할선), 뒷면=AUK, 색상=하양, 모양=타원형
DB:   앞면=1분할선3, 뒷면=AUK, 색상=하양, 모양=타원형

정규화: "1 3" → "13", "1분할선3" → "13" → exact match
점수: 35 + 35 + 8(색상) + 8(모양) = 86점 → 성공
```

---

### ❌ 매칭 실패 케이스

**케이스 1: 점수 미달**
```
쿼리: 앞면=null, 뒷면=null, 색상=하양, 모양=원형
DB:   앞면=ABC, 뒷면=123, 색상=하양, 모양=원형

점수: 0(각인 없음) + 8(색상) + 8(모양) = 16점 < 45 → 실패
```

**케이스 2: 색상+모양 동시 불일치**
```
쿼리: 앞면=MTS, 뒷면=7, 색상=노랑, 모양=타원형
DB:   앞면=MTS, 뒷면=7, 색상=분홍, 모양=원형

색상: 노랑 vs 분홍 → 다른 그룹 + color_conf >= 0.7
모양: 타원형 vs 원형 → shape_match_score = 3.0 > 0 → 완전 불일치 아님
→ 색상 단독 불일치 조건 적용 → 실패
```

**케이스 3: 뒷면 각인 + 색상 동시 불일치**
```
쿼리: 앞면=JS, 뒷면=10, 색상=노랑, 모양=원형
DB:   앞면=JS, 뒷면=UX, 색상=빨강, 모양=원형

뒷면: 10 ≠ UX → 불일치
색상: 노랑 vs 빨강 → 다른 그룹 + color_conf >= 0.7
→ 뒷면 각인 + 색상 동시 불일치 → 실패
```

**케이스 4: 후보 간 점수 차이 작음**
```
1위: ABC/123/하양/원형 → rerank_score = 51
2위: ABC/456/하양/원형 → rerank_score = 47
차이: 4 < 5 AND imprint_conf = 0.5 < 0.6 → 실패
```

**케이스 5: 이미지 특징 불명확**
```
imprint_confidence = 0.3
color_confidence = 0.4
shape_confidence = 0.5
→ 세 값 모두 임계값 미달 → 실패
```

---

## 7. 조건부 2차 VLM (ENABLE_SECOND_PASS=true)

기본값 `False`. 운영 환경에서 `.env`에 `ENABLE_SECOND_PASS=true` 설정 시 활성화.

### 7-1. 재검사 트리거 조건

| 조건 | 재검사 종류 |
|---|---|
| 상위 후보에 십자분할선 있는데 VLM이 못 찾음 | cross_scoreline_recheck |
| 분할선 후보 2개 이상 + score_line_conf < 0.6 | scoreline_recheck |
| 각인 총 길이 ≤ 2 + 후보에 각인 있음 | faint_imprint_recheck |
| imprint_confidence < 0.65 | faint_imprint_recheck |
| 반점/점박이 힌트 있음 | faint_imprint_recheck |
| 후보에 마크 있고 VLM이 JS/5/S 등으로 읽음 | mark_recheck |
| 마크 hypothesis 후보 발견 | candidate_visual_verification |

### 7-2. 2차 VLM 종류

- **faint_imprint**: 희미한 각인 전용 재판독
- **scoreline**: 분할선/십자분할선 전용 재확인
- **mark**: 마크 vs 문자 판별
- **candidate_visual_verification**: 후보 목록 보여주고 이미지와 일치 여부 검증

---

## 8. 3단계: 허가정보 조회 및 LLM 정제

### 8-1. DB 조회

매칭된 `item_seq`로 `drug_embeddings` 테이블에서 조회:
- `efficacy`: 효능효과 원문
- `caution`: 주의사항 원문
- `ingredient`: 유효성분 원문

### 8-2. LLM 정제 (refine_drug_info)

원본 허가정보 텍스트를 GPT로 정제해 사용자 친화적으로 변환:

| DB 필드 | 내용 |
|---|---|
| `active_ingredients` | 유효성분명 및 함량 요약 |
| `efficacy` | 주요 효능과 효과 |
| `usage_method` | 복용법 및 용량 |
| `warning` | 복용 전 경고 사항 |
| `caution` | 일반 주의사항 |
| `interactions` | 병용 주의 약물 |
| `side_effects` | 발생 가능한 부작용 |
| `storage_method` | 보관 방법 |

LLM 정제 실패 시 원본 텍스트 그대로 fallback 저장.

---

## 9. 설정값 (환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ENABLE_SECOND_PASS` | `false` | 2차 VLM 활성화 |
| `SECOND_PASS_THRESHOLD` | `0.55` | 2차 VLM 결과 병합 confidence 임계값 |
| `VLM_MAX_TOKENS` | `700` | GPT Vision 최대 토큰 |

---

## 10. 알려진 한계

| 한계 | 설명 |
|---|---|
| 각인 회전 오인식 | 4↔7, 6↔9 등 회전 혼동 문자는 프롬프트로 완화하나 완전 해결 불가 |
| 마크/로고 오인식 | JS, S, 5 등 마크 오인 가능 문자는 hypothesis 검색으로 보완 |
| 반점 알약 | 반점을 각인으로 오인하는 경우 confidence 보정으로 완화 |
| 희미한 각인 | 2차 VLM(ENABLE_SECOND_PASS=true)으로 보완 가능 |
| 색상 오인식 | 유사 색상 그룹으로 허용 범위 설정, 명확히 다른 그룹은 실패 처리 |
