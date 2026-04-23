"""
알약 분석 API 테스트

테스트 범위:
  1. 이미지 전처리 (리사이즈, JPEG 변환, Base64 인코딩)
  2. 이미지 유효성 검사 (용량, 포맷)
  3. POST /pill-analysis/analyze  — 분석 요청
  4. GET  /pill-analysis           — 목록 조회 (검색 포함)
  5. GET  /pill-analysis/{id}      — 상세 조회
  6. DELETE /pill-analysis/{id}    — 삭제
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from starlette import status


# ── 테스트용 이미지 생성 헬퍼 ─────────────────────────────────


def make_image_bytes(width: int = 800, height: int = 600, fmt: str = "JPEG") -> bytes:
    """테스트용 더미 이미지 바이트 생성."""
    img = Image.new("RGB", (width, height), color=(200, 150, 100))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_upload_file(data: bytes, filename: str = "pill.jpg", content_type: str = "image/jpeg"):
    """httpx multipart 업로드용 튜플 반환."""
    return (filename, data, content_type)


# ── 이미지 전처리 단위 테스트 ─────────────────────────────────


class TestPreprocessImage:
    def test_resize_large_image(self):
        """2000px 이미지가 1024px 이하로 리사이즈되는지 확인."""
        from ai_worker.tasks.pill_analysis import preprocess_image
        import base64

        img_bytes = make_image_bytes(2000, 1500)
        b64 = preprocess_image(img_bytes)
        decoded = base64.b64decode(b64)
        result_img = Image.open(io.BytesIO(decoded))

        assert max(result_img.size) <= 1024

    def test_small_image_not_upscaled(self):
        """작은 이미지(500px)는 확대되지 않는지 확인."""
        from ai_worker.tasks.pill_analysis import preprocess_image
        import base64

        img_bytes = make_image_bytes(500, 400)
        b64 = preprocess_image(img_bytes)
        decoded = base64.b64decode(b64)
        result_img = Image.open(io.BytesIO(decoded))

        assert result_img.size == (500, 400)

    def test_output_is_jpeg(self):
        """출력 포맷이 JPEG인지 확인."""
        from ai_worker.tasks.pill_analysis import preprocess_image
        import base64

        img_bytes = make_image_bytes(800, 600, fmt="PNG")
        b64 = preprocess_image(img_bytes)
        decoded = base64.b64decode(b64)
        result_img = Image.open(io.BytesIO(decoded))

        assert result_img.format == "JPEG"

    def test_aspect_ratio_preserved(self):
        """리사이즈 후 비율이 유지되는지 확인."""
        from ai_worker.tasks.pill_analysis import preprocess_image
        import base64

        img_bytes = make_image_bytes(2000, 1000)  # 2:1 비율
        b64 = preprocess_image(img_bytes)
        decoded = base64.b64decode(b64)
        result_img = Image.open(io.BytesIO(decoded))

        w, h = result_img.size
        assert abs(w / h - 2.0) < 0.01  # 2:1 비율 유지

    def test_exceeds_5mb_raises_error(self):
        """5MB 초과 이미지는 ValueError 발생."""
        from ai_worker.tasks.pill_analysis import preprocess_image

        large_bytes = b"x" * (5 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="5MB"):
            preprocess_image(large_bytes)

    def test_returns_valid_base64(self):
        """반환값이 유효한 Base64 문자열인지 확인."""
        from ai_worker.tasks.pill_analysis import preprocess_image
        import base64

        img_bytes = make_image_bytes(800, 600)
        b64 = preprocess_image(img_bytes)

        # Base64 디코딩 가능한지 확인
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0


# ── API 테스트 ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestPillAnalyzeEndpoint:
    """POST /api/v1/pill-analysis/analyze"""

    async def test_analyze_success(self, client, test_user, auth_headers):
        """정상 이미지 2장 업로드 시 분석 성공."""
        mock_task_result = {
            "status": "completed",
            "result": {
                "analysis_id": 1,
                "product_name": "타이레놀정500mg",
                "efficacy": "해열, 진통",
                "gpt_model_version": "gpt-4o-mini",
            },
        }

        with (
            patch("app.apis.v1.pill_analysis.upload_file", new_callable=AsyncMock),
            patch("app.apis.v1.pill_analysis.enqueue_task", new_callable=AsyncMock, return_value="task:abc123"),
            patch(
                "app.apis.v1.pill_analysis.wait_for_task_result", new_callable=AsyncMock, return_value=mock_task_result
            ),
            patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user),
        ):
            front = make_image_bytes(800, 600)
            back = make_image_bytes(800, 600)

            response = await client.post(
                "/api/v1/pill-analysis/analyze",
                files={
                    "front_image": make_upload_file(front, "front.jpg"),
                    "back_image": make_upload_file(back, "back.jpg"),
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["product_name"] == "타이레놀정500mg"

    async def test_analyze_invalid_format(self, client, test_user, auth_headers):
        """지원하지 않는 포맷(PDF) 업로드 시 400."""
        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.post(
                "/api/v1/pill-analysis/analyze",
                files={
                    "front_image": ("front.pdf", b"fake pdf", "application/pdf"),
                    "back_image": ("back.pdf", b"fake pdf", "application/pdf"),
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_analyze_exceeds_size(self, client, test_user, auth_headers):
        """5MB 초과 이미지 업로드 시 400."""
        large_data = b"x" * (5 * 1024 * 1024 + 1)

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.post(
                "/api/v1/pill-analysis/analyze",
                files={
                    "front_image": make_upload_file(large_data, "front.jpg"),
                    "back_image": make_upload_file(make_image_bytes(), "back.jpg"),
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_analyze_worker_failure(self, client, test_user, auth_headers):
        """워커 실패 시 500 반환."""
        with (
            patch("app.apis.v1.pill_analysis.upload_file", new_callable=AsyncMock),
            patch("app.apis.v1.pill_analysis.enqueue_task", new_callable=AsyncMock, return_value="task:fail"),
            patch(
                "app.apis.v1.pill_analysis.wait_for_task_result",
                new_callable=AsyncMock,
                return_value={"status": "failed"},
            ),
            patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user),
        ):
            front = make_image_bytes()
            back = make_image_bytes()

            response = await client.post(
                "/api/v1/pill-analysis/analyze",
                files={
                    "front_image": make_upload_file(front),
                    "back_image": make_upload_file(back),
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_analyze_unauthorized(self, client):
        """인증 없이 요청 시 401."""
        front = make_image_bytes()
        back = make_image_bytes()

        response = await client.post(
            "/api/v1/pill-analysis/analyze",
            files={
                "front_image": make_upload_file(front),
                "back_image": make_upload_file(back),
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
class TestPillAnalysisListEndpoint:
    """GET /api/v1/pill-analysis"""

    async def _create_history(self, user_id: int, product_name: str = "테스트약") -> int:
        """테스트용 분석 이력 직접 DB 삽입."""
        from tortoise import Tortoise

        conn = Tortoise.get_connection("default")

        # uploaded_file 먼저 생성
        file_rows = await conn.execute_query_dict(
            """
            INSERT INTO uploaded_file (
                user_id, original_name, stored_name, s3_bucket, s3_key, s3_url,
                content_type, file_size, file_extension,
                file_category_grp, file_category_code
            ) VALUES ($1,'test.jpg','test.jpg','bucket','key','http://url',
                      'image/jpeg',1024,'.jpg','FILE_CATEGORY','PILL_IMG')
            RETURNING file_id
            """,
            [user_id],
        )
        file_id = file_rows[0]["file_id"]

        rows = await conn.execute_query_dict(
            """
            INSERT INTO pill_analysis_history (user_id, file_id, product_name, efficacy)
            VALUES ($1, $2, $3, '해열 진통')
            RETURNING analysis_id
            """,
            [user_id, file_id, product_name],
        )
        return rows[0]["analysis_id"]

    async def test_list_success(self, client, test_user, auth_headers):
        """목록 조회 성공."""
        await self._create_history(test_user.user_id, "타이레놀")

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get("/api/v1/pill-analysis", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) >= 1

    async def test_list_search(self, client, test_user, auth_headers):
        """제품명 검색 필터 동작 확인."""
        await self._create_history(test_user.user_id, "아스피린")
        await self._create_history(test_user.user_id, "이부프로펜")

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get(
                "/api/v1/pill-analysis?search=아스피린",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all("아스피린" in row["product_name"] for row in data["data"])

    async def test_list_pagination(self, client, test_user, auth_headers):
        """페이지네이션 동작 확인."""
        for i in range(5):
            await self._create_history(test_user.user_id, f"약품{i}")

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get(
                "/api/v1/pill-analysis?page=1&size=2",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) <= 2
        assert data["pagination"]["size"] == 2

    async def test_list_unauthorized(self, client):
        """인증 없이 목록 조회 시 401."""
        response = await client.get("/api/v1/pill-analysis")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
class TestPillAnalysisDetailEndpoint:
    """GET /api/v1/pill-analysis/{id}"""

    async def _create_history(self, user_id: int) -> int:
        from tortoise import Tortoise

        conn = Tortoise.get_connection("default")
        file_rows = await conn.execute_query_dict(
            """
            INSERT INTO uploaded_file (
                user_id, original_name, stored_name, s3_bucket, s3_key, s3_url,
                content_type, file_size, file_extension,
                file_category_grp, file_category_code
            ) VALUES ($1,'t.jpg','t.jpg','b','k','http://u','image/jpeg',1,'.jpg','FILE_CATEGORY','PILL_IMG')
            RETURNING file_id
            """,
            [user_id],
        )
        file_id = file_rows[0]["file_id"]
        rows = await conn.execute_query_dict(
            """
            INSERT INTO pill_analysis_history (user_id, file_id, product_name, caution)
            VALUES ($1, $2, '타이레놀', '간 손상 주의')
            RETURNING analysis_id
            """,
            [user_id, file_id],
        )
        return rows[0]["analysis_id"]

    async def test_detail_success(self, client, test_user, auth_headers):
        """상세 조회 성공."""
        analysis_id = await self._create_history(test_user.user_id)

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get(
                f"/api/v1/pill-analysis/{analysis_id}",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["analysis_id"] == analysis_id
        assert data["data"]["product_name"] == "타이레놀"
        assert data["data"]["caution"] == "간 손상 주의"

    async def test_detail_not_found(self, client, test_user, auth_headers):
        """존재하지 않는 ID 조회 시 404."""
        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get(
                "/api/v1/pill-analysis/999999",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_detail_other_user_forbidden(self, client, test_user, auth_headers):
        """다른 사용자의 분석 결과 조회 시 404 (소유권 보호)."""
        from app.models.user import User

        other_user = await User.create(
            email="other_pill@healthguide.dev",
            password=None,
            nickname="다른유저",
            name="다른",
            provider_code="LOCAL",
        )
        analysis_id = await self._create_history(other_user.user_id)

        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.get(
                f"/api/v1/pill-analysis/{analysis_id}",
                headers=auth_headers,
            )

        await other_user.delete()
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestPillAnalysisDeleteEndpoint:
    """DELETE /api/v1/pill-analysis/{id}"""

    async def _create_history(self, user_id: int) -> tuple[int, int]:
        from tortoise import Tortoise

        conn = Tortoise.get_connection("default")
        file_rows = await conn.execute_query_dict(
            """
            INSERT INTO uploaded_file (
                user_id, original_name, stored_name, s3_bucket, s3_key, s3_url,
                content_type, file_size, file_extension,
                file_category_grp, file_category_code
            ) VALUES ($1,'d.jpg','d.jpg','b','pill/del.jpg','http://u','image/jpeg',1,'.jpg','FILE_CATEGORY','PILL_IMG')
            RETURNING file_id
            """,
            [user_id],
        )
        file_id = file_rows[0]["file_id"]
        rows = await conn.execute_query_dict(
            "INSERT INTO pill_analysis_history (user_id, file_id, product_name) VALUES ($1,$2,'삭제테스트약') RETURNING analysis_id",
            [user_id, file_id],
        )
        return rows[0]["analysis_id"], file_id

    async def test_delete_success(self, client, test_user, auth_headers):
        """삭제 성공 후 재조회 시 404."""
        analysis_id, _ = await self._create_history(test_user.user_id)

        with (
            patch("app.apis.v1.pill_analysis.delete_file", new_callable=AsyncMock, return_value=True),
            patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user),
        ):
            response = await client.delete(
                f"/api/v1/pill-analysis/{analysis_id}",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

        # 재조회 시 404
        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            check = await client.get(
                f"/api/v1/pill-analysis/{analysis_id}",
                headers=auth_headers,
            )
        assert check.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_not_found(self, client, test_user, auth_headers):
        """존재하지 않는 ID 삭제 시 404."""
        with patch("app.apis.v1.pill_analysis.get_current_user", return_value=test_user):
            response = await client.delete(
                "/api/v1/pill-analysis/999999",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_unauthorized(self, client):
        """인증 없이 삭제 시 401."""
        response = await client.delete("/api/v1/pill-analysis/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
