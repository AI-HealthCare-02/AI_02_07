"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import apiClient from "@/lib/axios";

interface UserInfo {
  user_id: number;
  email: string;
  nickname: string;
  name: string;
  agreed_personal_info: string | null;
  agreed_sensitive_info: string | null;
  agreed_medical_data: string | null;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export default function AuthCallbackPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get("error");
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    if (error) {
      setErrorMessage(params.get("message") ?? "로그인에 실패했습니다.");
      setStatus("error");
      return;
    }

    if (!accessToken) {
      setErrorMessage("토큰을 받지 못했습니다.");
      setStatus("error");
      return;
    }

    const isNewUser = params.get("is_new_user") === "true";
    void isNewUser; // 동의 화면에서 통합 처리

    localStorage.setItem("access_token", accessToken);
    if (refreshToken) localStorage.setItem("refresh_token", refreshToken);

    // 미들웨어에서 읽을 수 있도록 쿠키에도 저장
    document.cookie = `access_token=${accessToken}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
    if (refreshToken) {
      document.cookie = `refresh_token=${refreshToken}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    }

    apiClient
      .get<ApiResponse<UserInfo>>("/api/v1/users/me")
      .then(async ({ data }) => {
        setAuth(data.data, accessToken);

        const profile = data.data;

        // 1순위: 동의 미완료 시 동의 화면
        const hasAgreements =
          profile.agreed_personal_info &&
          profile.agreed_sensitive_info &&
          profile.agreed_medical_data;

        if (!hasAgreements) {
          router.replace("/agreements");
          return;
        }

        // 2순위: lifestyle 미입력 시 헬스정보 화면
        try {
          const { data: ls } = await apiClient.get("/api/v1/users/me/lifestyle");
          if (!ls.data) {
            router.replace("/health-profile");
            return;
          }
        } catch { /* 무시 */ }

        router.replace("/");
      })
      .catch(() => {
        setErrorMessage("사용자 정보를 불러오는 데 실패했습니다.");
        setStatus("error");
      });
  }, [router, setAuth]);

  if (status === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
        <span className="text-5xl">⚠️</span>
        <h1 className="text-xl font-bold text-foreground">로그인 실패</h1>
        <p className="text-sm text-muted-foreground">{errorMessage}</p>
        <button
          onClick={() => router.replace("/login")}
          className="mt-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          다시 로그인하기
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <span className="text-4xl">🏥</span>
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">로그인 처리 중...</p>
    </div>
  );
}
