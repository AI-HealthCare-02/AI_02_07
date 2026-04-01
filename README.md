# 🏥 HealthGuide

> AI 기반 헬스케어 상담 웹 서비스

이 프로젝트는 **AI 모델 추론(Inference) 워커**와 **FastAPI API 서버**를 통합한 헬스케어 서비스입니다.
Python 패키지 관리 도구 `uv`와 컨테이너화 도구 `Docker`를 활용하여 일관된 개발 및 배포 환경을 제공합니다.

---

## 서비스 개요

HealthGuide는 사용자의 건강 데이터를 기반으로 **AI 챗봇 상담**, **의료 문서 분석**, **건강 가이드 제공**, **알약 분석** 기능을 제공하는 웹 서비스입니다.
본 서비스는 전문 의료 행위를 대체하지 않으며, 보조적 건강 관리 도구로 활용됩니다.

---

## 🚀 주요 특징

- **FastAPI Framework**: 고성능 비동기 API 서버 구현
- **AI Worker**: 모델 추론 작업(vLLM 의료 문서 분석, 알약 분석)을 API 서버와 분리하여 처리
- **UV Package Manager**: 매우 빠른 의존성 설치 및 가상환경 관리
- **Tortoise ORM**: 비동기 방식의 데이터베이스 모델링 및 쿼리 관리
- **Raw SQL 초기화**: 서버 시작 시 DDL + 공통코드 시딩을 Raw SQL로 자동 실행
- **SSE Streaming**: AI 챗봇 실시간 토큰 단위 응답 스트리밍
- **3단계 질문 필터링**: 도메인 체크 → 위험도 체크 → 답변 생성
- **Docker-Compose**: PostgreSQL, Redis, Nginx, vLLM을 포함한 전체 서비스 스택을 한 번에 실행
- **CI/CD Scripts**: 코드 포맷팅(Ruff), 타입 체크(Mypy), 테스트(Pytest) 자동화 스크립트 제공

---

## 팀 구성

| 이름 | 역할 | 담당 기능 |
|------|------|-----------|
| 황보수호 | 팀장 | User · Admin · AI-Chat |
| 이승원 | 팀원 | 의료 문서 분석 (vLLM) |
| 한지수 | 팀원 | 건강 가이드 |
| 안은지 | 팀원 | 알약 분석 |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Language | Python 3.13+ |
| Framework | FastAPI |
| Package Manager | uv |
| ORM | Tortoise ORM |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| AI / LLM | OpenAI GPT API, vLLM |
| Streaming | SSE (Server-Sent Events) |
| Container | Docker · Docker Compose |
| Reverse Proxy | Nginx |
| GPU | NVIDIA CUDA 12.x |
| CI/CD | Ruff, Mypy, Pytest, Shell Scripts |

---

## 📂 프로젝트 구조

