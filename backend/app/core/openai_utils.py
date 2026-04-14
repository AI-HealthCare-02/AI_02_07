# app/core/openai_utils.py
# ──────────────────────────────────────────────
# OpenAI 모델별 파라미터 분기 헬퍼
#
# max_completion_tokens 사용: o1, o3, gpt-5 계열
# temperature 미지원:        o1, o3 계열
# 그 외 모두 max_tokens + temperature 사용
# ──────────────────────────────────────────────

_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "gpt-5")
_NO_TEMPERATURE_PREFIXES    = ("o1", "o3", "gpt-5")


def build_create_kwargs(
    model: str,
    max_tokens: int,
    temperature: float | None = None,
    stream: bool = False,
    stream_options: dict | None = None,
) -> dict:
    """client.chat.completions.create()에 전달할 kwargs 구성."""
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

    return kwargs
