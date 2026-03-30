# 🏥 HealthGuide (수호)

> AI 기반 헬스케어 상담 웹 서비스

## 서비스 개요

HealthGuide는 사용자의 건강 데이터를 기반으로 **AI 챗봇 상담**, **의료 문서 분석**, **건강 가이드 제공**, **알약 분석** 기능을 제공하는 웹 서비스입니다.

## 팀 구성

| 이름 | 역할 | 담당 기능 |
|------|------|-----------|
| 황보수호 | 팀장 | User · Admin · AI-Chat |
| 이승원 | 팀원 | 의료 문서 분석 (vLLM) |
| 한지수 | 팀원 | 건강 가이드 |
| 안은지 | 팀원 | 알약 분석 |

## 기술 스택

| 구분 | 기술 |
|------|------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Package Manager | uv |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| AI / LLM | vLLM, OpenAI API |
| Container | Docker · Docker Compose |
| GPU | NVIDIA CUDA 12.x |

## 프로젝트 구조

```
healthguide/
├── app/
│   ├── main.py                 # FastAPI 엔트리포인트
│   ├── core/
│   │   ├── config.py           # 환경변수 & 설정
│   │   ├── database.py         # DB 연결 (SQLAlchemy)
│   │   └── security.py         # JWT · OAuth
│   ├── domain/
│   │   ├── user/               # 회원가입 · 로그인 · 프로필
│   │   ├── admin/              # 관리자 대시보드 · 설정
│   │   ├── chat/               # AI 챗봇 (SSE 스트리밍)
│   │   ├── medical_doc/        # 의료 문서 분석 (vLLM)
│   │   ├── guide/              # 건강 가이드
│   │   └── pill/               # 알약 분석
│   ├── infrastructure/
│   │   ├── llm/                # LLM 클라이언트 래퍼
│   │   ├── redis/              # Redis 캐시 유틸
│   │   └── storage/            # 파일 스토리지
│   └── common/
│       ├── exceptions.py       # 글로벌 예외 처리
│       ├── responses.py        # 공통 응답 스키마
│       └── middleware.py       # 로깅 · CORS · 인증
├── alembic/                    # DB 마이그레이션
│   └── versions/
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── 요구사항_정의서.md
│   ├── API_명세서.md
│   └── SERVER_SETUP.md
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/healthguide.git
cd healthguide

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 DB, Redis, API 키 등을 입력

# 3-A. Docker로 실행 (권장)
docker compose up --build

# 3-B. 로컬 실행 (상세 → docs/SERVER_SETUP.md 참조)
uv sync
uv run uvicorn app.main:app --reload
```

## 문서

- [서버 셋업 가이드](docs/SERVER_SETUP.md)
- [요구사항 정의서](docs/요구사항_정의서.md)
- [API 명세서](docs/API_명세서.md)

## 브랜치 전략

```
main          ← 배포용 (PR 머지만 허용)
 └─ develop   ← 통합 개발 브랜치
     ├─ feature/user-auth
     ├─ feature/admin-dashboard
     ├─ feature/chat-sse
     ├─ feature/medical-doc
     ├─ feature/guide
     └─ feature/pill-analysis
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
