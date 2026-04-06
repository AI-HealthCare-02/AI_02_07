"""common_code.py 라우터 테스트 — 공통코드 조회."""

import pytest
from starlette import status


@pytest.mark.asyncio
class TestCommonCode:
    async def test_list_group_codes(self, client):
        response = await client.get("/api/v1/codes/groups")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_get_codes_by_group(self, client):
        response = await client.get("/api/v1/codes/GENDER")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_get_codes_nonexistent_group(self, client):
        """존재하지 않는 그룹도 빈 리스트 반환 (에러 아님)."""
        response = await client.get("/api/v1/codes/NONEXISTENT")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == []
