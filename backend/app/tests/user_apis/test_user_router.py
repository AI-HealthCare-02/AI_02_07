"""user.py 라우터 테스트 — 프로필, 생활습관, 알레르기, 기저질환."""
import pytest
from starlette import status


@pytest.mark.asyncio
class TestUserProfile:
    async def test_get_me(self, client, auth_headers):
        response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == "test_router@healthguide.dev"

    async def test_get_me_unauthorized(self, client):
        response = await client.get("/api/v1/users/me")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_update_me(self, client, auth_headers):
        response = await client.patch(
            "/api/v1/users/me",
            json={"nickname": "수정닉네임"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["nickname"] == "수정닉네임"

    async def test_update_agreements(self, client, auth_headers):
        response = await client.patch(
            "/api/v1/users/me/agreements",
            json={"agreed_personal_info": True},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["agreed_personal_info"] is not None

    async def test_delete_me_wrong_confirm(self, client, auth_headers):
        response = await client.delete(
            "/api/v1/users/me",
            headers=auth_headers,
            content='{"confirm_text": "잘못된문구"}',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
class TestHealthProfile:
    async def test_get_health_profile(self, client, auth_headers):
        response = await client.get("/api/v1/users/me/health-profile", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert "profile" in data
        assert "lifestyle" in data
        assert "allergies" in data
        assert "diseases" in data


@pytest.mark.asyncio
class TestLifestyle:
    async def test_get_lifestyle_empty(self, client, auth_headers):
        response = await client.get("/api/v1/users/me/lifestyle", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] is None

    async def test_put_lifestyle(self, client, auth_headers):
        response = await client.put(
            "/api/v1/users/me/lifestyle",
            json={"height": "175.5", "weight": "70.0"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["height"] is not None


@pytest.mark.asyncio
class TestAllergies:
    async def test_list_allergies_empty(self, client, auth_headers):
        response = await client.get("/api/v1/users/me/allergies", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == []

    async def test_create_allergy(self, client, auth_headers):
        response = await client.post(
            "/api/v1/users/me/allergies",
            json={"allergy_name": "땅콩"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["allergy_name"] == "땅콩"

    async def test_create_duplicate_allergy(self, client, auth_headers):
        await client.post(
            "/api/v1/users/me/allergies",
            json={"allergy_name": "우유_dup"},
            headers=auth_headers,
        )
        response = await client.post(
            "/api/v1/users/me/allergies",
            json={"allergy_name": "우유_dup"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_bulk_create_allergies(self, client, auth_headers):
        response = await client.post(
            "/api/v1/users/me/allergies/bulk",
            json={"allergy_names": ["갑각류", "복숭아"]},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.json()["data"]) == 2

    async def test_delete_all_allergies(self, client, auth_headers):
        response = await client.delete("/api/v1/users/me/allergies", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
class TestDiseases:
    async def test_list_diseases_empty(self, client, auth_headers):
        response = await client.get("/api/v1/users/me/diseases", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == []

    async def test_create_disease(self, client, auth_headers):
        response = await client.post(
            "/api/v1/users/me/diseases",
            json={"disease_name": "고혈압"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["disease_name"] == "고혈압"

    async def test_bulk_create_diseases(self, client, auth_headers):
        response = await client.post(
            "/api/v1/users/me/diseases/bulk",
            json={"disease_names": ["당뇨", "천식"]},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.json()["data"]) == 2

    async def test_delete_all_diseases(self, client, auth_headers):
        response = await client.delete("/api/v1/users/me/diseases", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
