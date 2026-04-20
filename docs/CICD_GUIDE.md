# HealthGuide CI/CD 가이드

## 목차
1. [전체 구조](#전체-구조)
2. [GitHub Actions 워크플로우](#github-actions-워크플로우)
3. [GitHub Secrets 설정](#github-secrets-설정)
4. [EC2 최초 배포 설정](#ec2-최초-배포-설정)
5. [자동 배포 흐름](#자동-배포-흐름)
6. [로컬 개발 환경](#로컬-개발-환경)
7. [DB 접속 방법 (DBeaver)](#db-접속-방법-dbeaver)
8. [배포 확인 방법](#배포-확인-방법)
9. [Troubleshooting](#troubleshooting)

---

## 전체 구조

```
코드 작성 (feature 브랜치)
    ↓
PR 생성 → GitHub Actions CI 자동 실행
    ├── lint: Ruff 코드 품질 검사
    └── test: Pytest 테스트 실행
    ↓
develop 머지 → main 머지
    ↓
GitHub Actions Deploy 자동 실행
    ↓
EC2 자동 배포 (git pull → docker compose up)
```

---

## GitHub Actions 워크플로우

### 1. CI 검사 (`.github/workflows/checks.yml`)

**트리거**: `main`, `develop` 브랜치에 push 또는 PR

#### lint 잡
- Python 3.13 + uv 설치
- `uv sync --group app --group dev --frozen`
- `ruff check app/ ai_worker/` — 코드 품질 검사
- `ruff format app/ ai_worker/ --check` — 포맷 검사

#### test 잡
- PostgreSQL 16, Redis 7 서비스 컨테이너 실행
- SQLite 인메모리 DB로 테스트 실행 (실제 DB 불필요)
- `pytest app/tests -v --tb=short`
- 커버리지 리포트 출력

> **주의**: 커밋 전 로컬에서 반드시 아래 명령어로 검사 후 푸시
> ```bash
> cd backend
> uv run ruff check app/ ai_worker/ && uv run ruff format app/ ai_worker/ --check
> ```

### 2. 자동 배포 (`.github/workflows/deploy.yml`)

**트리거**: `main` 브랜치에 `backend/` 경로 변경이 포함된 push

**배포 단계**:
1. SSH로 EC2 접속
2. `~/healthguide`에서 `git pull origin main`
3. GitHub Secrets의 `PROD_ENV` → `backend/envs/.prod.env` 파일 생성
4. `docker compose -f docker-compose.prod.yml up -d --build`
5. `docker system prune -f` — 미사용 이미지 정리

---

## GitHub Secrets 설정

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret 이름 | 설명 | 예시 |
|-------------|------|------|
| `EC2_HOST` | EC2 Elastic IP | `13.209.187.137` |
| `EC2_USER` | EC2 접속 유저 | `ubuntu` |
| `EC2_SSH_KEY` | `.pem` 파일 전체 내용 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `PROD_ENV` | `.prod.env` 파일 전체 내용 | 아래 참고 |
| `OPENAI_API_KEY` | OpenAI API 키 (CI 테스트용) | `sk-...` |

### PROD_ENV 내용 예시

```env
APP_ENV=production
APP_DEBUG=false

DB_HOST=db
DB_PORT=5432
DB_USER=healthguide
DB_PASSWORD=your_password
DB_NAME=healthguide_db

POSTGRES_USER=healthguide
POSTGRES_PASSWORD=your_password
POSTGRES_DB=healthguide_db

REDIS_HOST=redis
REDIS_PORT=6379

JWT_SECRET_KEY=your_jwt_secret

OPENAI_API_KEY=sk-your-key

# ... 기타 환경변수
```

> **중요**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`는 반드시 포함해야 해요.
> PostgreSQL 컨테이너 초기화 시 이 값들을 사용해요.

---

## EC2 최초 배포 설정

자동 배포 전 EC2에서 **최초 1회만** 실행해야 해요.

```bash
# 1. EC2 SSH 접속
ssh -i health-guide-key.pem ubuntu@13.209.187.137

# 2. 프로젝트 클론
mkdir -p ~/healthguide
cd ~/healthguide
git clone https://github.com/AI-HealthCare-02/AI_02_07.git .

# 3. prod.env 생성
mkdir -p ~/healthguide/backend/envs
nano ~/healthguide/backend/envs/.prod.env
# PROD_ENV 내용 붙여넣기 후 저장

# 4. 최초 빌드 및 실행
cd ~/healthguide/backend
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 자동 배포 흐름

최초 설정 이후 코드 변경 시 자동으로 배포돼요.

```
1. feature 브랜치에서 개발
2. develop으로 PR → CI 통과 확인
3. develop → main으로 PR → CI 통과 확인
4. main 머지 시 deploy.yml 자동 실행
5. EC2에서 git pull + docker compose up 자동 실행
```

> **주의**: `PROD_ENV` Secret을 수정한 경우, 다음 자동 배포 시 반영돼요.
> 즉시 반영하려면 EC2에서 직접 `.prod.env`를 수정해야 해요.

---

## 로컬 개발 환경

```bash
cd backend

# 전체 서비스 실행 (--reload 핫 리로드 포함)
docker compose up -d --build

# 개별 서비스 실행
docker compose up -d db redis     # DB, Redis만
docker compose up -d app          # FastAPI만

# 로그 확인
docker compose logs app -f

# 중지
docker compose down
```

로컬 접속:
- API 서버: `http://localhost:8000`
- Swagger: `http://localhost:8000/api/docs`
- DB: `localhost:5432`

---

## DB 접속 방법 (DBeaver)

### 방법 1: SSH 터널 (보안 유지, 권장)

EC2 보안그룹에서 5432 포트를 닫아둔 경우 사용해요.

```powershell
# 로컬 Windows에서 실행 (터미널 유지)
ssh -i health-guide-key.pem -L 5433:localhost:5432 ubuntu@13.209.187.137 -N
```

DBeaver 설정:
```
Host: localhost
Port: 5433
Database: healthguide_db
User: healthguide
Password: PROD_ENV의 DB_PASSWORD 값
```

### 방법 2: 직접 접속

EC2 보안그룹에서 5432 포트를 열어둔 경우 사용해요.

DBeaver 설정:
```
Host: 13.209.187.137
Port: 5432
Database: healthguide_db
User: healthguide
Password: PROD_ENV의 DB_PASSWORD 값
```

> **보안 주의**: 운영 완료 후 보안그룹에서 5432 포트를 닫고 SSH 터널 방식으로 전환 권장

---

## 배포 확인 방법

```bash
# 1. 컨테이너 상태 확인
docker compose -f docker-compose.prod.yml ps

# 2. 헬스체크
curl http://localhost/health
# 정상: {"status":"ok","env":"production","dev_login_available":false}

# 3. API DB 연결 확인
curl http://localhost/api/v1/codes/groups

# 4. 서비스별 로그 확인
docker compose -f docker-compose.prod.yml logs app --tail=50
docker compose -f docker-compose.prod.yml logs db --tail=20
docker compose -f docker-compose.prod.yml logs nginx --tail=20
```

---

## Troubleshooting

### CI lint 실패

**증상**: `ruff check` 또는 `ruff format --check` 실패

**원인**: 코드 스타일 오류 (미사용 import, import 정렬, 타입 힌트 등)

**해결**:
```bash
cd backend
uv run ruff check app/ ai_worker/ --fix
uv run ruff format app/ ai_worker/
git add -A && git commit -m "fix: ruff 오류 수정"
```

---

### CI test 실패 — fixture not found

**증상**: `fixture 'async_client' not found`

**원인**: 테스트 파일이 `conftest.py`에 없는 fixture를 사용

**해결**: 해당 테스트 디렉토리에 `conftest.py` 추가
```python
# app/tests/해당폴더/conftest.py
@pytest_asyncio.fixture
async def async_client(mock_user):
    from app.dependencies.security import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: mock_user
    async with AsyncClient(...) as ac:
        yield ac
    app.dependency_overrides.clear()
```

---

### CI test 실패 — E902 파일 없음

**증상**: `E902 지정된 파일을 찾을 수 없습니다`

**원인**: `checks.yml`에서 존재하지 않는 `tests/` 디렉토리를 ruff 검사 대상으로 지정

**해결**: `checks.yml`에서 `tests/` 제거
```yaml
run: uv run ruff check app/ ai_worker/
```

---

### 배포 후 502 Bad Gateway

**증상**: `curl http://localhost/health` → 502

**원인**: app 컨테이너가 실행 중이 아니거나 임포트 오류

**해결**:
```bash
docker logs healthguide-app --tail=50
```
로그에서 `ModuleNotFoundError` 확인 시 → `Dockerfile`에 해당 모듈 복사 추가

---

### ModuleNotFoundError: No module named 'ai_worker'

**증상**: app 컨테이너 시작 실패

**원인**: `Dockerfile`에서 `ai_worker/` 디렉토리를 복사하지 않음

**해결**: `backend/Dockerfile`에 추가
```dockerfile
COPY app/ /code/app/
COPY ai_worker/ /code/ai_worker/   # 이 줄 추가
COPY scripts/sql/ /code/scripts/sql/
```

---

### DB 컨테이너 unhealthy — POSTGRES_PASSWORD not specified

**증상**: `Error: Database is uninitialized and superuser password is not specified`

**원인**: `.prod.env`에 `POSTGRES_PASSWORD`가 없거나 비어있음

**해결**: `.prod.env`에 아래 3줄 추가
```env
POSTGRES_USER=healthguide
POSTGRES_PASSWORD=실제비밀번호
POSTGRES_DB=healthguide_db
```
GitHub Secrets의 `PROD_ENV`에도 동일하게 추가

---

### DB 비밀번호 인증 실패

**증상**: `FATAL: password authentication failed for user "healthguide"`

**원인**: 볼륨에 저장된 비밀번호와 `.prod.env`의 `DB_PASSWORD`가 다름
(볼륨 삭제 없이 재시작하면 기존 비밀번호가 유지됨)

**해결**:
```bash
# 방법 1: DB 비밀번호를 env에 맞게 변경
docker exec healthguide-db psql -U healthguide -d healthguide_db \
  -c "ALTER USER healthguide PASSWORD '새비밀번호';"

# 방법 2: 볼륨 삭제 후 재초기화 (데이터 삭제 주의)
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```

---

### DBeaver 접속 실패 — Connection refused

**증상**: `Connection to 13.209.187.137:5432 refused`

**원인**: `docker-compose.prod.yml`에서 DB 포트가 `127.0.0.1`로만 바인딩됨

**해결**:
```bash
# EC2에서 docker-compose.prod.yml 수정
# db 서비스의 ports를 아래로 변경
ports:
  - "0.0.0.0:5432:5432"

docker compose -f docker-compose.prod.yml up -d db
```

또는 SSH 터널 사용:
```powershell
ssh -i health-guide-key.pem -L 5433:localhost:5432 ubuntu@13.209.187.137 -N
# DBeaver에서 localhost:5433으로 접속
```

---

### 기존 컨테이너 이름 충돌

**증상**: `Conflict. The container name "/healthguide-redis" is already in use`

**원인**: 이전 컨테이너가 제거되지 않은 상태에서 재시작

**해결**:
```bash
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker compose -f docker-compose.prod.yml up -d --build
```

---

### DDL 실행 실패 — duplicate key

**증상**: `duplicate key value violates unique constraint "pg_type_typname_nsp_index"`

**원인**: 이미 테이블/타입이 존재하는 DB에 재실행 시 발생. 정상 동작임

**확인**: 로그 마지막 줄이 `데이터베이스 초기화 완료`이면 무시해도 됨

---

### git clone 실패 — directory not empty

**증상**: `fatal: destination path '.' already exists and is not an empty directory`

**원인**: 디렉토리에 이미 파일이 존재

**해결**:
```bash
cd ~/healthguide
git init
git remote add origin https://github.com/AI-HealthCare-02/AI_02_07.git
git fetch origin main
git reset --hard origin/main
```
