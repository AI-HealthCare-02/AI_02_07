# app/services/rag_service.py
# ──────────────────────────────────────────────
# 약품 RAG (Retrieval-Augmented Generation) 공통 서비스
#
# 사용 예시:
#   from app.services.rag_service import DrugRAGService
#
#   rag = DrugRAGService()
#   context = await rag.build_context("아스피린 복용 시 주의사항")
# ──────────────────────────────────────────────

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Literal

from openai import AsyncOpenAI
from tortoise import Tortoise

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

ChunkType = Literal["efficacy", "caution", "ingredient"]

CACHE_PREFIX = "rag:drug"
CACHE_TTL = 60 * 60  # 1시간


@dataclass
class DrugChunk:
    item_seq: str
    item_name: str
    etc_otc_code: str
    chunk_type: ChunkType
    chunk_text: str
    similarity: float


class DrugRAGService:
    """
    약품 벡터 검색 서비스.

    - pgvector cosine similarity 검색
    - Redis 캐싱 (동일 쿼리 재사용)
    - LLM 프롬프트용 컨텍스트 빌더
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = AsyncOpenAI(api_key=self._settings.OPENAI_API_KEY)

    # ── 임베딩 ────────────────────────────────────────────────

    async def _embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._settings.OPENAI_EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    # ── 캐시 키 ───────────────────────────────────────────────

    @staticmethod
    def _cache_key(query: str, top_k: int, chunk_type: str | None, etc_otc_filter: str | None) -> str:
        raw = f"{query}|{top_k}|{chunk_type}|{etc_otc_filter}"
        digest = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"{CACHE_PREFIX}:{digest}"

    # ── 벡터 검색 ─────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 5,
        chunk_type: ChunkType | None = None,
        etc_otc_filter: str | None = None,
    ) -> list[DrugChunk]:
        """
        쿼리와 유사한 약품 청크를 검색합니다.

        Parameters
        ----------
        query : str
            검색 쿼리 (증상, 약품명, 효능 등)
        top_k : int
            반환할 최대 결과 수
        chunk_type : 'efficacy' | 'caution' | 'ingredient' | None
            특정 청크 타입만 검색 (None이면 전체)
        etc_otc_filter : str | None
            '전문의약품' 또는 '일반의약품' 필터 (None이면 전체)
        """
        # 캐시 확인
        cache_key = self._cache_key(query, top_k, chunk_type, etc_otc_filter)
        try:
            redis = get_redis()
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [DrugChunk(**item) for item in data]
        except Exception:
            pass

        # 임베딩 생성
        embedding = await self._embed(query)
        vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

        # SQL 조건 구성
        conditions = ["embedding IS NOT NULL"]
        params: list = [vector_str, top_k]

        if chunk_type:
            conditions.append(f"chunk_type = ${len(params) + 1}")
            params.append(chunk_type)

        if etc_otc_filter:
            conditions.append(f"etc_otc_code = ${len(params) + 1}")
            params.append(etc_otc_filter)

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT
                item_seq,
                item_name,
                etc_otc_code,
                chunk_type,
                chunk_text,
                1 - (embedding <=> $1::vector) AS similarity
            FROM drug_embeddings
            WHERE {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(sql, params)

        results = [
            DrugChunk(
                item_seq=row["item_seq"],
                item_name=row["item_name"],
                etc_otc_code=row["etc_otc_code"],
                chunk_type=row["chunk_type"],
                chunk_text=row["chunk_text"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

        # 캐시 저장
        try:
            redis = get_redis()
            await redis.set(
                cache_key,
                json.dumps([r.__dict__ for r in results], ensure_ascii=False),
                ex=CACHE_TTL,
            )
        except Exception:
            pass

        return results

    # ── 컨텍스트 빌더 ─────────────────────────────────────────

    async def build_context(
        self,
        query: str,
        top_k: int = 5,
        chunk_type: ChunkType | None = None,
        etc_otc_filter: str | None = None,
        min_similarity: float = 0.3,
    ) -> str:
        """
        LLM 프롬프트에 삽입할 약품 참고 컨텍스트 문자열을 반환합니다.

        Parameters
        ----------
        min_similarity : float
            이 값 미만의 유사도 결과는 제외 (기본 0.3)

        Returns
        -------
        str
            컨텍스트가 없으면 빈 문자열 반환
        """
        chunks = await self.search(
            query=query,
            top_k=top_k,
            chunk_type=chunk_type,
            etc_otc_filter=etc_otc_filter,
        )

        relevant = [c for c in chunks if c.similarity >= min_similarity]
        if not relevant:
            return ""

        lines = ["[약품 참고 정보]"]
        for chunk in relevant:
            lines.append(f"- {chunk.chunk_text}")

        return "\n".join(lines)

    # ── 약품명으로 직접 조회 ──────────────────────────────────

    async def search_by_name(
        self,
        item_name: str,
        chunk_type: ChunkType | None = None,
        similarity_threshold: float = 0.3,
    ) -> list[DrugChunk]:
        """
        약품명으로 검색합니다.

        1단계: pg_trgm 유사도 기반으로 오타도 허용합니다.
        2단계: 결과 없으면 ILIKE 포함 검색으로 fallback
               (예: "넥실렌정" → DB의 "넥실렌정500mg" 매칭)

        Parameters
        ----------
        similarity_threshold : float
            trgm 유사도 임계값 (0~1, 기본 0.3 — 낮을수록 더 많이 허용)
        """
        results = await self._search_by_name_trgm(item_name, chunk_type, similarity_threshold)

        # ✅ 추가: trgm 결과 없으면 ILIKE 포함 검색으로 fallback
        if not results:
            logger.info(f"trgm 검색 결과 없음 [{item_name}] → ILIKE 포함 검색 시도")
            results = await self._search_by_name_ilike(item_name, chunk_type)

        return results

    async def _search_by_name_trgm(
        self,
        item_name: str,
        chunk_type: ChunkType | None = None,
        similarity_threshold: float = 0.3,
    ) -> list[DrugChunk]:
        """pg_trgm similarity 기반 약품명 검색."""
        conditions = ["similarity(item_name, $1) > $2"]
        params: list = [item_name, similarity_threshold]

        if chunk_type:
            conditions.append(f"chunk_type = ${len(params) + 1}")
            params.append(chunk_type)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT
                item_seq, item_name, etc_otc_code, chunk_type, chunk_text,
                similarity(item_name, $1) AS similarity
            FROM drug_embeddings
            WHERE {where_clause}
            ORDER BY similarity(item_name, $1) DESC
            LIMIT 10
        """

        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(sql, params)

        return [
            DrugChunk(
                item_seq=row["item_seq"],
                item_name=row["item_name"],
                etc_otc_code=row["etc_otc_code"],
                chunk_type=row["chunk_type"],
                chunk_text=row["chunk_text"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    async def _search_by_name_ilike(
        self,
        item_name: str,
        chunk_type: ChunkType | None = None,
    ) -> list[DrugChunk]:
        """
        ✅ 추가: ILIKE 포함 검색.
        DB에 "넥실렌정500mg" 형태로 저장돼 있어도 "넥실렌정"으로 매칭 가능.
        """
        conditions = ["item_name ILIKE $1"]
        params: list = [f"%{item_name}%"]

        if chunk_type:
            conditions.append(f"chunk_type = ${len(params) + 1}")
            params.append(chunk_type)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT
                item_seq, item_name, etc_otc_code, chunk_type, chunk_text,
                1.0 AS similarity
            FROM drug_embeddings
            WHERE {where_clause}
            ORDER BY item_name
            LIMIT 10
        """

        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(sql, params)

        if rows:
            logger.info(f"ILIKE 검색 성공 [{item_name}] → {len(rows)}개 결과")

        return [
            DrugChunk(
                item_seq=row["item_seq"],
                item_name=row["item_name"],
                etc_otc_code=row["etc_otc_code"],
                chunk_type=row["chunk_type"],
                chunk_text=row["chunk_text"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    # ── 통계 ─────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """임베딩 현황 통계를 반환합니다."""
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            """
            SELECT
                COUNT(DISTINCT item_seq) AS total_drugs,
                COUNT(*) AS total_chunks,
                COUNT(*) FILTER (WHERE chunk_type = 'efficacy')   AS efficacy_count,
                COUNT(*) FILTER (WHERE chunk_type = 'caution')    AS caution_count,
                COUNT(*) FILTER (WHERE chunk_type = 'ingredient') AS ingredient_count,
                MAX(created_at) AS last_updated
            FROM drug_embeddings
            """
        )
        return rows[0] if rows else {}


# ── 싱글턴 인스턴스 ───────────────────────────────────────────
_rag_service: DrugRAGService | None = None


def get_rag_service() -> DrugRAGService:
    """
    RAG 서비스 싱글턴을 반환합니다.
    FastAPI Depends 또는 직접 호출로 사용하세요.

    사용 예시 (FastAPI):
        from app.services.rag_service import get_rag_service
        rag = Depends(get_rag_service)

    사용 예시 (직접):
        rag = get_rag_service()
        context = await rag.build_context("두통 약")
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = DrugRAGService()
    return _rag_service
