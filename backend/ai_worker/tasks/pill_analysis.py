# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — 안은지 담당
#
# 이 파일에 알약 이미지 분석 로직을 구현하세요.
# S3에서 이미지 다운로드 → 모델 추론 → 결과 반환
# ──────────────────────────────────────────────

from ai_worker.core.logger import setup_logger

logger = setup_logger("task.pill_analysis")
