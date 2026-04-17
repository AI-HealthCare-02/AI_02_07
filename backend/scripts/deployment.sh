# #!/bin/bash
# set -eo pipefail

# COLOR_GREEN=$(tput setaf 2)
# COLOR_BLUE=$(tput setaf 4)
# COLOR_RED=$(tput setaf 1)
# COLOR_NC=$(tput sgr0)

# cd "$(dirname "$0")/.."
# source ./envs/.prod.env

# # ---------- 도커 이미지 빌드 및 푸시 함수 ----------
# build_and_push () {
#   local docker_user=$1
#   local docker_repo=$2
#   local name=$3
#   local tag=$4
#   local dockerfile=$5
#   local context=$6
#   local tag_base=""

#   if [[ "$name" == "FastAPI" ]]; then
#     tag_base="app"
#   else
#     tag_base="ai"
#   fi
#   echo "${COLOR_BLUE}${name} Docker Image Build Start.${COLOR_NC}"
#   docker build --platform linux/amd64 -t ${docker_user}/${docker_repo}:${tag_base}-${tag} -f ${dockerfile} ${context}

#   echo "${COLOR_BLUE}${name} Docker Image Push Start.${COLOR_NC}"
#   docker push ${docker_user}/${docker_repo}:${tag_base}-${tag}

#   echo "${COLOR_GREEN}${name} Done.${COLOR_NC}"
#   echo ""
# }

# # ---------- Docker login Prompt ----------
# echo "${COLOR_BLUE}도커 유저네임과 비밀번호(PAT)을 입력해주세요.${COLOR_NC}"
# read -p "username: " docker_user
# read -p "password: " docker_pw
# echo ""


# # ---------- Docker Login ----------
# echo "${COLOR_BLUE}Docker login${COLOR_NC}"
# if ! docker login -u ${docker_user} -p ${docker_pw} ; then
#   echo "${COLOR_RED}도커 로그인에 실패했습니다. 도커 유저네임과 비밀번호를 확인해주세요.${COLOR_NC}"
# fi
# echo "${COLOR_GREEN}도커 로그인 성공!${COLOR_NC}"
# echo ""

# # ---------- Docker Repository Input Prompt ----------
# echo "${COLOR_BLUE}도커 이미지를 업로드할 레포지토리 이름을 입력해주세요.${COLOR_NC}"
# read -p "Docker Repository Name: " docker_repo
# echo ""

# # ---------- Select Prompt ----------
# echo "${COLOR_BLUE}배포 전 빌드 & 푸시할 이미지를 선택하세요(복수선택 가능, 띄어쓰기로 구분)${COLOR_NC}"
# echo "1) fastapi"
# echo "2) ai_worker"
# read -p "선택 (예: 1 2): " selections
# echo ""


# # ---------- Docker Image Build & Push ----------
# DEPLOY_SERVICES=()

# for choice in $selections; do
#   case $choice in
#     1)
#       echo "${COLOR_BLUE}FastAPI 앱의 배포 버젼을 입력하세요(ex. v1.0.0)${COLOR_NC}"
#       read -p "FastAPI 앱 버젼: " fastapi_version
#       build_and_push ${docker_user} ${docker_repo} "FastAPI" ${fastapi_version} "app/Dockerfile" "."
#       DEPLOY_SERVICES+=("fastapi")
#       ;;
#     2)
#       echo "${COLOR_BLUE}AI-worker 앱의 배포 버젼을 입력하세요(ex. v1.0.0)${COLOR_NC}"
#       read -p "AI-worker 앱 버젼: " ai_version
#       build_and_push ${docker_user} ${docker_repo} "AI Worker" ${ai_version} "ai_worker/Dockerfile" "."
#       DEPLOY_SERVICES+=("ai-worker")
#       ;;
#     *)
#       echo "${COLOR_RED}잘못된 선택입니다: $choice${COLOR_NC}"
#       exit 1
#       ;;
#   esac
# done

# echo "${COLOR_GREEN}모든 선택된 이미지 빌드 & 푸시 완료! 🎉${COLOR_NC}"
# echo "${COLOR_BLUE}배포 대상 서비스: ${DEPLOY_SERVICES[*]}${COLOR_NC}"
# echo ""

