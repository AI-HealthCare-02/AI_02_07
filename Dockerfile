# ──────────── Build Stage ────────────
FROM python:3.12-slim AS builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 의존성 파일 먼저 복사 (캐시 레이어 활용)
COPY pyproject.toml uv.lock* ./

# 의존성 설치 (가상환경을 시스템에 직접)
RUN uv sync --no-dev --frozen

# ──────────── Runtime Stage ────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# 빌더에서 설치된 패키지 복사
COPY --from=builder /app/.venv /app/.venv

# 애플리케이션 소스 복사
COPY . .

# PATH에 가상환경 추가
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
