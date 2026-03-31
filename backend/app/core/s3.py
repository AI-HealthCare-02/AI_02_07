# app/core/s3.py
# ──────────────────────────────────────────────
# AWS S3 클라이언트 유틸리티
# 파일 업로드 / 다운로드 / presigned URL 생성
# 팀원들은 이 모듈을 import해서 S3 관련 작업 수행
# ──────────────────────────────────────────────

import uuid
from datetime import datetime
from typing import BinaryIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings

# 모듈 레벨 S3 클라이언트 (lazy init)
_s3_client = None


def get_s3_client():
    """
    S3 클라이언트 싱글턴 반환.
    boto3 클라이언트는 스레드 세이프하므로 하나만 유지합니다.
    """
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        _s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
    return _s3_client


def generate_s3_key(
    folder: str,
    filename: str,
    user_id: int | str | None = None,
) -> str:
    """
    S3 오브젝트 키를 생성합니다.
    충돌 방지를 위해 UUID와 날짜 기반 경로를 사용합니다.

    Args:
        folder: 최상위 폴더 (예: "medical-docs", "pill-images", "guides")
        filename: 원본 파일명
        user_id: 사용자 ID (선택)

    Returns:
        예: "medical-docs/2026/03/30/user_42/a1b2c3d4_report.pdf"
    """
    now = datetime.utcnow()
    date_path = now.strftime("%Y/%m/%d")
    unique_prefix = uuid.uuid4().hex[:8]

    parts = [folder, date_path]
    if user_id is not None:
        parts.append(f"user_{user_id}")
    parts.append(f"{unique_prefix}_{filename}")

    return "/".join(parts)


async def upload_file(
    file: BinaryIO,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    파일을 S3에 업로드합니다.

    Args:
        file: 파일 객체 (read 가능)
        s3_key: S3 오브젝트 키
        content_type: MIME 타입

    Returns:
        업로드된 S3 오브젝트 키

    Raises:
        ClientError: S3 업로드 실패 시
    """
    settings = get_settings()
    client = get_s3_client()

    client.upload_fileobj(
        file,
        settings.AWS_S3_BUCKET_NAME,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return s3_key


async def generate_presigned_url(
    s3_key: str,
    expiration: int = 3600,
) -> str:
    """
    S3 오브젝트에 대한 프리사인드 URL을 생성합니다.
    프론트엔드에서 직접 다운로드할 수 있는 임시 URL.

    Args:
        s3_key: S3 오브젝트 키
        expiration: URL 유효 시간 (초, 기본 1시간)

    Returns:
        프리사인드 URL 문자열
    """
    settings = get_settings()
    client = get_s3_client()

    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_S3_BUCKET_NAME,
            "Key": s3_key,
        },
        ExpiresIn=expiration,
    )
    return url


async def delete_file(s3_key: str) -> bool:
    """
    S3 오브젝트를 삭제합니다.

    Returns:
        삭제 성공 여부
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        client.delete_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
        )
        return True
    except ClientError:
        return False