# # ---------- SSH 접속 정보 입력 prompt ----------
# echo "${COLOR_BLUE}EC2 인스턴스 생성시 발급받은 ssh key 파일의 파일명을 입력하세요.(ex. ai_health_key.pem)${COLOR_NC}"
# read -p "SSH 키 파일명: " ssh_key_file
# echo ""

# echo "${COLOR_BLUE}EC2 인스턴스의 IP를 입력하세요.${COLOR_NC}"
# read -p "EC2-IP: " ec2_ip
# echo ""

# echo "${COLOR_BLUE}배포중인 서버의 https 여부를 선택하세요.${COLOR_NC}"
# echo "1) http 사용중"
# echo "2) https 사용중"
# read -p "선택(ex. 1): " is_https
# echo ""

# # ---------- EC2 내에 배포 준비 파일 복사  ----------
# scp -i ~/.ssh/${ssh_key_file} envs/.prod.env ubuntu@${ec2_ip}:~/project/.env
# scp -i ~/.ssh/${ssh_key_file} docker-compose.prod.yml ubuntu@${ec2_ip}:~/project/docker-compose.yml
# if is_https ; then
#   # ---------- prod_https.conf 파일의 server_name, ssl_certificate 자동 수정 ----------
#   sed -i '' "s/server_name .*/server_name ${ec2_ip};/g" nginx/prod_http.conf
#   scp -i ~/.ssh/${ssh_key_file} nginx/prod_http.conf ubuntu@${ec2_ip}:~/project/nginx/default.conf
# else
#   echo "${COLOR_BLUE} 사용중인 도메인을 입력하세요. (ex. api.ozcoding.site)${COLOR_NC}"
#   read -p "Domain: " domain
#   # ---------- prod_https.conf 파일의 server_name, ssl_certificate 자동 수정 ----------
#   sed -i '' "s/server_name .*/server_name ${domain};/g" nginx/prod_https.conf
#   sed -i '' "s|/etc/letsencrypt/live/[^/]*|/etc/letsencrypt/live/${domain}|g" nginx/prod_https.conf
#   scp -i ~/.ssh/${ssh_key_file} nginx/prod_https.conf ubuntu@${ec2_ip}:~/project/nginx/default.conf
# fi

# # ---------- EC2 배포 자동화  ----------
# echo "${COLOR_BLUE}EC2 인스턴스에 SSH 접속을 시도합니다.${COLOR_NC}"
# chmod 400 ~/.ssh/${ssh_key_file}
# ssh -i ~/.ssh/${ssh_key_file} ubuntu@${ec2_ip} \
#   "DOCKER_USERNAME=${docker_user} \
#    DOCKER_PAT=${docker_pw} \
#    DEPLOY_SERVICES='${DEPLOY_SERVICES[*]}' \
#    bash -s" << 'EOF'
#   set -e
#   cd project

#   echo "Docker login"
#   docker login -u "$DOCKER_USERNAME" -p "$DOCKER_PAT"

#   echo "Deploying services: $DEPLOY_SERVICES"
#   docker compose up -d --pull always --no-deps $DEPLOY_SERVICES

#   docker image prune -af
# EOF

# echo "✅ Deployment finished."
#!/usr/bin/env bash
# scripts/deployment.sh
# ──────────────────────────────────────────────
# EC2 자동 배포 스크립트
#
# 흐름:
#   1. Docker 이미지 빌드
#   2. Docker Hub에 푸시
#   3. EC2 SSH 접속하여 이미지 풀 + 컨테이너 재시작
# ──────────────────────────────────────────────

set -euo pipefail

echo "========================================"
echo "🚀 HealthGuide 배포 스크립트"
echo "========================================"

# ── 1. Docker Hub 인증 정보 ──
read -rp "Docker Hub Username: " DOCKER_USERNAME
read -rsp "Docker Hub PAT (Personal Access Token): " DOCKER_PAT
echo ""
echo "$DOCKER_PAT" | docker login --username "$DOCKER_USERNAME" --password-stdin
echo "✅ Docker Hub 로그인 성공"

