# ai_worker/core/s3_client.py
# ──────────────────────────────────────────────
# Worker 전용 S3 클라이언트
# 분석 대상 파일 다운로드용
# ──────────────────────────────────────────────

import io
from typing import BinaryIO

import boto3
from botocore.config import Config as BotoConfig

from ai_worker.core.config import get_worker_settings

_s3_client = None


def _get_s3_client():
    """S3 클라이언트 싱글턴."""
    global _s3_client
    if _s3_client is None:
        settings = get_worker_settings()
        _s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=BotoConfig(
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
    return _s3_client


def download_file_from_s3(s3_key: str) -> bytes:
    """
    S3에서 파일을 다운로드하여 bytes로 반환합니다.

    Args:
        s3_key: S3 오브젝트 키

    Returns:
        파일 내용 (bytes)

    사용 예시 (팀원용):
        file_bytes = download_file_from_s3("medical-docs/2026/03/30/report.pdf")
        # 이후 PyTorch 모델이나 vLLM에 전달
    """
    settings = get_worker_settings()
    client = _get_s3_client()

    buffer = io.BytesIO()
    client.download_fileobj(
        settings.AWS_S3_BUCKET_NAME,
        s3_key,
        buffer,
    )
    buffer.seek(0)
    return buffer.read()


def upload_result_to_s3(
    data: bytes, s3_key: str, content_type: str = "application/json"
) -> str:
    """
    Worker 처리 결과를 S3에 업로드합니다.
    예: 분석 결과 JSON, 변환된 이미지 등

    Returns:
        업로드된 S3 키
    """
    settings = get_worker_settings()
    client = _get_s3_client()

    buffer = io.BytesIO(data)
    client.upload_fileobj(
        buffer,
        settings.AWS_S3_BUCKET_NAME,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return s3_key
