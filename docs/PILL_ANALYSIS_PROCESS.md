# 알약 분석 프로세스 상세 문서

## 개요

사용자가 알약 이미지를 업로드하면 **Clova OCR → GPT Vision → pgvector RAG + Rerank → DB 조회** 순서로 약품을 식별하고 허가정보를 반환하는 파이프라인입니다.

---

## 전체 흐름

```
[사용자]
  │ 이미지 업로드 (앞면 필수, 뒷면 선택)
  ▼
[FastAPI: POST /api/v1/pill-analysis/analyze]
  │ 이미지 유효성 검사 (포맷, 5MB 제한)
  │ S3 업로드
  │ UploadedFile DB 저장
  │ Redis 큐에 태스크 등록 (production)
  ▼
[AI Worker: process_pill_analysis]
  │
  ├─ 이미지 전처리
  ├─ Clova OCR (각인 추출)
  ├─ 1단계: GPT Vision (색상/모양 추출 + OCR 교정)
  ├─ 2단계: imprint RAG + Rerank (약품 특정)
  └─ 3단계: DB 직접 조회 (허가정보)
  ▼
[pill_analysis_history 저장]
  ▼
[사용자에게 결과 반환]
```

---

## API 레이어 (`app/apis/v1/pill_analysis.py`)

### 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/pill-analysis/analyze` | 이미지 업로드 + 분석 요청 |
| GET | `/api/v1/pill-analysis` | 분석 이력 목록 조회 (검색/페이징) |
| GET | `/api/v1/pill-analysis/{id}` | 분석 상세 조회 (이미지 URL 포함) |
| DELETE | `/api/v1/pill-analysis/{id}` | 분석 이력 삭제 |

### 분석 요청 처리 흐름

1. **이미지 유효성 검사**
   - 허용 포맷: `JPEG`, `PNG`, `WEBP`, `HEIC`
   - 최대 크기: 5MB
   - `front_image` 필수, `back_image` 선택

2. **S3 업로드**
   - 앞면/뒷면 각각 `pill-images/{user_id}/...` 경로로 업로드
   - `UploadedFile` 테이블에 메타데이터 저장

3. **환경별 분기**
   - `local`: API 서버에서 직접 처리 (개발 편의)
   - `production`: Redis 큐(`ai_task_queue`)에 태스크 등록 → AI Worker가 처리 → 결과 대기 (최대 120초)

4. **식별 불가 판단** (`is_unidentified`)
   - `product_name`에 아래 키워드 포함 시 프론트에서 분석 불가 화면 표시
   - 키워드: `식별 불가`, `미매칭`, `알약 이미지가 아닙니다`, `여러 알약`, `분석 실패`

---

## AI Worker 파이프라인 (`ai_worker/tasks/pill_analysis.py`)

### 이미지 전처리 (`preprocess_image`)

```
원본 이미지 bytes
  │
  ├─ EXIF 회전 보정 (ImageOps.exif_transpose)
  ├─ RGB 변환
  ├─ 최대 1024px 리사이즈 (비율 유지, LANCZOS)
  └─ JPEG quality=90 인코딩
  ▼
(base64 문자열, bytes) 반환
```

---

### Clova OCR (`extract_imprint_ocr`)

각인 텍스트를 이미지에서 직접 추출합니다.

```
이미지 bytes
  │
  ├─ 원본 OCR 요청
  └─ 180도 회전 OCR 요청  ← 거꾸로 찍힌 이미지 대응
  │  (두 요청 asyncio.gather로 병렬 처리)
  ▼
더 긴 텍스트 결과 선택 (더 많이 인식된 방향)
  ▼
대문자 변환 후 반환
```

**앞뒤 swap 로직**
- 앞면 OCR이 숫자만(`500`)이고 뒷면이 영문자(`TYLENOL`)인 경우
- 사용자가 앞뒤를 반대로 업로드한 것으로 판단하여 자동 교체

---

### 1단계: GPT Vision (`extract_pill_features`)

OCR 결과를 힌트로 제공하고, GPT Vision은 **색상/모양 판단 + OCR 오인식 교정**을 담당합니다.