```text
AI_02_07/
├── backend/                          # 백엔드 전체
│   ├── ai_worker/                    # AI 모델 추론 워커 (API 서버와 분리)
│   │   ├── core/                     # 워커 설정, 로거, Redis/S3 클라이언트
│   │   ├── schemas/                  # 워커 입출력 스키마
│   │   ├── tasks/                    # 추론 작업 정의
│   │   │   ├── chat_filter.py        # 3단계 질문 필터링 – 황보수호
│   │   │   ├── medical_doc.py        # 의료 문서 분석 (vLLM) – 이승원
│   │   │   └── pill_analysis.py      # 알약 분석 – 안은지
│   │   ├── Dockerfile
│   │   └── main.py                   # 워커 진입점
│   ├── app/                          # FastAPI 서버 코드
│   │   ├── apis/                     # API 라우터
│   │   │   └── v1/
│   │   │       ├── auth.py           # 인증 (OAuth, JWT)
│   │   │       ├── user.py           # 사용자 프로필 · 건강정보
│   │   │       ├── common_code.py    # 공통코드 조회
│   │   │       └── __init__.py       # 라우터 등록
│   │   ├── core/                     # 서버 설정 (pydantic-settings)
│   │   │   ├── config.py             # 환경변수 & 설정
│   │   │   ├── security.py           # JWT · OAuth 유틸
│   │   │   ├── redis.py              # Redis 연결 관리
│   │   │   └── s3.py                 # AWS S3 클라이언트
│   │   ├── db/                       # DB 초기화 및 마이그레이션 (Tortoise ORM)
│   │   │   ├── migrations/
│   │   │   └── databases.py
│   │   ├── dependencies/             # FastAPI 의존성 주입
│   │   │   └── security.py           # 인증 의존성
│   │   ├── dtos/                     # 데이터 전송 객체 (Pydantic models)
│   │   │   ├── auth_dto.py
│   │   │   ├── user_dto.py
│   │   │   ├── common_code_dto.py
│   │   │   └── common_dto.py         # 공통 응답 래퍼
│   │   ├── models/                   # DB 테이블 정의 (Tortoise 모델)
│   │   │   ├── user.py
│   │   │   ├── user_lifestyle.py
│   │   │   ├── user_allergy.py
│   │   │   ├── user_disease.py
│   │   │   ├── admin.py
│   │   │   ├── common_code.py
│   │   │   └── system_error_log.py
│   │   ├── repositories/             # DB 접근 레이어
│   │   │   └── user_repository.py
│   │   ├── services/                 # 비즈니스 로직
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── oauth_service.py
│   │   │   ├── jwt.py                # JWT 발급 · 검증
│   │   │   ├── common_code_service.py# 공통코드 조회 · 캐시
│   │   │   ├── db_init_service.py    # 서버 시작 시 DDL + 시딩
│   │   │   ├── error_log_service.py
│   │   │   └── task_queue.py         # Redis 작업 큐
│   │   ├── tests/                    # 테스트 코드
│   │   │   ├── auth_apis/
│   │   │   └── user_apis/
│   │   ├── utils/                    # 공통 유틸리티
│   │   │   └── jwt/                  # JWT 백엔드 구현
│   │   ├── validators/               # 입력값 검증
│   │   ├── Dockerfile
│   │   └── main.py                   # FastAPI 애플리케이션 진입점
│   ├── envs/                         # 환경 변수 설정 파일
│   │   ├── example.local.env
│   │   └── example.prod.env
│   ├── nginx/                        # Nginx 설정 파일 (리버스 프록시)
│   │   ├── default.conf
│   │   ├── prod_http.conf
│   │   └── prod_https.conf
│   ├── scripts/                      # 배포 및 CI 스크립트
│   │   ├── ci/
│   │   │   ├── run_test.sh           # Pytest 실행
│   │   │   ├── code_fommatting.sh    # Ruff 포맷팅
│   │   │   └── check_mypy.sh         # Mypy 타입 체크
│   │   ├── sql/
│   │   │   ├── create_tables.sql     # 전체 테이블 DDL
│   │   │   └── seed_common_codes.sql # 공통코드 시드 데이터
│   │   ├── deployment.sh             # EC2 자동 배포
│   │   └── certbot.sh                # SSL 인증서 발급
│   ├── certbot/                      # Let's Encrypt 인증서
│   ├── uploads/                      # 업로드 파일 저장소
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                         # 프론트엔드 (개발 예정)
├── docs/
│   ├── DOCKER_SETUP.md
│   └── SERVER_SETUP.md
├── .github/
│   └── workflows/
└── README.md
```

---

## ⚙️ 사전 준비 사항

