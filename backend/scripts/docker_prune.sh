#!/bin/bash
# scripts/docker_prune.sh
# 미사용 Docker 리소스 정리 (실행 중인 컨테이너·볼륨에는 영향 없음)

set -e

echo "=== Docker 디스크 사용량 (정리 전) ==="
docker system df

echo ""
echo "정리 항목:"
echo "  - 중단된 컨테이너"
echo "  - dangling 이미지 (태그 없는 중간 레이어)"
echo "  - 미사용 빌드 캐시"
echo "  - 미사용 네트워크"
echo ""
read -p "계속하시겠습니까? (y/N) " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "취소됨"; exit 0; }

# 중단된 컨테이너 제거
docker container prune -f

# dangling 이미지만 제거 (사용 중인 이미지 보존)
docker image prune -f

# 미사용 빌드 캐시 제거
docker builder prune -f

# 미사용 네트워크 제거
docker network prune -f

echo ""
echo "=== Docker 디스크 사용량 (정리 후) ==="
docker system df
