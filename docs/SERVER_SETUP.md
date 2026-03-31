# 🖥️ HealthGuide 서버 셋업 가이드

> **uv** 패키지 매니저를 사용한 로컬 개발 환경 구성  
> AI Healthcare Project Template 구조 기반

---

## 사전 준비

| 도구 | 버전 | 비고 |
|------|------|------|
| Python | 3.13 이상 | |
| uv | 최신 | Rust 기반 고속 패키지 매니저 |
| Docker | 24+ | 전체 서비스 실행용 |
| Docker Compose | v2 | `docker compose` (V2) |
| NVIDIA Driver | 535+ | GPU 사용 시 |
| NVIDIA Container Toolkit | 최신 | Docker GPU 지원 |
| Git | 최신 | |

---

## A. Windows 환경

### 1단계 – Python 설치

```powershell
# winget으로 설치 (Windows 10/11)
winget install Python.Python.3.13

# 설치 확인
python --version
```

> ⚠️ 설치 시 **"Add Python to PATH"** 체크 필수

### 2단계 – uv 설치

```powershell
# 공식 설치 스크립트
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 설치 확인
uv --version
```

### 3단계 – 프로젝트 셋업

```powershell
# 저장소 클론
git clone https://github.com/your-org/healthguide.git
cd healthguide

# 환경변수 파일 생성
copy envs\example.local.env envs\.local.env
# VS Code로 envs\.local.env 파일 편집

# 의존성 설치 (가상환경 자동 생성)
uv sync

# 특정 그룹만 설치
uv sync --group app   # API 서버용
uv sync --group ai    # AI 워커용

# FastAPI 서버 실행
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# AI Worker 실행 (별도 터미널)
uv run python -m ai_worker.main
```

### 4단계 – GPU 설정 (Windows)

```powershell
# NVIDIA 드라이버 확인
nvidia-smi

# CUDA Toolkit 설치 (12.x)
# https://developer.nvidia.com/cuda-downloads 에서 다운로드

# PyTorch GPU 버전 설치 (uv 사용)
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# GPU 인식 확인
uv run python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}')"
```

### 5단계 – Docker 서비스 실행 (Windows)

```powershell
# Docker Desktop 실행 확인
# Settings > Resources > WSL Integration 활성화 권장

# 인프라 서비스만 실행 (DB + Redis)
docker compose up -d postgres redis

# 전체 서비스 실행 (GPU 없이)
docker compose up -d --build

# GPU 포함 전체 서비스
docker compose --profile gpu up -d --build
```

---

## B. macOS 환경

### 1단계 – Python 설치

```bash
# Homebrew로 설치
brew install python@3.13

# 설치 확인
python3 --version
```

### 2단계 – uv 설치

```bash
# 공식 설치 스크립트
curl -LsSf https://astral.sh/uv/install.sh | sh

# 셸 재시작 또는 PATH 반영
source ~/.zshrc   # zsh 사용 시
source ~/.bashrc  # bash 사용 시

# 설치 확인
uv --version
```

### 3단계 – 프로젝트 셋업

```bash
# 저장소 클론
git clone https://github.com/your-org/healthguide.git
cd AI-02-07

# 환경변수 파일 생성
cp envs/example.local.env envs/.local.env
# nano, vim 또는 VS Code로 편집

# 의존성 설치
uv sync

# 특정 그룹만 설치
uv sync --group app   # API 서버용
uv sync --group ai    # AI 워커용

# FastAPI 서버 실행
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# AI Worker 실행 (별도 터미널)
uv run python -m ai_worker.main
```

### 4단계 – GPU 설정 (macOS)

```bash
# ⚠️ macOS는 NVIDIA GPU를 지원하지 않습니다.
# Apple Silicon (M1/M2/M3/M4)의 경우 MPS(Metal Performance Shaders) 사용 가능

# PyTorch MPS 지원 확인
uv run python -c "import torch; print(f'MPS: {torch.backends.mps.is_available()}')"

# vLLM은 현재 Linux NVIDIA GPU에서만 완전 지원됩니다
# macOS에서는 Docker 컨테이너 또는 원격 GPU 서버 방식을 권장합니다
```

> 💡 **Apple Silicon 팀원**: vLLM 관련 기능(의료 문서 분석, 알약 분석)은 Docker 컨테이너 내에서 실행하거나, GPU가 탑재된 리눅스 서버에 원격 접속하여 테스트하세요.

### 5단계 – Docker 서비스 실행 (macOS)

```bash
# Docker Desktop 실행 확인
docker --version

# 인프라 서비스만 실행
docker compose up -d postgres redis

# 전체 서비스 실행
docker compose up -d --build
```

---

## C. 공통 – DB 마이그레이션 (Tortoise ORM + Aerich)

```bash
# Aerich 초기 설정 (최초 1회)
uv run aerich init -t app.db.databases.TORTOISE_ORM

# 마이그레이션 파일 생성
uv run aerich migrate --name initial_tables

# 마이그레이션 적용
uv run aerich upgrade

# 마이그레이션 히스토리 확인
uv run aerich history
```

---

## D. 환경변수 설정 (envs/example.local.env)

```env
# ─── App ───
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# ─── Database (PostgreSQL) ───
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthguide
DB_USER=healthguide
DB_PASSWORD=your_password_here

# ─── Redis ───
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ─── JWT ───
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── OAuth ───
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=

# ─── LLM (ChatBot) ───
OPENAI_API_KEY=
LLM_MODEL_NAME=gpt-4o
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# ─── vLLM (Medical Doc / Pill Analysis) ───
VLLM_BASE_URL=http://localhost:8001
VLLM_MODEL_NAME=
VLLM_GPU_MEMORY_UTILIZATION=0.8
VLLM_TENSOR_PARALLEL_SIZE=1
```

---

## E. 트러블슈팅

| 증상 | 해결 방법 |
|------|-----------|
| `uv: command not found` | 터미널 재시작 또는 PATH에 `~/.cargo/bin` 추가 |
| `uv sync` 실패 | `uv cache clean` 후 재시도 |
| DB 연결 실패 | `envs/.local.env`의 DB 정보 확인 + `docker compose up -d postgres` 실행 |
| `torch.cuda.is_available()` = False | NVIDIA 드라이버 + CUDA Toolkit 버전 호환 확인 |
| Docker GPU 인식 안 됨 | `nvidia-container-toolkit` 설치 + Docker 데몬 재시작 |
| macOS에서 vLLM 실행 불가 | Linux GPU 서버에서 실행하거나 Docker 컨테이너 사용 |
| Aerich 마이그레이션 충돌 | `aerich downgrade` 후 충돌 파일 정리 → 재생성 |
| SSE 연결 끊김 | Nginx `proxy_read_timeout` 값 증가 (기본 60s → 300s) |