| 도구 | 버전 | 비고 |
|------|------|------|
| Python | 3.13 이상 | 로컬 개발 환경용 |
| uv | 최신 | [설치 가이드](https://github.com/astral-sh/uv) |
| Docker & Docker Compose | v2 | 전체 서비스 실행용 |
| NVIDIA Driver | 535+ | GPU 사용 시 |
| NVIDIA Container Toolkit | 최신 | Docker GPU 지원 |
| Git | 최신 | |

---

## 🛠️ 설치 및 설정

### 1. 가상환경 구축 및 의존성 설치

```bash
# 저장소 클론
git clone https://github.com/AI-HealthCare-02/AI_02_07.git
cd AI_02_07/backend

# 전체 의존성 설치 (가상환경 자동 생성)
uv sync

# 특정 그룹의 의존성만 설치하려는 경우
uv sync --extra app   # API 서버용
uv sync --extra ai    # AI 워커용 (vLLM, torch 등)
```

### 2. 환경 변수 설정

```bash
# 로컬용
cp envs/example.local.env envs/.local.env

# 배포용
cp envs/example.prod.env envs/.prod.env
```

생성된 `.env` 파일을 프로젝트 상황에 맞게 수정하세요.

---

## 🏃 실행 방법

### 1. Docker Compose로 전체 스택 실행 (권장)

```bash
cd backend

# 전체 서비스 (API + Worker + DB + Redis + Nginx)
docker compose up -d --build

# GPU 포함 (워커)
docker compose --profile gpu up -d --build
```

실행 후 접속 주소:
- **API 문서 (Swagger UI)**: [http://localhost/api/docs](http://localhost/api/docs)
- **Nginx**: 80 포트를 통해 API 서버로 요청 전달

### 2. 로컬에서 개별 실행 (개발용)

```bash
cd backend

# FastAPI 서버 실행
uv run uvicorn app.main:app --reload
# or
docker compose up -d --build app

# AI Worker 실행
uv run python -m ai_worker.main
# or
docker compose up -d --build ai_worker
```

### 3. EC2 배포 환경 (Production)

#### 사전 준비
- EC2 인스턴스 (Ubuntu 권장)
- SSH 키 페어 (`~/.ssh/` 경로에 위치)
- Docker Hub 계정 및 Personal Access Token
- 배포용 환경 변수 설정 (`envs/.prod.env`)
- 도메인 구매 (Gabia, GoDaddy, AWS Route53 등)

#### 자동 배포 스크립트 실행

```bash
chmod +x backend/scripts/deployment.sh
./backend/scripts/deployment.sh
```

스크립트 실행 시 입력 항목:
1. Docker Hub 계정 정보 (Username, PAT)
2. 이미지를 업로드할 레포지토리 이름
3. 배포할 서비스 선택 (FastAPI, AI-Worker) 및 버전(Tag)
4. SSH 키 파일명 및 EC2 IP 주소
5. HTTPS 사용 여부 (사용 시 도메인 추가 입력)

#### SSL(HTTPS) 설정 (Certbot)

```bash
chmod +x backend/scripts/certbot.sh
./backend/scripts/certbot.sh
```

1. 도메인 주소 및 이메일 입력
2. SSH 키 파일명 및 EC2 IP 주소 입력
3. Let's Encrypt 인증서 발급 및 Nginx 자동 갱신 적용

---

## 🧪 테스트 및 품질 관리

```bash
cd backend

# 테스트 실행
./scripts/ci/run_test.sh

# 코드 포맷팅 확인 (Ruff)
./scripts/ci/code_fommatting.sh

# 정적 타입 검사 (Mypy)
./scripts/ci/check_mypy.sh
```

---

## 📝 개발 가이드

- **API 추가**: `backend/app/apis/v1/` 아래에 새로운 라우터 파일을 생성하고 `app/apis/v1/__init__.py`에 등록
- **DB 모델 추가**: `backend/app/models/`에 Tortoise 모델을 정의하고 `app/db/databases.py`의 `MODELS` 리스트에 추가
- **테이블 추가**: `backend/scripts/sql/create_tables.sql`에 DDL 추가, 공통코드는 `seed_common_codes.sql`에 추가
- **AI 로직 추가**: `backend/ai_worker/tasks/`에 새로운 처리 로직을 작성하고 `ai_worker/main.py`에서 호출하도록 구성
- **DTO 추가**: `backend/app/dtos/`에 Pydantic 스키마를 정의하여 요청/응답 검증에 활용

---

## 브랜치 전략

```
main          ← 배포용 (PR 머지만 허용)
 └─ develop   ← 통합 개발 브랜치
     ├─ feature/user          (황보수호)
     ├─ feature/admin         (황보수호)
     ├─ feature/chat          (황보수호)
     ├─ feature/medical-doc   (이승원)
     ├─ feature/guide         (한지수)
     └─ feature/pill-analysis (안은지)
```

## 커밋 컨벤션

```
feat:     새로운 기능
fix:      버그 수정
docs:     문서 수정
refactor: 리팩토링
test:     테스트 추가/수정
chore:    빌드, 설정 변경
```

---

## 문서

- [서버 셋업 가이드](docs/SERVER_SETUP.md)
- [Docker 셋업 가이드](docs/DOCKER_SETUP.md)
- [개발 가이드](docs/개발%20가이드.txt)
