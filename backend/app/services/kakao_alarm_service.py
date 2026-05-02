"""
app/services/kakao_alarm_service.py
────────────────────────────────────
카카오 나에게 보내기 API 서비스

[동작 조건]
- 카카오 OAuth 로그인 사용자만 사용 가능 (provider_code == 'KAKAO')
- users 테이블의 kakao_access_token 컬럼 값이 있어야 함
- 수호가 auth_service.py 에서 카카오 로그인 시 토큰 DB 저장 담당

[카카오 나에게 보내기 API]
- 엔드포인트: POST https://kapi.kakao.com/v2/api/talk/memo/default/send
- 인증: 사용자 카카오 액세스 토큰 (Bearer)
- 비용: 무료 (알림톡과 다름 — 사업자 등록 불필요)
- 제한: 카카오 로그인 사용자 본인에게만 전송 가능

[토큰 갱신 전략]
- 액세스 토큰 유효기간: 6시간
- 401 응답 수신 시 kakao_refresh_token으로 자동 갱신 후 재발송
- 갱신된 토큰은 users 테이블에 즉시 저장
"""

import json
import logging

import httpx

logger = logging.getLogger(__name__)

# 카카오 나에게 보내기 API URL
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 카카오 토큰 갱신 URL
KAKAO_TOKEN_REFRESH_URL = "https://kauth.kakao.com/oauth/token"


class KakaoAlarmService:
    """카카오 나에게 보내기 알림 서비스."""

    async def send_medication_alarm(
        self,
        kakao_access_token: str,
        guide_title: str,
        medication_names: list[str],
        reminder_time: str,
        user_id: int | None = None,  # ✅ 추가: 토큰 만료 시 갱신에 필요
    ) -> bool:
        """
        복약 알림을 카카오 나에게 보내기로 발송합니다.

        Args:
            kakao_access_token: 카카오 액세스 토큰 (users.kakao_access_token)
            guide_title: 가이드 제목 (예: "서울나우병원 복약 가이드")
            medication_names: 약물명 목록 (예: ["넥실렌정", "셈비트캡슐100mg"])
            reminder_time: 알림 시각 문자열 (예: "08:00")
            user_id: 사용자 ID (토큰 만료 시 자동 갱신에 사용)

        Returns:
            bool: 발송 성공 여부
        """
        med_list = "\n".join(f"  · {name}" for name in medication_names)
        message_text = (
            f"💊 복약 알림 — {reminder_time}\n\n[{guide_title}]\n\n지금 드실 약:\n{med_list}\n\n건강한 하루 되세요 😊"
        )

        payload = {
            "template_object": {
                "object_type": "text",
                "text": message_text,
                "link": {
                    "web_url": "https://ai-02-07.vercel.app",
                    "mobile_web_url": "https://ai-02-07.vercel.app",
                },
            }
        }

        headers = {
            "Authorization": f"Bearer {kakao_access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 카카오 API는 JSON이 아닌 form 인코딩 방식으로 template_object를 전달
                form_data = {"template_object": json.dumps(payload["template_object"], ensure_ascii=False)}
                response = await client.post(KAKAO_MEMO_URL, headers=headers, data=form_data)

            if response.status_code == 200:
                result = response.json()
                if result.get("result_code") == 0:
                    logger.info(f"[KakaoAlarm] 발송 성공 — {guide_title} / {medication_names}")
                    return True
                else:
                    logger.warning(f"[KakaoAlarm] API 오류 — result_code={result.get('result_code')}, msg={result}")
                    return False

            elif response.status_code == 401:
                # ✅ 수정: 토큰 만료 시 refresh_token으로 자동 갱신 후 재발송
                logger.warning(f"[KakaoAlarm] 액세스 토큰 만료 — user_id={user_id}, 갱신 시도")
                if user_id is None:
                    logger.error("[KakaoAlarm] user_id 없음 — 토큰 갱신 불가")
                    return False

                new_token = await self._refresh_kakao_token(user_id)
                if new_token:
                    # 새 토큰으로 재발송 (user_id=None으로 무한루프 방지)
                    return await self.send_medication_alarm(
                        kakao_access_token=new_token,
                        guide_title=guide_title,
                        medication_names=medication_names,
                        reminder_time=reminder_time,
                        user_id=None,
                    )
                return False

            else:
                logger.error(f"[KakaoAlarm] HTTP {response.status_code} — {response.text}")
                return False

        except httpx.TimeoutException:
            logger.error("[KakaoAlarm] 요청 타임아웃")
            return False
        except Exception as e:
            logger.error(f"[KakaoAlarm] 발송 실패: {e}")
            return False

    async def _refresh_kakao_token(self, user_id: int) -> str | None:
        """
        ✅ 추가: kakao_refresh_token으로 새 access_token 발급 후 DB 저장.

        카카오 액세스 토큰 유효기간: 6시간
        리프레시 토큰 유효기간: 2개월 (1개월 미만 남으면 갱신 응답에 새 리프레시 토큰 포함)
        """
        try:
            from app.core.config import get_settings
            from app.models.user import User

            user = await User.get_or_none(user_id=user_id)
            if not user or not getattr(user, "kakao_refresh_token", None):
                logger.error(f"[KakaoAlarm] refresh_token 없음 — user_id={user_id}")
                return None

            settings = get_settings()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    KAKAO_TOKEN_REFRESH_URL,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": settings.OAUTH_KAKAO_CLIENT_ID,
                        "refresh_token": user.kakao_refresh_token,
                    },
                )

            if response.status_code != 200:
                logger.error(f"[KakaoAlarm] 토큰 갱신 실패 — HTTP {response.status_code}: {response.text}")
                return None

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")  # 1개월 미만 남은 경우만 포함

            if not new_access_token:
                logger.error(f"[KakaoAlarm] 갱신 응답에 access_token 없음 — {token_data}")
                return None

            # ✅ DB에 새 토큰 저장
            user.kakao_access_token = new_access_token
            if new_refresh_token:
                # 리프레시 토큰도 갱신된 경우 함께 저장
                user.kakao_refresh_token = new_refresh_token
                logger.info(f"[KakaoAlarm] 리프레시 토큰도 갱신됨 — user_id={user_id}")
            await user.save()

            logger.info(f"[KakaoAlarm] 토큰 갱신 성공 — user_id={user_id}")
            return new_access_token

        except Exception as e:
            logger.error(f"[KakaoAlarm] 토큰 갱신 오류 — user_id={user_id}: {e}")
            return None

    async def send_test_alarm(self, kakao_access_token: str) -> bool:
        """
        카카오 토큰 유효성 확인용 테스트 메시지 발송.
        관리자 페이지 또는 알림 등록 시 토큰 검증에 사용.
        """
        return await self.send_medication_alarm(
            kakao_access_token=kakao_access_token,
            guide_title="테스트",
            medication_names=["테스트 알림입니다"],
            reminder_time="--:--",
        )