**입력**
- 이미지 (detail:low, 토큰 절약)
- OCR 각인 텍스트 (힌트)

**프롬프트 구성**

```
[업로드 패턴 고려]
- 일반: 첫 번째=앞면, 두 번째=뒷면
- 앞뒤 반대: 앞면이 숫자만이면 앞뒤 바뀐 것
- 한 이미지에 앞뒤 모두: 알약 2개가 함께 찍힌 경우 직접 구분
- 여러 알약: 서로 다른 알약 여러 개 → multiple_pills=true

[OCR 오인식 교정]
- H ↔ N (TYLEHOL → TYLENOL)
- 0 ↔ O, 1 ↔ I ↔ L, 8 ↔ B, 5 ↔ S, 6 ↔ G

[각인 유추]
- 존재하지 않는 각인이면 발음/철자 유사한 실제 약품 각인으로 유추
```

**출력 JSON**
```json
{
  "is_pill": true,
  "multiple_pills": false,
  "print_front": "TYLENOL",
  "print_back": "500",
  "color": "하양",
  "shape": "장방형"
}
```

**모양 분류 기준**

| 모양 | 설명 |
|------|------|
| 원형 | 완전한 원 |
| 타원형 | 위아래가 둥근 타원, 가로가 세로보다 조금 더 넓음 |
| 장방형 | 직사각형에 가까운 모양, 가로가 세로보다 눈에 띄게 더 길고 끝이 둥근 직사각형 (타이레놀정500 대표 예시) |
| 반원형 | 반으로 자른 원 |
| 삼각형 / 사각형 / 마름모형 / 오각형 / 육각형 / 팔각형 | 해당 다각형 |

> 타원형과 장방형은 혼동하기 쉬우므로 가로/세로 비율을 주의 깊게 확인

**조기 종료 조건**
- `is_pill=false` → `"알약 이미지가 아닙니다"` 저장 후 반환
- `multiple_pills=true` → `"여러 알약 감지 - 분석 실패"` 저장 후 반환

---

### 2단계: imprint RAG + Rerank (`find_drug_by_imprint`)

각인/색상/모양으로 DB에서 약품을 찾습니다.

#### 2-1. 검색 쿼리 구성

```python
query_str = "TYLENOL 500 하양 장방형"
```

#### 2-2. 이미지 분석 결과 정규화 (`normalize_vision_result`)

```
GPT Vision 결과
  │
  ├─ 각인 정규화: 분할선 제거, 대문자화, 공백/특수문자 제거
  │   예) "C 분할선6" → "C6"
  ├─ 색상 정규화: 흰색→하양, 황색→노랑, 핑크→분홍 등
  ├─ 모양 정규화: 긴타원형→장방형, 동그라미→원형 등
  └─ OCR 혼동 문자 variant 생성 (편집거리 1)
      예) "TYLEHOL" → "TYLENOL" (H↔N)
  ▼
{
  "front_norm": "TYLENOL",
  "back_norm": "500",
  "color_norm": "하양",
  "shape_norm": "장방형",
  "query_variants": ["TYLENOL 500 하양 장방형", "500 TYLENOL 하양 장방형", ...]
}
```

#### 2-3. 후보 검색 (3가지 병행)

```
① metadata exact match
   - metadata->'search_keys'->>'front_norm' = 'TYLENOL'
   - metadata->'search_keys'->>'back_norm' = '500'
   - LIMIT 10

② metadata swapped match (앞뒤 반전 대응)
   - front_norm = '500', back_norm = 'TYLENOL'
   - LIMIT 5

③ pgvector similarity search (fallback)
   - text-embedding-3-small으로 query_str 임베딩
   - cosine similarity 기준 LIMIT 20
```

모든 후보를 `item_seq` 기준으로 중복 제거 후 통합

#### 2-4. Rerank 점수 계산 (`_rerank_score`)

각 후보에 대해 0~100점 점수를 계산합니다.

