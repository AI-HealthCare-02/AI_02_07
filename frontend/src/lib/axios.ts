import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: typeof window === "undefined" ? BASE_URL : "",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// ── 요청 인터셉터 ──
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// ── 응답 인터셉터 ──
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // 401 → 토큰 갱신 시도
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data } = await axios.post(`/api/v1/auth/token/refresh`, null, {
          withCredentials: true,
        });
        const newToken = data?.data?.access_token;
        if (newToken) {
          localStorage.setItem("access_token", newToken);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        }
      } catch {
        localStorage.removeItem("access_token");
        if (typeof window !== "undefined") window.location.href = "/login";
      }
    }

    // 공통 에러 메시지 추출
    const message =
      (error.response?.data as { detail?: string })?.detail ??
      error.message ??
      "알 수 없는 오류가 발생했습니다.";

    return Promise.reject(new Error(message));
  }
);

export default apiClient;
