# pgvector RAG 구축 작업 정리

> 작업자: 황보수호  
> 브랜치: `feature/pgvector` → `main` 머지 완료

---

## 작업 개요

약품 데이터(drug_json/*.jsonl)를 pgvector에 임베딩하여  
AI 상담, 알약 분석, 의료문서 분석에서 공통으로 사용할 수 있는 **RAG(Retrieval-Augmented Generation)** 인프라를 구축했습니다.

---

## 변경된 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `backend/docker-compose.yml` | `postgres:16-alpine` → `pgvector/pgvector:pg16` |
| `backend/docker-compose.prod.yml` | 동일 이미지 교체 + db 메모리 512m → 768m |
| `backend/scripts/sql/create_tables.sql` | `vector`, `pg_trgm` extension 추가 + `drug_embeddings` 테이블 추가 |
| `backend/pyproject.toml` | `pgvector>=0.3.0`, `asyncpg` 공통 의존성 추가 |
| `backend/app/services/rag_service.py` | 공통 RAG 서비스 신규 생성 |
| `backend/app/apis/v1/rag.py` | RAG 관리자 API 신규 생성 |
| `backend/app/apis/v1/__init__.py` | RAG 라우터 등록 |
| `backend/scripts/embed_drugs.py` | 약품 임베딩 스크립트 신규 생성 |

---

## DB 변경사항

### 추가된 Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- 벡터 검색
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 약품명 유사도 검색 (오타 허용)
```

### 추가된 테이블: `drug_embeddings`
```sql
CREATE TABLE drug_embeddings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_seq     VARCHAR(20)  NOT NULL,       -- 약품 고유코드
    item_name    VARCHAR(500) NOT NULL,       -- 약품명
    etc_otc_code VARCHAR(50),                 -- 전문/일반 구분
    chunk_type   VARCHAR(20)  NOT NULL,       -- 'efficacy' | 'caution' | 'ingredient'
    chunk_text   TEXT         NOT NULL,       -- 임베딩 원문
    embedding    vector(1536),                -- text-embedding-3-small
    metadata     JSONB,                       -- 원본 전체 데이터
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (item_seq, chunk_type)
);
```

### 인덱스
```sql
-- 약품 코드 검색
CREATE INDEX idx_drug_emb_item_seq ON drug_embeddings (item_seq);

-- 약품명 유사도 검색 (pg_trgm)
CREATE INDEX idx_drug_name_trgm ON drug_embeddings USING gin (item_name gin_trgm_ops);

-- 벡터 검색 (임베딩 완료 후 생성)
CREATE INDEX idx_drug_emb_ivfflat
    ON drug_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

## 임베딩 현황 (EC2 DB 기준)

| 항목 | 수치 |
|---|---|
| 총 약품 수 | ~32,000개 |
| 총 청크 수 | ~97,382개 |
| 청크 타입 | efficacy(효능효과), caution(주의사항), ingredient(주성분) |
| 임베딩 모델 | `text-embedding-3-small` (1536차원) |

---

## 공통 RAG 서비스: `DrugRAGService`

위치: `backend/app/services/rag_service.py`

### 주요 메서드

```python
from app.services.rag_service import get_rag_service

rag = get_rag_service()

# 1. 벡터 유사도 검색
chunks = await rag.search(
    query="아스피린 부작용",
    top_k=5,
    chunk_type="caution",        # 'efficacy' | 'caution' | 'ingredient' | None
    etc_otc_filter="전문의약품",  # None이면 전체
)

# 2. LLM 프롬프트용 컨텍스트 문자열 반환
context = await rag.build_context(
    query="두통약 주의사항",
    top_k=5,
    min_similarity=0.3,
)
# 반환 예시:
# "[약품 참고 정보]
# - [아세트아미노펜] 주의사항: ...
# - [이부프로펜] 주의사항: ..."

# 3. 약품명 직접 검색 (OCR 결과, 오타 허용)
chunks = await rag.search_by_name(
    item_name="타이레놀",
    chunk_type="caution",
    similarity_threshold=0.3,
)

# 4. 임베딩 통계
stats = await rag.get_stats()
```

### 반환 타입: `DrugChunk`
```python
@dataclass
class DrugChunk:
    item_seq: str
    item_name: str
    etc_otc_code: str
    chunk_type: str
    chunk_text: str
    similarity: float  # 0.0 ~ 1.0
```

---

## 관리자 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/admin/rag/stats` | 임베딩 통계 조회 |
| POST | `/api/v1/admin/rag/search` | 벡터 검색 테스트 |
| GET | `/api/v1/admin/rag/search/by-name` | 약품명 직접 검색 |

---

## 로컬 개발 시 주의사항

로컬 DB에는 임베딩 데이터가 없어요.  
`build_context()`는 빈 문자열을 반환하고, `search()`는 빈 리스트를 반환합니다.  
**기존 LLM 단독 동작과 동일하게 작동하므로 서비스에 영향 없습니다.**

RAG 기능을 로컬에서 테스트하려면 SSH 터널링으로 EC2 DB를 바라보게 하세요:

```bash
# 터미널 1 - 터널링 유지
ssh -i "~/.ssh/health-guide-key.pem" -L 15432:localhost:5432 ubuntu@13.209.187.137 -N

# .local.env 수정
DB_PORT=15432
DB_PASSWORD=healthguide1234
```

---

## 임베딩 스크립트 재실행 방법

약품 데이터가 추가되거나 재임베딩이 필요할 때:

```bash
# SSH 터널링 열고
ssh -i "health-guide-key.pem" -L 15432:localhost:5432 ubuntu@13.209.187.137 -N

# 전체 실행
$env:DB_PORT = "15432"
$env:DB_PASSWORD = "healthguide1234"
uv run python scripts/embed_drugs.py

# 기존 건너뛰고 이어서
uv run python scripts/embed_drugs.py --skip-existing

# 특정 파일만
uv run python scripts/embed_drugs.py --files drugs_0000.jsonl drugs_0001.jsonl
```
