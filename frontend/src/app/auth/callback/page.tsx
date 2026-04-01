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

    // 토큰 저장 후 유저 정보 조회
    localStorage.setItem("access_token", accessToken);
    if (refreshToken) localStorage.setItem("refresh_token", refreshToken);

    apiClient
      .get<ApiResponse<UserInfo>>("/api/v1/users/me")
      .then(({ data }) => {
        setAuth(data.data, accessToken);
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
