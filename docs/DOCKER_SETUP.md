- pyproject.toml, uv.lock에 명시된 의존성 라이브러리들 설치
- uv 가상환경에 sync는 pyproject.toml에 명시된 의존성 라이브러리들을 설치합니다.
- --all-groups 는 pyproject.toml 내에 분리된 의존성 그룹(dev, app, ai 등)의 패키지를 모두 설치합니다.
- --frozen 은 패키지 설치시 uv.lock 파일에 명시된 것을 기준으로 패키지버젼을 고정하여 설치합니다.
uv sync --all-groups --frozen

# sample 파일을 사용하여 로컬용, 배포용 env 파일 복사
cp envs/example.local.env envs/.local.env
cp envs/example.prod.env envs/.prod.env

# 윈도우라면
cmd /c mklink .env envs\.local.env

# 맥이라면
ln -s envs/.local.env .env

# ── (DB + Redis + app + nginx) ── 여기까지 진행하면 다 됨.
docker compose up -d db redis app nginx





# 도움 될만한 것들
# ── 앱 + 워커 (GPU 없이) ──
docker compose up -d --build

# ── GPU 포함 전체 (vLLM) ──
docker compose --profile gpu up -d --build

# ── 로컬 개발 (서버만) ──
uv run uvicorn app.main:app --reload

# ── 로컬 개발 (워커만) ──
uv run python -m ai_worker.main

# ── 로그 확인 ──
docker compose logs -f app
docker compose logs -f ai_worker

# ── 중지 ──
docker compose down

# ── 볼륨 포함 완전 삭제 ──
docker compose down -v

# ── 테스트 ──
./scripts/ci/run_test.sh

# ── 코드 포맷팅 ──
./scripts/ci/code_formatting.sh

# ── 타입 체크 ──
./scripts/ci/check_mypy.sh

# ── EC2 배포 ──
./scripts/deployment.sh

# ── SSL 인증서 ──
./scripts/certbot.sh



# 시나리오 1 — API 코드 수정 중 (가장 흔한 경우)

DB와 Redis만 Docker로 띄우고, FastAPI는 로컬에서 --reload로 실행합니다. 코드를 저장할 때마다 서버가 자동 재시작되니까 개발 속도가 빠릅니다.


docker compose up -d postgres redis          # 인프라만
uv run uvicorn app.main:app --reload         # 로컬에서 핫리로드

# 시나리오 2 — AI Worker 로직 개발 중 (이승원, 안은지)

마찬가지로 인프라만 Docker로 띄우고, Worker를 로컬에서 직접 실행하면 디버깅이 편합니다.


docker compose up -d postgres redis
uv run python -m ai_worker.main              # 로컬에서 워커 디버깅

# 시나리오 3 — 통합 테스트 또는 데모

전체를 한 번에 올려서 실제 서비스처럼 동작하는지 확인합니다. GPU가 없는 환경이면 vLLM 없이 띄웁니다.


docker compose up -d --build                 # GPU 없이 전체
docker compose --profile gpu up -d --build   # GPU 있으면 vLLM 포함

# 정리하면
개발 중 (코드 자주 수정)  →  인프라만 Docker + 로컬 실행 (핫리로드)

통합 테스트 / 데모        →  Docker로 전체 실행

배포 (EC2)               →  GPU 포함 전체 실행