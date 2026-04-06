# app/apis/v1/s3_test.py
# 개발 환경에서만 사용하는 S3 연동 테스트 엔드포인트

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.s3 import (
    delete_file,
    generate_presigned_url,
    generate_s3_key,
    upload_file,
)

router = APIRouter(prefix="/s3-test", tags=["S3 Test"])


@router.post("/upload")
async def test_upload(file: UploadFile = File(...)):
    """S3 업로드 테스트"""
    settings = get_settings()
    if settings.APP_ENV == "production":
        raise HTTPException(403, "운영 환경에서는 사용 불가")

    s3_key = generate_s3_key("test-uploads", file.filename, user_id=0)
    await upload_file(file.file, s3_key, file.content_type or "application/octet-stream")

    download_url = generate_presigned_url(s3_key)

    return {
        "s3_key": s3_key,
        "download_url": download_url,
        "file_name": file.filename,
        "content_type": file.content_type,
    }


@router.delete("/delete")
async def test_delete(s3_key: str):
    """S3 삭제 테스트"""
    settings = get_settings()
    if settings.APP_ENV == "production":
        raise HTTPException(403, "운영 환경에서는 사용 불가")

    success = await delete_file(s3_key)
    return {"deleted": success, "s3_key": s3_key}