| 항목 | 배점 | 조건 |
|------|------|------|
| 앞면 각인 일치 | 35점 | `front_norm` 완전 일치 |
| 뒷면 각인 일치 | 35점 | `back_norm` 완전 일치 |
| 앞뒤 swap 일치 | 최대 70점 | 앞뒤 반전 후 일치 시 동일 점수 |
| 앞면 분할선 일치 | 4점 | `has_score_line` 일치 |
| 뒷면 분할선 일치 | 4점 | `has_score_line` 일치 |
| 색상 일치 | 8점 | `color_normalized` 일치 |
| 모양 일치 | 8점 | `shape_normalized` 일치 |
| vector 보조 | 최대 10점 | `vector_similarity × 10` |

**최종 점수** = `rerank_base + vector_similarity × 10`

#### 2-5. 매칭 판정

```
rerank_base >= 10점  OR  vector_similarity >= 0.55
  → 매칭 성공 → 3단계 진행

둘 다 미달
  → 매칭 실패 → "각인: TYLENOL, 500 (DB 미매칭)" 저장 후 반환
```

---

### 3단계: 허가정보 DB 직접 조회 (`fetch_drug_info_from_db`)

매칭된 `item_seq`로 `drug_embeddings` 테이블에서 허가정보를 조회합니다. GPT 재호출 없음.

```sql
SELECT chunk_type, chunk_text
FROM drug_embeddings
WHERE item_seq = $1
  AND chunk_type IN ('efficacy', 'caution', 'ingredient')
```

| chunk_type | 내용 |
|------------|------|
| `efficacy` | 효능·효과 |
| `caution` | 주의사항 |
| `ingredient` | 주성분 |

chunk_text 형식: `[약품명] 효능효과: 실제내용` → `": "` 기준으로 분리하여 실제 내용만 추출

---

### 결과 저장 (`save_analysis_result`)

`pill_analysis_history` 테이블에 저장:

| 필드 | 값 |
|------|----|
| `product_name` | 매칭된 약품명 |
| `active_ingredients` | 주성분 |
| `efficacy` | 효능·효과 |
| `caution` | 주의사항 |
| `gpt_model_version` | 사용된 GPT 모델 |

---

## imprint 파서 (`ai_worker/tasks/imprint_parser.py`)

### parse_imprint_chunk

DB에 저장된 `chunk_text`를 파싱하여 구조화된 `metadata`를 생성합니다.

**입력 예시**
```
[타이레놀정500밀리그람] 각인: 앞면 TYLENOL, 뒷면 500 | 색상: 하양 | 모양: 장방형 | 크기: 17.6x7.1mm
```

**출력 metadata 구조**
```json
{
  "imprint_schema_version": 1,
  "source": {
    "raw_text": "...",
    "raw_imprint": "앞면 TYLENOL, 뒷면 500",
    "raw_color": "하양",
    "raw_shape": "장방형",
    "raw_size": "17.6x7.1mm"
  },
  "imprint": {
    "front": {
      "raw": "TYLENOL",
      "normalized": "TYLENOL",
      "has_score_line": false,
      "tokens": ["TYLENOL"]
    },
    "back": {
      "raw": "500",
      "normalized": "500",
      "has_score_line": false,
      "tokens": ["500"]
    }
  },
  "appearance": {
    "color_raw": "하양",
    "color_normalized": "하양",
    "shape_raw": "장방형",
    "shape_normalized": "장방형"
  },
  "size": {
    "raw": "17.6x7.1mm",
    "long_mm": 17.6,
    "short_mm": 7.1,
    "unit": "mm"
  },
  "search_keys": {
    "front_norm": "TYLENOL",
    "back_norm": "500",
    "all_imprints_norm": "TYLENOL 500",
    "all_imprints_compact": "TYLENOL500",
    "imprint_variants": ["TYLENOL 500", "500 TYLENOL"]
  }
}
```

### 분할선 처리

```
"C분할선6"
  → has_score_line: true
  → normalized: "C6"  (분할선 제거 후 공백/특수문자 제거)
  → tokens: ["C", "6"]
```

### 크기 파싱

- `18x8mm`, `18X8mm`, `18×8mm` 모두 처리
- `long_mm`에 큰 값, `short_mm`에 작은 값
- 오타 허용: `9..5mm` → `9.5mm`, `14.2.mm` → `14.2mm`

---

## Backfill 스크립트 (`scripts/backfill_imprint_metadata.py`)

