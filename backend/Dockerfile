# Dockerfile
# ──────────────────────────────────────────────
# FastAPI API 서버 이미지
# 멀티스테이지 빌드로 최종 이미지 크기 최소화
# ──────────────────────────────────────────────

# ── Stage 1: 의존성 설치 ──
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/code/.venv uv sync --group app --no-dev --frozen --no-cache

# ── Stage 2: 런타임 이미지 ──
FROM python:3.13-slim AS runtime

# 비root 유저 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /code

COPY --from=builder /code/.venv /code/.venv
COPY app/ /code/app/
COPY ai_worker/ /code/ai_worker/
COPY scripts/sql/ /code/scripts/sql/

RUN chown -R appuser:appuser /code

ENV PATH="/code/.venv/bin:$PATH"
ENV PYTHONPATH="/code"

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]