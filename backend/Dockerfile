# Dockerfile
# ──────────────────────────────────────────────
# FastAPI API 서버 이미지
# 멀티스테이지 빌드로 최종 이미지 크기 최소화
# ──────────────────────────────────────────────

# ── Stage 1: 의존성 설치 ──
FROM python:3.13-slim AS builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

# 의존성 파일만 먼저 복사 (캐시 활용)
COPY pyproject.toml ./

# app 그룹 의존성 설치 (가상환경을 /build/.venv 에 생성)
RUN uv sync --group app --no-dev

# ── Stage 2: 런타임 이미지 ──
FROM python:3.13-slim AS runtime

WORKDIR /code

# builder에서 가상환경 복사
COPY --from=builder /build/.venv /code/.venv

# shebang 경로 수정 (/build/.venv -> /code/.venv)
RUN find /code/.venv/bin -type f | xargs grep -l '#!/build/.venv/bin/python' | \
    xargs sed -i 's|#!/build/.venv/bin/python|#!/code/.venv/bin/python|g'

# 앱 소스코드 복사
COPY app/ /code/app/
COPY scripts/ /code/scripts/
# migrations 폴더가 없어도 빌드 성공
RUN mkdir -p /code/migrations

# PATH에 가상환경 bin 추가
ENV PATH="/code/.venv/bin:$PATH"
ENV PYTHONPATH="/code"

EXPOSE 8000

# uvicorn으로 서버 실행 (단일 워커 - DB 초기화 중복 방지)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]