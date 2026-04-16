# app/core/openai_utils.py
# ──────────────────────────────────────────────
# OpenAI 모델별 파라미터 분기 헬퍼
# Langfuse tracing은 langfuse.openai drop-in이 자동 처리
# ──────────────────────────────────────────────

try:
    from langfuse.openai import AsyncOpenAI  # tracing 자동 적용
except ImportError:
    from openai import AsyncOpenAI  # type: ignore[assignment]

__all__ = ["AsyncOpenAI", "build_create_kwargs"]

_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "gpt-5")
_NO_TEMPERATURE_PREFIXES    = ("o1", "o3", "gpt-5")


def build_create_kwargs(
    model: str,
    max_tokens: int,
    temperature: float | None = None,
    stream: bool = False,
    stream_options: dict | None = None,
    name: str | None = None,
) -> dict:
    """client.chat.completions.create()에 전달할 kwargs 구성.
    name을 넘기면 Langfuse UI에서 해당 이름으로 generation이 표시됩니다.
    """
    m = model.lower().strip()
    kwargs: dict = {"model": model}

    if any(m.startswith(p) for p in _COMPLETION_TOKENS_PREFIXES):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens

    supports_temp = not any(m.startswith(p) for p in _NO_TEMPERATURE_PREFIXES)
    if temperature is not None and supports_temp:
        kwargs["temperature"] = temperature

    if stream:
        kwargs["stream"] = True
        if stream_options:
            kwargs["stream_options"] = stream_options

    if name:
        kwargs["name"] = name  # langfuse.openai가 generation 이름으로 사용

    return kwargs