기존 DB의 imprint 데이터에 구조화된 metadata를 추가합니다.

### 실행 방법

```bash
# dry-run (실제 DB 변경 없음)
DB_HOST=localhost DB_PORT=5432 uv run python scripts/backfill_imprint_metadata.py --dry-run

# 실제 실행
DB_HOST=localhost DB_PORT=5432 uv run python scripts/backfill_imprint_metadata.py

# batch size 조정
DB_HOST=localhost DB_PORT=5432 uv run python scripts/backfill_imprint_metadata.py --batch-size 50
```

### 동작 방식

1. `chunk_type='imprint'` 전체 행 조회
2. `imprint_schema_version >= 1`인 행은 건너뜀 (idempotent)
3. `parse_imprint_chunk`로 metadata 생성
4. `metadata || new_metadata::jsonb` 방식으로 기존 metadata에 merge (기존 데이터 보존)
5. batch 단위로 트랜잭션 commit

---

## DB 인덱스

metadata 기반 검색 성능을 위해 아래 인덱스가 권장됩니다.

```sql
-- chunk_type 인덱스
CREATE INDEX IF NOT EXISTS idx_drug_emb_chunk_type
ON drug_embeddings (chunk_type);

-- front_norm 인덱스
CREATE INDEX IF NOT EXISTS idx_drug_emb_metadata_front_norm
ON drug_embeddings ((metadata->'search_keys'->>'front_norm'))
WHERE chunk_type = 'imprint';

-- back_norm 인덱스
CREATE INDEX IF NOT EXISTS idx_drug_emb_metadata_back_norm
ON drug_embeddings ((metadata->'search_keys'->>'back_norm'))
WHERE chunk_type = 'imprint';

-- 색상/모양 복합 인덱스
CREATE INDEX IF NOT EXISTS idx_drug_emb_metadata_color_shape
ON drug_embeddings (
  (metadata->'appearance'->>'color_normalized'),
  (metadata->'appearance'->>'shape_normalized')
)
WHERE chunk_type = 'imprint';
```

---

## 로그 예시

### 정상 매칭

```
Clova OCR 결과: TYLENOL (normal=TYLENOL, rotated=LONELYT)
OCR 결과: front=TYLENOL, back=500
1단계 완료: {'is_pill': True, 'multiple_pills': False, 'print_front': 'TYLENOL', 'print_back': '500', 'color': '하양', 'shape': '장방형'}
2단계 imprint 검색 쿼리: TYLENOL 500 하양 장방형
imprint 상위 5개 후보 (rerank 내림차순): 타이레놀정500밀리그람(rerank=78, vec=0.821), ...
imprint 매칭 성공: 'TYLENOL 500 하양 장방형' → '타이레놀정500밀리그람' (rerank=78.0, vec=0.821)
  DB chunk: [타이레놀정500밀리그람] 각인: 앞면 TYLENOL, 뒷면 500 | 색상: 하양 | 모양: 장방형
3단계 완료: item_seq=199500630, 조회 필드=['efficacy', 'caution', 'ingredient']
분석 완료: analysis_id=42, product_name=타이레놀정500밀리그람
```

### 매칭 실패

```
imprint 상위 5개 후보 (rerank 내림차순): 페니목스정500mg(rerank=8, vec=0.496), ...
imprint 매칭 실패 - rerank=8.0, vec=0.496
  쿼리: TYLEHOL 500 하양 타원형
  최유사 DB: [페니목스정500mg] 각인: 앞면 HTP, 뒷면 500 | 색상: 하양 | 모양: 타원형
2단계 매칭 실패 → 각인 정보만 저장
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `app/apis/v1/pill_analysis.py` | FastAPI 엔드포인트, S3 업로드, 큐 등록 |
| `ai_worker/tasks/pill_analysis.py` | 분석 파이프라인 메인 로직 |
| `ai_worker/tasks/imprint_parser.py` | imprint chunk_text 파서, 정규화 유틸 |
| `scripts/backfill_imprint_metadata.py` | 기존 DB metadata backfill |
| `app/models/pill_analysis.py` | Tortoise ORM 모델 (UploadedFile, PillAnalysisHistory) |
