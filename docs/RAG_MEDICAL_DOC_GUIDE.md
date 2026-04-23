# 의료문서 분석 RAG 연결 가이드

> 담당: 이승원  
> 파일: `backend/ai_worker/tasks/medical_doc.py`

---

## 개요

현재 의료문서 분석 파이프라인:
```
이미지 업로드 → OCR → GPT 구조화 분석 → 결과 반환
```

RAG 연결 후:
```
이미지 업로드 → OCR → 약품명 추출 → RAG 검색 → GPT 구조화 분석(+약품 DB 참조) → 결과 반환
```

OCR로 추출한 약품명을 RAG로 검색해서 **공식 약품 DB의 효능/주의사항**을 프롬프트에 추가하면 분석 정확도가 높아집니다.

---

## 연결 방법

### Step 1 — RAG 서비스 import 추가

`medical_doc.py` 상단에 추가:

```python
# 기존 import 아래에 추가
from app.services.rag_service import get_rag_service
```

> ⚠️ `ai_worker`는 `app` 패키지와 분리되어 있어요.  
> `ai_worker`에서 `app.services`를 import하려면 `PYTHONPATH`에 `backend`가 포함되어야 합니다.  
> 현재 Docker 환경에서는 `/code`가 루트이므로 정상 동작합니다.

---

### Step 2 — 약품명 추출 함수 추가

`medical_doc.py`에 아래 함수 추가:

```python
async def enrich_with_rag(medication_names: list[str]) -> str:
    """
    OCR로 추출한 약품명 목록을 RAG로 검색해서
    공식 약품 DB의 주의사항을 컨텍스트로 반환합니다.

    Parameters
    ----------
    medication_names : list[str]
        GPT가 추출한 약품명 목록 (예: ["타이레놀", "아목시실린"])

    Returns
    -------
    str
        LLM 프롬프트에 삽입할 약품 참고 정보 문자열
        데이터 없으면 빈 문자열 반환
    """
    if not medication_names:
        return ""

    rag = get_rag_service()
    context_lines = []

    for name in medication_names:
        # 약품명으로 직접 검색 (오타 허용, pg_trgm 사용)
        chunks = await rag.search_by_name(
            item_name=name,
            chunk_type="caution",       # 주의사항만 가져옴
            similarity_threshold=0.3,
        )
        for chunk in chunks[:2]:        # 약품당 최대 2개
            context_lines.append(f"- {chunk.chunk_text}")

    if not context_lines:
        return ""

    return "[약품 공식 DB 참고 정보]\n" + "\n".join(context_lines)
```

---

### Step 3 — `analyze_with_gpt` 함수에 RAG 컨텍스트 주입

기존 `analyze_with_gpt` 함수를 아래처럼 수정:

```python
async def analyze_with_gpt(
    client: AsyncOpenAI,
    extracted_text: str,
    doc_type: str,
) -> dict:
    if doc_type == "자동인식":
        doc_type = await detect_document_type(client, extracted_text)
        logger.info(f"자동 감지된 문서 종류: {doc_type}")
    else:
        logger.info(f"선택된 문서 종류: {doc_type}")

    # ── RAG: OCR 텍스트에서 약품명 추출 후 DB 검색 ──
    rag_context = ""
    try:
        rag = get_rag_service()
        rag_context = await rag.build_context(
            query=extracted_text[:500],   # OCR 텍스트 앞부분으로 검색
            top_k=5,
            chunk_type="caution",
            min_similarity=0.4,
        )
        if rag_context:
            logger.info("RAG 컨텍스트 추가됨")
    except Exception as e:
        logger.warning(f"RAG 검색 실패 (무시하고 계속): {e}")
        rag_context = ""

    # ── 프롬프트에 RAG 컨텍스트 추가 ──
    prompt = get_prompt_by_document_type(doc_type, extracted_text)
    if rag_context:
        prompt = f"{rag_context}\n\n위 약품 정보를 참고하여 아래 문서를 분석해줘.\n\n{prompt}"

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=1500,
        name="analyze_doc",
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.choices[0].message.content.strip()
    cleaned = result
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_summary": cleaned, "overall_confidence": 0.5}
```

---

## 변경 전/후 비교

### 변경 전 프롬프트
```
아래는 처방전에서 OCR로 추출한 텍스트야.
이 텍스트를 분석해서 JSON 형식으로 구조화해줘.
...
--- 추출된 텍스트 ---
타이레놀 500mg 1일 3회 식후...
```

### 변경 후 프롬프트
```
[약품 공식 DB 참고 정보]
- [타이레놀(아세트아미노펜)] 주의사항: 매일 세잔 이상 정기적으로 술을 마시는 사람이 이 약을 복용하면 간손상이 유발될 수 있다...
- [아목시실린] 주의사항: 페니실린계 항생물질에 과민반응 병력이 있는 환자...

위 약품 정보를 참고하여 아래 문서를 분석해줘.

아래는 처방전에서 OCR로 추출한 텍스트야.
...
```

---

## 주의사항

### RAG 실패 시 기존 동작 유지
```python
try:
    rag_context = await rag.build_context(...)
except Exception as e:
    logger.warning(f"RAG 검색 실패 (무시하고 계속): {e}")
    rag_context = ""  # 빈 문자열 → 기존 프롬프트 그대로 사용
```
RAG가 실패해도 기존 분석은 정상 동작합니다.

### 로컬 환경
로컬 DB에 임베딩 데이터가 없으면 `rag_context = ""`이 되어 기존과 동일하게 동작합니다.

### 토큰 사용량
RAG 컨텍스트가 추가되면 프롬프트 토큰이 약 **200~500 토큰** 증가합니다.  
`max_tokens=1500`은 유지해도 됩니다 (응답 토큰 기준).

---

## 알약 분석(pill_analysis.py)에서 사용하는 방법

OCR로 추출한 약품명을 `search_by_name()`으로 검색:

```python
from app.services.rag_service import get_rag_service

rag = get_rag_service()

# OCR로 추출한 약품명으로 주의사항 검색
chunks = await rag.search_by_name(
    item_name="타이레놀",
    chunk_type="caution",
)

# 효능효과 검색
chunks = await rag.search_by_name(
    item_name="타이레놀",
    chunk_type="efficacy",
)
```
