# set -eo pipefail

# COLOR_GREEN=$(tput setaf 2)
# COLOR_BLUE=$(tput setaf 4)
# COLOR_RED=$(tput setaf 1)
# COLOR_NC=$(tput sgr0)

# cd "$(dirname "$0")/../.."

# echo "${COLOR_BLUE}Start Ruff Auto Fix${COLOR_NC}"
# uv run ruff check . --fix || true
# echo "${COLOR_GREEN}Auto-fix Done${COLOR_NC}"

# echo "${COLOR_BLUE}Check remaining issues${COLOR_NC}"
# if ! uv run ruff check .; then
#   echo ""
#   echo "${COLOR_RED}✖ Ruff found issues that could NOT be auto-fixed.${COLOR_NC}"
#   echo "${COLOR_RED}→ Please fix the issues above manually and re-run the command.${COLOR_NC}"
#   exit 1
# fi

# echo "${COLOR_BLUE}Start Formatting${COLOR_NC}"
# uv run ruff format .

# echo "${COLOR_GREEN}Code formatting successfully!${COLOR_NC}"
#!/usr/bin/env bash
# scripts/ci/code_formatting.sh
# ──────────────────────────────────────────────
# Ruff 린터 + 포매터 실행 스크립트
# --check 모드로 CI에서 검증, --fix로 자동 수정
# ──────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."

echo "========================================"
echo "🎨 HealthGuide 코드 포맷팅 검사"
echo "========================================"

# 인자로 --fix가 넘어오면 자동 수정 모드
FIX_MODE="${1:-}"

if [ "$FIX_MODE" = "--fix" ]; then
    echo "🔧 자동 수정 모드 (ruff format + ruff check --fix)"
    echo ""

    echo "1️⃣  Ruff Format (자동 포맷팅)..."
    uv run ruff format app/ ai_worker/ tests/

    echo ""
    echo "2️⃣  Ruff Check + Fix (린트 자동 수정)..."
    uv run ruff check app/ ai_worker/ tests/ --fix

    echo ""
    echo "✅ 코드 포맷팅 및 린트 자동 수정 완료!"
else
    echo "🔍 검사 전용 모드 (수정하려면: $0 --fix)"
    echo ""

    echo "1️⃣  Ruff Format Check..."
    uv run ruff format --check app/ ai_worker/ tests/

    echo ""
    echo "2️⃣  Ruff Lint Check..."
    uv run ruff check app/ ai_worker/ tests/

    echo ""
    echo "✅ 코드 포맷팅 검사 통과!"
fi