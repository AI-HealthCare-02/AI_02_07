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
"""

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
    ) -> bool:
        """
        복약 알림을 카카오 나에게 보내기로 발송합니다.

        Args:
            kakao_access_token: 카카오 액세스 토큰 (users.kakao_access_token)
            guide_title: 가이드 제목 (예: "서울나우병원 복약 가이드")
            medication_names: 약물명 목록 (예: ["넥실렌정", "셈비트캡슐100mg"])
            reminder_time: 알림 시각 문자열 (예: "08:00")

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
                import json

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
                # 토큰 만료 — 갱신 시도 후 재발송
                logger.warning("[KakaoAlarm] 액세스 토큰 만료, 갱신 시도")
                return False  # 토큰 갱신은 수호 파트(auth_service) 담당이므로 False 반환

            else:
                logger.error(f"[KakaoAlarm] HTTP {response.status_code} — {response.text}")
                return False

        except httpx.TimeoutException:
            logger.error("[KakaoAlarm] 요청 타임아웃")
            return False
        except Exception as e:
            logger.error(f"[KakaoAlarm] 발송 실패: {e}")
            return False

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
