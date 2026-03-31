# ai_worker/tasks/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 작업 핸들러 — 이승원 담당
#
# 이 파일에 vLLM 기반 의료 문서 분석 로직을 구현하세요.
# S3에서 문서를 다운로드 → vLLM 추론 → 결과 반환
# ──────────────────────────────────────────────

from typing import Any

from ai_worker.core.logger import setup_logger
from ai_worker.core.s3_client import download_file_from_s3
from ai_worker.tasks import register_task

logger = setup_logger("task.medical_doc")
