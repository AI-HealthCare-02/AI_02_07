# app/services/kakao_notification.py
"""
카카오 알림톡 클라이언트
- 카카오 비즈메시지 API (https://business.kakao.com/info/bizmessage/) 사용
- 알림톡 발송 전 필수 준비사항:
    1) 카카오 비즈니스 채널 생성 및 검수 완료
    2) 알림톡 템플릿 생성 및 검수 완료 → TEMPLATE_ID 발급
    3) 사업자 번호 등록 및 발신 프로필 키(SENDER_KEY) 발급

환경변수 (.local.env):
  KAKAO_ALIMTALK_SENDER_KEY=<발신프로필키>
  KAKAO_ALIMTALK_TEMPLATE_ID_REMINDER=<복약알림 템플릿ID>

※ 카카오 알림톡 API는 직접 호출 방식과 솔루션사(예: 솔라피, NHN Cloud) 경유 방식이 있습니다.
   여기서는 솔라피(Solapi) REST API 기준으로 작성했습니다.
   다른 솔루션사 사용 시 _call_api() 부분만 교체하면 됩니다.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 솔라피 API 엔드포인트
# 다른 솔루션사 사용 시 이 값을 교체하세요.
# ──────────────────────────────────────────
SOLAPI_BASE_URL = "https://api.solapi.com/messages/v4/send"


class KakaoAlimtalkClient:
    """
    카카오 알림톡 발송 클라이언트 (솔라피 경유).

    솔라피 API 키는 settings에 추가 필요:
      KAKAO_API_KEY      : 솔라피 API Key
      KAKAO_API_SECRET   : 솔라피 API Secret
      KAKAO_SENDER_KEY   : 카카오 채널 발신 프로필 키
      KAKAO_CHANNEL_ID   : 카카오 채널 ID (@ 포함)
    """

    def __init__(self) -> None:
        self._api_key: str = getattr(settings, "KAKAO_API_KEY", "")
        self._api_secret: str = getattr(settings, "KAKAO_API_SECRET", "")
        self._sender_key: str = getattr(settings, "KAKAO_SENDER_KEY", "")
        self._channel_id: str = getattr(settings, "KAKAO_CHANNEL_ID", "")

    # ──────────────────────────────────────────
    # 공개 메서드: 복약 알림
    # ──────────────────────────────────────────
    async def send_medication_reminder(
        self,
        to: str,
        guide_title: str,
        reminder_time: str,
    ) -> bool:
        """
        복약 알림톡 발송.

        템플릿 변수 (검수 완료된 템플릿과 변수명 일치시킬 것):
          #{가이드명}   : guide_title
          #{알림시간}   : reminder_time (HH:MM)

        Args:
            to:             수신자 전화번호 (01012345678 형식, 하이픈 없이)
            guide_title:    가이드 제목
            reminder_time:  알림 시간 문자열 (예: "09:00")

        Returns:
            True if 발송 성공, False otherwise
        """
        template_id = getattr(settings, "KAKAO_TEMPLATE_ID_REMINDER", "")
        if not template_id:
            logger.warning("KAKAO_TEMPLATE_ID_REMINDER 설정이 없습니다.")
            return False

        # 템플릿 변수 치환
        variables = {
            "#{가이드명}": guide_title,
            "#{알림시간}": reminder_time,
        }

        return await self._send(to=to, template_id=template_id, variables=variables)

    # ──────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────
    async def _send(
        self,
        to: str,
        template_id: str,
        variables: dict[str, str],
    ) -> bool:
        """솔라피 API를 통한 알림톡 발송."""
        if not self._api_key or not self._sender_key:
            logger.error("카카오 알림톡 설정 누락 — KAKAO_API_KEY 또는 KAKAO_SENDER_KEY가 비어있습니다.")
            return False

        headers = self._build_auth_headers()
        payload = {
            "message": {
                "to": to,
                "from": self._channel_id,
                "kakaoOptions": {
                    "pfId": self._sender_key,
                    "templateId": template_id,
                    "variables": variables,
                    "disableSms": False,  # 알림톡 실패 시 SMS 대체 발송
                },
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    SOLAPI_BASE_URL,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                # 솔라피는 groupId 반환 시 성공
                if data.get("groupId"):
                    logger.info(
                        "알림톡 발송 성공 [to=%s, template=%s, groupId=%s]",
                        to,
                        template_id,
                        data["groupId"],
                    )
                    return True
                else:
                    logger.warning("알림톡 발송 응답 이상: %s", data)
                    return False

        except httpx.HTTPStatusError as e:
            logger.error(
                "알림톡 HTTP 오류 [%s]: %s — %s",
                to,
                e.response.status_code,
                e.response.text,
            )
        except httpx.HTTPError as e:
            logger.error("알림톡 네트워크 오류 [%s]: %s", to, e)

        return False

    def _build_auth_headers(self) -> dict[str, str]:
        """
        솔라피 HMAC-SHA256 인증 헤더 생성.
        https://developers.solapi.com/references/auth
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salt = uuid.uuid4().hex
        data_to_sign = f"date={date_str}&salt={salt}"

        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            data_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "Authorization": (
                f"HMAC-SHA256 apiKey={self._api_key}, date={date_str}, salt={salt}, signature={signature}"
            ),
            "Content-Type": "application/json",
        }
