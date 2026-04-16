# app/services/chat_stats_service.py
# 모델별 채팅 통계 조회 (관리자용)

from datetime import datetime
from typing import Optional

from tortoise import connections

# GPT 모델별 가격 (USD per 1M tokens)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
}
_DEFAULT_PRICING = (0.15, 0.60)

# 컬럼 존재 여부 캐시
_col_cache: dict[str, bool] = {}


async def _has_column(conn, table: str, column: str) -> bool:
    key = f"{table}.{column}"
    if key in _col_cache:
        return _col_cache[key]
    rows = await conn.execute_query_dict(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = $1 AND column_name = $2
        LIMIT 1
        """,
        [table, column],
    )
    result = len(rows) > 0
    _col_cache[key] = result
    return result


def _calc_cost(
    model: str | None, prompt: int | None, completion: int | None
) -> float | None:
    if prompt is None or completion is None:
        return None
    inp_price, out_price = _MODEL_PRICING.get(model or "", _DEFAULT_PRICING)
    return round(
        (prompt / 1_000_000 * inp_price) + (completion / 1_000_000 * out_price), 8
    )


def _build_conditions(
    room_id: Optional[int],
    model_name: Optional[str],
    filter_result: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    has_model_col: bool = True,
) -> tuple[list[str], list]:
    conditions = [
        "a.sender_type_code = 'ASSISTANT'",
        "a.content IS NOT NULL",
        "a.content <> ''",
    ]
    params: list = []
    idx = 1

    if room_id is not None:
        conditions.append(f"a.room_id = ${idx}")
        params.append(room_id)
        idx += 1
    if model_name and has_model_col:
        conditions.append(f"a.model_name = ${idx}")
        params.append(model_name)
        idx += 1
    if filter_result:
        conditions.append(f"a.filter_result = ${idx}")
        params.append(filter_result)
        idx += 1
    if start_date:
        conditions.append(f"a.created_at >= ${idx}::timestamptz")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"a.created_at < (${idx}::date + INTERVAL '1 day')")
        params.append(end_date)
        idx += 1

    return conditions, params


def _row_to_dict(r: dict) -> dict:
    prompt = r.get("prompt_tokens")
    completion = r.get("completion_tokens")
    total = (
        ((prompt or 0) + (completion or 0))
        if (prompt is not None or completion is not None)
        else None
    )
    cost = _calc_cost(r.get("model_name"), prompt, completion)
    created = r.get("created_at")
    return {
        "message_id": r["message_id"],
        "room_id": r["room_id"],
        "model_name": r.get("model_name"),
        "input_text": r.get("input_text"),
        "output_text": r.get("content"),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cost_usd": cost,
        "latency_ms": r.get("latency_ms"),
        "filter_result": r.get("filter_result"),
        "created_at": (
            created.isoformat()
            if isinstance(created, datetime)
            else str(created) if created else None
        ),
    }


def _build_select_query(where: str, model_col: str, extra_params_count: int) -> str:
    limit_idx = extra_params_count + 1
    offset_idx = extra_params_count + 2
    return f"""
        SELECT
            a.message_id,
            a.room_id,
            {model_col}
            u.content AS input_text,
            a.content,
            a.prompt_tokens,
            a.completion_tokens,
            a.latency_ms,
            a.filter_result,
            a.created_at
        FROM chat_messages a
        LEFT JOIN LATERAL (
            SELECT content FROM chat_messages
            WHERE room_id = a.room_id
              AND sender_type_code = 'USER'
              AND message_id < a.message_id
            ORDER BY message_id DESC
            LIMIT 1
        ) u ON TRUE
        {where}
        ORDER BY a.created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """


def _build_all_query(where: str, model_col: str) -> str:
    return f"""
        SELECT
            a.message_id,
            a.room_id,
            {model_col}
            u.content AS input_text,
            a.content,
            a.prompt_tokens,
            a.completion_tokens,
            a.latency_ms,
            a.filter_result,
            a.created_at
        FROM chat_messages a
        LEFT JOIN LATERAL (
            SELECT content FROM chat_messages
            WHERE room_id = a.room_id
              AND sender_type_code = 'USER'
              AND message_id < a.message_id
            ORDER BY message_id DESC
            LIMIT 1
        ) u ON TRUE
        {where}
        ORDER BY a.created_at DESC
    """


async def get_stats(
    page: int,
    size: int,
    room_id: Optional[int] = None,
    model_name: Optional[str] = None,
    filter_result: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    conn = connections.get("default")
    has_model_col = await _has_column(conn, "chat_messages", "model_name")
    model_col = "a.model_name," if has_model_col else "NULL AS model_name,"

    conditions, params = _build_conditions(
        room_id, model_name, filter_result, start_date, end_date, has_model_col
    )
    where = "WHERE " + " AND ".join(conditions)

    count_rows = await conn.execute_query_dict(
        f"SELECT COUNT(*) AS cnt FROM chat_messages a {where}", params
    )
    total = int(count_rows[0]["cnt"])

    offset = (page - 1) * size
    sql = _build_select_query(where, model_col, len(params))
    rows = await conn.execute_query_dict(sql, params + [size, offset])

    return {
        "totalCount": total,
        "page": page,
        "size": size,
        "items": [_row_to_dict(r) for r in rows],
    }


async def get_all_stats(
    room_id: Optional[int] = None,
    model_name: Optional[str] = None,
    filter_result: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    conn = connections.get("default")
    has_model_col = await _has_column(conn, "chat_messages", "model_name")
    model_col = "a.model_name," if has_model_col else "NULL AS model_name,"

    conditions, params = _build_conditions(
        room_id, model_name, filter_result, start_date, end_date, has_model_col
    )
    where = "WHERE " + " AND ".join(conditions)

    sql = _build_all_query(where, model_col)
    rows = await conn.execute_query_dict(sql, params)
    return [_row_to_dict(r) for r in rows]
