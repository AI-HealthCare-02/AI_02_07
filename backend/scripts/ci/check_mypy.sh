# set -eo pipefail

# COLOR_GREEN=$(tput setaf 2)
# COLOR_BLUE=$(tput setaf 4)
# COLOR_RED=$(tput setaf 1)
# COLOR_NC=$(tput sgr0)

# cd "$(dirname "$0")/../.."

# echo "${COLOR_BLUE}Run Mypy${COLOR_NC}"
# if ! uv run mypy . ; then
#   echo ""
#   echo "${COLOR_RED}✖ Mypy found issues.${COLOR_NC}"
#   echo "${COLOR_RED}→ Please fix the issues above manually and re-run the command.${COLOR_NC}"
#   exit 1
# fi

# echo "${COLOR_GREEN}Successfully Ended.${COLOR_NC}"

#!/usr/bin/env bash
# scripts/ci/check_mypy.sh
# ──────────────────────────────────────────────
# Mypy 정적 타입 검사 실행 스크립트
# ──────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."

echo "========================================"
echo "🔎 HealthGuide Mypy 타입 검사"
echo "========================================"

echo "📦 의존성 동기화..."
uv sync --group dev --group app

echo ""
echo "🔬 Mypy 실행 중..."
uv run mypy app/ ai_worker/ --ignore-missing-imports "$@"

echo ""
echo "✅ Mypy 타입 검사 통과!"