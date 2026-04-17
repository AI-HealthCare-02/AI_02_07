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

# 가상환경을 /code/.venv 에 직접 생성 (shebang 수정 불필요)
RUN UV_PROJECT_ENVIRONMENT=/code/.venv uv sync --group app --no-dev --frozen --no-cache

# ── Stage 2: 런타임 이미지 ──
FROM python:3.13-slim AS runtime

WORKDIR /code

COPY --from=builder /code/.venv /code/.venv

# SQL 초기화 스크립트만 복사 (CI 스크립트 제외)
COPY app/ /code/app/
COPY scripts/sql/ /code/scripts/sql/

ENV PATH="/code/.venv/bin:$PATH"
ENV PYTHONPATH="/code"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]