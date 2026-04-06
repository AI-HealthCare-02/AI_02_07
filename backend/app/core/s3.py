# ===========================================================
# app/core/s3.py
# AWS S3 파일 업로드 / 다운로드 / Presigned URL / 삭제
#
# 사용법:
#   from app.core.s3 import upload_file, generate_presigned_url, delete_file
#
#   # 업로드
#   s3_key = generate_s3_key("medical-docs", "처방전.pdf", user_id=1)
#   url = await upload_file(file.file, s3_key, file.content_type)
#
#   # 다운로드 URL (1시간 유효)
#   url = generate_presigned_url(s3_key)
#
#   # 삭제
#   await delete_file(s3_key)
# ===========================================================

import logging
import uuid
from datetime import datetime
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# S3 클라이언트 (싱글턴)
# ─────────────────────────────────────────────
_s3_client = None


def get_s3_client():
    """
    boto3 S3 클라이언트를 반환합니다.
    최초 호출 시 한 번만 생성하고 이후 재사용합니다.
    """
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        logger.info(
            "[S3] 클라이언트 초기화 완료 (region=%s, bucket=%s)",
            settings.AWS_REGION,
            settings.AWS_S3_BUCKET_NAME,
        )
    return _s3_client


# ─────────────────────────────────────────────
# S3 키 생성
# ─────────────────────────────────────────────
def generate_s3_key(
    folder: str,
    filename: str,
    user_id: int | None = None,
) -> str:
    """
    S3 에 저장할 고유 키를 생성합니다.

    Parameters
    ----------
    folder : str
        S3 폴더명 (예: 'medical-docs', 'pill-images', 'guides')
    filename : str
        원본 파일명 (확장자 추출용)
    user_id : int, optional
        사용자 ID (경로에 포함하여 사용자별 분리)

    Returns
    -------
    str
        예: 'medical-docs/user_1/20260331/a1b2c3d4.pdf'

    사용 예시
    --------
        key = generate_s3_key("medical-docs", "처방전.pdf", user_id=1)
    """
    # 확장자 추출
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    # 날짜별 분류
    date_prefix = datetime.now().strftime("%Y%m%d")

    # 고유 파일명 (UUID)
    unique_name = uuid.uuid4().hex[:16]

    # 경로 구성
    if user_id:
        return f"{folder}/user_{user_id}/{date_prefix}/{unique_name}{ext}"
    else:
        return f"{folder}/{date_prefix}/{unique_name}{ext}"


# ─────────────────────────────────────────────
# 파일 업로드
# ─────────────────────────────────────────────
async def upload_file(
    file_obj: BinaryIO,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    파일을 S3에 업로드하고 S3 키를 반환합니다.

    Parameters
    ----------
    file_obj : BinaryIO
        업로드할 파일 객체 (UploadFile.file)
    s3_key : str
        S3 저장 경로 (generate_s3_key 로 생성)
    content_type : str
        파일의 MIME 타입

    Returns
    -------
    str
        업로드된 S3 키

    Raises
    ------
    Exception
        업로드 실패 시

    사용 예시
    --------
        from fastapi import UploadFile

        async def upload_document(file: UploadFile, user_id: int):
            s3_key = generate_s3_key("medical-docs", file.filename, user_id)
            await upload_file(file.file, s3_key, file.content_type)
            return s3_key
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        client.upload_fileobj(
            file_obj,
            settings.AWS_S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("[S3] 업로드 완료: %s", s3_key)
        return s3_key
    except ClientError as e:
        logger.error("[S3] 업로드 실패: %s — %s", s3_key, e)
        raise


# ─────────────────────────────────────────────
# Presigned URL 생성 (다운로드/조회용)
# ─────────────────────────────────────────────
def generate_presigned_url(
    s3_key: str,
    expiration: int = 3600,
) -> str | None:
    """
    S3 객체에 대한 임시 접근 URL을 생성합니다.

    Parameters
    ----------
    s3_key : str
        S3 파일 경로
    expiration : int
        URL 유효 시간 (초, 기본 3600 = 1시간)

    Returns
    -------
    str or None
        Presigned URL (실패 시 None)

    사용 예시
    --------
        url = generate_presigned_url("medical-docs/user_1/20260331/abc.pdf")
        # → https://ah-02-07-healthguide.s3.ap-northeast-2.amazonaws.com/...
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_S3_BUCKET_NAME,
                "Key": s3_key,
            },
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error("[S3] Presigned URL 생성 실패: %s — %s", s3_key, e)
        return None


# ─────────────────────────────────────────────
# Presigned URL 생성 (업로드용 — 프론트엔드 직접 업로드)
# ─────────────────────────────────────────────
def generate_presigned_upload_url(
    s3_key: str,
    content_type: str = "application/octet-stream",
    expiration: int = 3600,
) -> dict | None:
    """
    프론트엔드에서 S3로 직접 업로드할 수 있는 Presigned URL을 생성합니다.

    Returns
    -------
    dict or None
        {'url': 'https://...', 'fields': {...}} 형태
        프론트엔드에서 이 url 로 multipart/form-data POST 요청

    사용 예시
    --------
        info = generate_presigned_upload_url(
            "pill-images/user_1/20260331/abc.jpg",
            content_type="image/jpeg"
        )
        # 프론트에서: POST info['url'] with info['fields'] + file
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        response = client.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, 50 * 1024 * 1024],  # 최대 50MB
            ],
            ExpiresIn=expiration,
        )
        return response
    except ClientError as e:
        logger.error("[S3] Presigned Upload URL 생성 실패: %s — %s", s3_key, e)
        return None


# ─────────────────────────────────────────────
# 파일 삭제
# ─────────────────────────────────────────────
async def delete_file(s3_key: str) -> bool:
    """
    S3에서 파일을 삭제합니다.

    Returns
    -------
    bool
        삭제 성공 여부
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        client.delete_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
        )
        logger.info("[S3] 삭제 완료: %s", s3_key)
        return True
    except ClientError as e:
        logger.error("[S3] 삭제 실패: %s — %s", s3_key, e)
        return False


# ─────────────────────────────────────────────
# 파일 존재 확인
# ─────────────────────────────────────────────
async def file_exists(s3_key: str) -> bool:
    """
    S3에 해당 키의 파일이 존재하는지 확인합니다.
    """
    settings = get_settings()
    client = get_s3_client()

    try:
        client.head_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
        )
        return True
    except ClientError:
        return False
