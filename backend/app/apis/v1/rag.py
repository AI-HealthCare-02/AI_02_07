# app/apis/v1/rag.py
# ──────────────────────────────────────────────
# 약품 RAG 관리자 API
# - 임베딩 통계 조회
# - 검색 테스트
# ──────────────────────────────────────────────

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.rag_service import ChunkType, get_rag_service

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    chunk_type: ChunkType | None = None
    etc_otc_filter: str | None = None
    min_similarity: float = 0.3


class SearchResult(BaseModel):
    item_seq: str
    item_name: str
    etc_otc_code: str
    chunk_type: str
    chunk_text: str
    similarity: float


@router.get("/stats", summary="RAG 임베딩 통계")
async def get_rag_stats() -> dict:
    """임베딩된 약품 수, 청크 수, 마지막 업데이트 시각을 반환합니다."""
    rag = get_rag_service()
    return await rag.get_stats()


@router.post("/search", summary="약품 벡터 검색 테스트", response_model=list[SearchResult])
async def search_drugs(body: SearchRequest) -> list[SearchResult]:
    """쿼리와 유사한 약품 청크를 검색합니다. (개발/테스트용)"""
    rag = get_rag_service()
    chunks = await rag.search(
        query=body.query,
        top_k=body.top_k,
        chunk_type=body.chunk_type,
        etc_otc_filter=body.etc_otc_filter,
    )
    return [
        SearchResult(
            item_seq=c.item_seq,
            item_name=c.item_name,
            etc_otc_code=c.etc_otc_code,
            chunk_type=c.chunk_type,
            chunk_text=c.chunk_text,
            similarity=c.similarity,
        )
        for c in chunks
        if c.similarity >= body.min_similarity
    ]


@router.get("/search/by-name", summary="약품명 직접 검색", response_model=list[SearchResult])
async def search_by_name(
    name: str = Query(..., description="약품명 (오타 허용)"),
    chunk_type: ChunkType | None = Query(None),
    similarity_threshold: float = Query(0.3, ge=0.0, le=1.0, description="trgm 유사도 임계값"),
) -> list[SearchResult]:
    """pg_trgm 기반 약품명 검색입니다. 오타나 부분 일치도 허용합니다. (OCR 결과 검증용)"""
    rag = get_rag_service()
    chunks = await rag.search_by_name(
        item_name=name,
        chunk_type=chunk_type,
        similarity_threshold=similarity_threshold,
    )
    return [
        SearchResult(
            item_seq=c.item_seq,
            item_name=c.item_name,
            etc_otc_code=c.etc_otc_code,
            chunk_type=c.chunk_type,
            chunk_text=c.chunk_text,
            similarity=c.similarity,
        )
        for c in chunks
    ]
