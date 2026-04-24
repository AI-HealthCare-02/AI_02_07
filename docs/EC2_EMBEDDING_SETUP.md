# EC2 임베딩 작업 및 서버 설정 가이드

> EC2 (Ubuntu) 환경에서 약품 임베딩 데이터 생성 및 서버 최적화 작업 기록

---

## 1. 약품 임베딩 생성 (embed_drugs.py)

### 전체 약품 임베딩

```bash
nohup bash -c '
source /home/ubuntu/healthguide/backend/envs/.prod.env
OPENAI_API_KEY=$OPENAI_API_KEY DB_HOST=localhost DB_PORT=5432 \
DB_USER=$DB_USER DB_PASSWORD=$DB_PASSWORD DB_NAME=$DB_NAME \
uv run python scripts/embed_drugs.py --skip-existing
' > /tmp/embed_log.txt 2>&1 &

tail -f /tmp/embed_log.txt
```

**결과**: 약품 36,297개, 청크 97,382개 완료 | 소요시간: 2254.2초

---

## 2. 낱알식별 데이터 수집 (fetch_pill_imprint.py)

### 파일 존재 여부 확인

```bash
ls -lh ~/healthguide/backend/drug_json/imprint_data.jsonl
wc -l ~/healthguide/backend/drug_json/imprint_data.jsonl
head -1 ~/healthguide/backend/drug_json/imprint_data.jsonl
```

- 저장 위치: `backend/drug_json/imprint_data.jsonl`
- 수집 결과: 24,628건

> 파일이 이미 존재하면 fetch 단계 생략 가능

### 낱알 데이터 fetch (파일 없을 경우)

```bash
nohup bash -c '
source /home/ubuntu/healthguide/backend/envs/.prod.env
DB_HOST=localhost DB_PORT=5432 \
DB_USER=$DB_USER DB_PASSWORD=$DB_PASSWORD DB_NAME=$DB_NAME \
uv run python scripts/fetch_pill_imprint.py
' > /tmp/fetch_pill_log.txt 2>&1 &

tail -f /tmp/fetch_pill_log.txt
```

---

## 3. 낱알 임베딩 생성 (--imprint-only)

```bash
nohup bash -c '
source /home/ubuntu/healthguide/backend/envs/.prod.env
OPENAI_API_KEY=$OPENAI_API_KEY DB_HOST=localhost DB_PORT=5432 \
DB_USER=$DB_USER DB_PASSWORD=$DB_PASSWORD DB_NAME=$DB_NAME \
uv run python scripts/embed_drugs.py --imprint-only --skip-existing
' > /tmp/embed_pill_log.txt 2>&1 &

tail -f /tmp/embed_pill_log.txt
```

**결과**: 약품 24,613개, 청크 24,628개 완료 | 소요시간: 422.9초

---

## 4. IVFFlat 인덱스 생성

psql이 EC2에 설치되어 있지 않으므로 Docker 컨테이너를 통해 실행

```bash
source /home/ubuntu/healthguide/backend/envs/.prod.env
docker exec -i healthguide-db psql -U $DB_USER -d $DB_NAME -c "
SET maintenance_work_mem = '256MB';
CREATE INDEX idx_drug_emb_ivfflat
    ON drug_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"
```

> `maintenance_work_mem` 기본값(64MB)으로는 메모리 부족 에러 발생 → 256MB로 설정 필요  
> 성공 시 `SET` / `CREATE INDEX` 메시지 출력

---

## 5. 서버 리소스 확인 방법

```bash
free -h                      # 메모리
df -h                        # 디스크
top                          # CPU + 메모리 실시간
docker stats --no-stream     # 컨테이너별 리소스
```

### 확인 당시 상태 (2026-04-23 기준)

| 항목 | 상태 |
|------|------|
| 메모리 | 3.7GB 중 2.4GB 여유 (안전) |
| 디스크 | 29GB 중 16GB 사용 (54%) |
| CPU | 99% idle |
| 스왑 | 설정 전 0B → 2GB 설정 완료 |

---

## 6. 스왑 메모리 설정

스왑이 없으면 메모리 스파이크 시 OOM으로 컨테이너가 종료될 수 있음

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

- `/etc/fstab`에 등록하여 재부팅 후에도 유지
- 설정 확인: `free -h` → Swap 항목에 `2.0Gi` 표시

---

## 작업 완료 체크리스트

- [x] 전체 약품 임베딩 (36,297개)
- [x] 낱알식별 데이터 수집 (24,628건)
- [x] 낱알 임베딩 (24,613개)
- [x] IVFFlat 인덱스 생성
- [x] 스왑 메모리 2GB 설정
