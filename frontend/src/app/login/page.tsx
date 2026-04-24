"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import apiClient from "@/lib/axios";

interface LoginUrl {
  authorization_url: string;
  provider: string;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

async function getOAuthUrl(provider: "google" | "kakao"): Promise<string> {
  const { data } = await apiClient.get<ApiResponse<LoginUrl>>(
    `/api/v1/auth/${provider}/login`
  );
  return data.data.authorization_url;
}

export default function LoginPage() {
  const [loading, setLoading] = useState<"google" | "kakao" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // URL에 에러 파라미터가 있으면 표시
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err) setError(params.get("message") ?? "로그인에 실패했습니다.");
  }, []);

  const handleOAuth = async (provider: "google" | "kakao") => {
    setLoading(provider);
    setError(null);
    try {
      const url = await getOAuthUrl(provider);
      if (!url.startsWith("http")) {
        setError(`${provider === "google" ? "Google" : "카카오"} OAuth가 서버에 설정되지 않았습니다.`);
        setLoading(null);
        return;
      }
      window.location.href = url;
    } catch {
      setError("로그인 URL을 가져오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.");
      setLoading(null);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-primary/5 to-background px-4">
      {/* 로고 */}
      <Link href="/" className="mb-8 flex items-center gap-2">
        <span className="text-3xl">🏥</span>
        <span className="text-2xl font-bold text-primary">HealthGuide</span>
      </Link>

      {/* 카드 */}
      <div className="w-full max-w-sm rounded-2xl border bg-card p-8 shadow-lg">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-foreground">로그인</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            소셜 계정으로 간편하게 시작하세요
          </p>
        </div>

        {/* 에러 메시지 */}
        {error && (
          <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3">
          {/* 구글 로그인 - 추후 활성화 */}
          {/* <button
            onClick={() => handleOAuth("google")}
            disabled={loading !== null}
            className="flex w-full items-center justify-center gap-3 rounded-lg border bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-all hover:bg-gray-50 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading === "google" ? (
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
            ) : (
              <GoogleIcon />
            )}
            Google로 계속하기
          </button> */}

          {/* 카카오 로그인 */}
          <button
            onClick={() => handleOAuth("kakao")}
            disabled={loading !== null}
            className="flex w-full items-center justify-center gap-3 rounded-lg px-4 py-3 text-sm font-medium text-[#3C1E1E] shadow-sm transition-all hover:brightness-95 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
            style={{ backgroundColor: "#FEE500" }}
          >
            {loading === "kakao" ? (
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-yellow-600 border-t-yellow-900" />
            ) : (
              <KakaoIcon />
            )}
            카카오로 계속하기
          </button>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          로그인 시{" "}
          <span className="underline underline-offset-2 cursor-pointer hover:text-foreground">
            이용약관
          </span>{" "}
          및{" "}
          <span className="underline underline-offset-2 cursor-pointer hover:text-foreground">
            개인정보처리방침
          </span>
          에 동의하게 됩니다.
        </p>
      </div>

      <Link
        href="/"
        className="mt-6 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← 홈으로 돌아가기
      </Link>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M9 0C4.029 0 0 3.134 0 7c0 2.467 1.548 4.638 3.888 5.896L2.94 16.5a.25.25 0 0 0 .372.274L7.74 14.1c.41.057.83.086 1.26.086 4.971 0 9-3.134 9-7S13.971 0 9 0z" fill="#3C1E1E"/>
    </svg>
  );
}