# ── 2. 이미지 설정 ──
read -rp "Docker Hub 레포지토리 이름 (예: healthguide): " REPO_NAME

echo ""
echo "배포할 서비스를 선택하세요:"
echo "  1) FastAPI API 서버"
echo "  2) AI Worker"
echo "  3) 둘 다"
read -rp "선택 (1/2/3): " SERVICE_CHOICE

read -rp "이미지 태그 (예: v0.1.0, latest): " IMAGE_TAG

# 이미지 빌드 및 푸시
FULL_REPO="$DOCKER_USERNAME/$REPO_NAME"

if [ "$SERVICE_CHOICE" = "1" ] || [ "$SERVICE_CHOICE" = "3" ]; then
    echo ""
    echo "📦 FastAPI 이미지 빌드 중..."
    docker build -t "$FULL_REPO:app-$IMAGE_TAG" -f Dockerfile .
    echo "⬆️  FastAPI 이미지 푸시 중..."
    docker push "$FULL_REPO:app-$IMAGE_TAG"
    echo "✅ FastAPI 이미지 푸시 완료: $FULL_REPO:app-$IMAGE_TAG"
fi

if [ "$SERVICE_CHOICE" = "2" ] || [ "$SERVICE_CHOICE" = "3" ]; then
    echo ""
    echo "📦 AI Worker 이미지 빌드 중..."
    docker build -t "$FULL_REPO:worker-$IMAGE_TAG" -f Dockerfile.worker .
    echo "⬆️  AI Worker 이미지 푸시 중..."
    docker push "$FULL_REPO:worker-$IMAGE_TAG"
    echo "✅ AI Worker 이미지 푸시 완료: $FULL_REPO:worker-$IMAGE_TAG"
fi

# ── 3. EC2 배포 ──
echo ""
echo "──── EC2 배포 설정 ────"
read -rp "SSH 키 파일명 (~/.ssh/ 기준): " SSH_KEY
read -rp "EC2 IP 주소: " EC2_IP
EC2_USER="${EC2_USER:-ubuntu}"

SSH_CMD="ssh -i ~/.ssh/$SSH_KEY -o StrictHostKeyChecking=no $EC2_USER@$EC2_IP"

# HTTPS 여부
read -rp "HTTPS 사용 여부 (y/n): " USE_HTTPS
if [ "$USE_HTTPS" = "y" ]; then
    read -rp "도메인 주소: " DOMAIN_NAME
fi

echo ""
echo "🚀 EC2에 배포 중..."

$SSH_CMD << DEPLOY_SCRIPT
    set -e

    echo "📥 Docker Hub 로그인..."
    echo "$DOCKER_PAT" | docker login --username "$DOCKER_USERNAME" --password-stdin

    # 프로젝트 디렉토리 이동 (없으면 생성)
    mkdir -p ~/healthguide && cd ~/healthguide

    # docker-compose.yml이 없으면 다운로드 (또는 git pull)
    if [ ! -f docker-compose.yml ]; then
        echo "⚠️  docker-compose.yml이 없습니다. git clone을 먼저 해주세요."
        exit 1
    fi

    echo "📥 최신 이미지 풀..."
    docker compose pull

    echo "🔄 컨테이너 재시작..."
    docker compose up -d --remove-orphans

    echo "🧹 미사용 이미지 정리..."
    docker image prune -f

    echo "⏰ Docker prune cron 등록 (매주 일요일 새벽 3시)..."
    CRON_JOB="0 3 * * 0 docker container prune -f && docker image prune -f && docker builder prune -f && docker network prune -f >> /var/log/docker-prune.log 2>&1"
    ( crontab -l 2>/dev/null | grep -v 'docker.*prune'; echo "$CRON_JOB" ) | crontab -
    echo "✅ cron 등록 완료"

    echo "✅ 배포 완료!"
    docker compose ps
DEPLOY_SCRIPT

echo ""
echo "========================================"
echo "✅ 배포가 완료되었습니다!"
echo "========================================"