# HealthGuide — AI 기반 헬스케어 상담 웹 서비스

> 4인 팀 프로젝트 | 2025 | Python · FastAPI · Next.js · PostgreSQL · OpenAI

---

## 프로젝트 개요

사용자의 건강 데이터를 기반으로 **AI 챗봇 상담**, **의료 문서 분석**, **건강 가이드 관리**, **알약 분석** 기능을 제공하는 풀스택 헬스케어 서비스입니다.
전문 의료 행위를 대체하지 않으며, 보조적 건강 관리 도구로 활용됩니다.

---

## 담당 역할 (황보수호 — 팀장)

- 프로젝트 아키텍처 설계 및 공통 인프라 구축
- **User · Admin API** 전체 구현 (인증, 프로필, 건강정보)
- **AI 챗봇** 기능 전체 구현 (필터링 파이프라인 + SSE 스트리밍)
- Docker Compose 기반 전체 서비스 스택 구성
- CI/CD 스크립트 및 EC2 배포 자동화

---

## 핵심 기능 및 구현 포인트

### 1. AI 챗봇 — 2단계 GPT 파이프라인 + SSE 스트리밍

사용자 질문을 **1단계 분류 → 2단계 스트리밍 답변** 구조로 처리합니다.

```
사용자 입력
    │
    ▼
[1단계] 분류 (gpt-4o-mini, non-streaming)
    EMERGENCY → 즉시 응급 안내 반환
    OTHER     → 도메인 외 차단 메시지 반환
    GREETING  → 인사 모드로 2단계 진입
    DOMAIN    → 일반 건강 상담으로 2단계 진입
    │
    ▼
[2단계] 스트리밍 답변 (SSE token-by-token)
    - 사용자 건강 프로필(키·몸무게·기저질환·알레르기 등) 컨텍스트 주입
    - Redis cancel 키로 스트리밍 중단 지원
    - 응답 완료 후 DB 저장 (토큰 수, 지연시간 포함)
```

- `app/services/chat_service.py` — 비즈니스 로직 + SSE 생성기
- `ai_worker/tasks/chat_filter.py` — 워커 큐용 독립 필터 태스크

### 2. 약품 RAG (Retrieval-Augmented Generation)

공공 약품 데이터(약 36만 건 이상 JSONL)를 **pgvector**에 임베딩하여 의미 기반 검색을 제공합니다.

- `text-embedding-3-small` 모델로 효능효과·주의사항·주성분 3종 청크 생성
- `pgvector` cosine similarity 검색 + IVFFlat 인덱스
- `pg_trgm` 기반 약품명 오타 허용 검색
- Redis 1시간 캐싱으로 중복 임베딩 API 호출 방지
- `scripts/embed_drugs.py` — 비동기 배치 임베딩 스크립트 (배치 100건, 동시 5개)

### 3. 의료 문서 분석 (vLLM · OCR)

처방전·진료기록·약봉투 이미지를 업로드하면 OCR + LLM으로 구조화된 데이터를 추출합니다.

- 문서 종류 자동 인식 (처방전 / 진료기록 / 약봉투)
- confidence 0.7 미만 항목 경고 로깅
- 분석 결과를 건강 가이드로 자동 연동 (`create_guide_from_doc`)

### 4. 건강 가이드 & 복약 관리

- 처방 약물 등록 및 복약 체크 (일별·월별 달력)
- 최근 7일 복약 이행률 자동 계산
- AI 가이드 생성 (복약 안내·생활습관·주의사항 3종)
- 복약 알림 설정 (브라우저 알림·이메일)

### 5. 인증 시스템

- JWT (Access + Refresh Token) 발급·검증
- OAuth 소셜 로그인 연동
- FastAPI Depends 기반 인증 의존성 주입

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.13, FastAPI, Tortoise ORM |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, Zustand |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| AI / LLM | OpenAI GPT-4o-mini, text-embedding-3-small, vLLM |
| Streaming | SSE (Server-Sent Events) |
| Package Manager | uv |
| Container | Docker, Docker Compose |
| Reverse Proxy | Nginx |
| CI/CD | Ruff, Mypy, Pytest, GitHub Actions, EC2 자동 배포 |

---

## 아키텍처

```
[Client: Next.js]
        │  HTTP / SSE
        ▼
[Nginx: Reverse Proxy]
        │
        ▼
[FastAPI App Server]
   ├── Auth / User API
   ├── Chat API (SSE Streaming)
   ├── Medical Doc API
   ├── Guide API
   └── RAG API
        │                    │
        ▼                    ▼
[PostgreSQL + pgvector]   [Redis]
                             │
                             ▼
                      [AI Worker (별도 프로세스)]
                         ├── chat_filter
                         ├── medical_doc (vLLM)
                         └── pill_analysis
```

---

## 프로젝트 구조 (주요 부분)

```
backend/
├── app/
│   ├── apis/v1/          # 라우터 (auth, user, chat, guide, medical_doc, rag)
│   ├── services/         # 비즈니스 로직
│   │   ├── chat_service.py       # SSE 스트리밍 + 2단계 분류
│   │   ├── rag_service.py        # pgvector 약품 검색
│   │   ├── guide_service.py      # 복약 가이드 관리
│   │   └── medical_doc_service.py# 문서 분석 결과 처리
│   └── models/           # Tortoise ORM 모델
├── ai_worker/
│   └── tasks/
│       ├── chat_filter.py        # 질문 필터링 워커
│       ├── medical_doc.py        # 문서 분석 워커 (vLLM)
│       └── pill_analysis.py      # 알약 분석 워커
└── scripts/
    └── embed_drugs.py            # 약품 데이터 pgvector 임베딩
frontend/
└── src/
    ├── app/              # Next.js App Router
    ├── components/       # UI 컴포넌트
    └── store/            # Zustand 상태 관리
```

---

## 트러블슈팅 & 기술적 의사결정

**SSE 스트리밍 중 취소 처리**
- 스트리밍 도중 사용자가 취소 요청 시 Redis에 `chat:cancel:{message_id}` 키를 설정
- 스트리밍 루프에서 매 청크마다 Redis 키 존재 여부를 확인하여 즉시 중단

**AI 설정 동적 변경**
- `ai_settings` 테이블에서 모델명·시스템 프롬프트·temperature를 관리자가 실시간 변경 가능
- 60초 인메모리 캐시로 DB 조회 부하 최소화

**약품 임베딩 대용량 처리**
- 36만 건 이상의 약품 데이터를 배치 100건 단위로 비동기 처리
- `--skip-existing` 옵션으로 중단 후 재실행 시 기존 데이터 건너뜀
- Rate limit 대응을 위한 배치 간 딜레이 및 자동 재시도 로직

**API 서버 / AI 워커 분리**
- 무거운 모델 추론(vLLM) 작업을 별도 워커 프로세스로 분리하여 API 서버 응답성 유지
- Redis 큐를 통한 비동기 작업 전달

---

## GitHub

[https://github.com/AI-HealthCare-02/AI_02_07](https://github.com/AI-HealthCare-02/AI_02_07)
