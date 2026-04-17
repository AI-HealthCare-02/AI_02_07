import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { useAdminStore } from "@/store/admin-store";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const adminApiClient = axios.create({
  baseURL: typeof window === "undefined" ? BASE_URL : "",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

adminApiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("admin_access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

adminApiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // store를 초기화해야 isAuthenticated가 false가 되어 루프가 끊김
      // window.location.href 직접 이동은 store를 초기화하지 않아 무한 루프 발생
      useAdminStore.getState().clearAuth();
      if (typeof window !== "undefined") window.location.replace("/admin/login");
    }
    const message =
      (error.response?.data as { detail?: string })?.detail ??
      error.message ??
      "오류가 발생했습니다.";
    return Promise.reject(new Error(message));
  }
);

// ── Types ──────────────────────────────────────────────────

export interface DashboardSummary {
  totalUsers: number;
  todayActiveUsers: number;
  ocrUsageCount: number;
  todayChatCount: number;
  todayFilterBlockedCount: { domainBlocked: number; emergencyBlocked: number; total: number };
}

export interface ChartData {
  type: string;
  period: string;
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

export interface AdminUserItem {
  userId: number;
  name: string;
  email: string;
  createdAt: string;
  providerCode: string;
  providerName: string;
  isSuspended: boolean;
  status: string;
}

export interface AdminUserList {
  totalCount: number;
  page: number;
  size: number;
  items: AdminUserItem[];
}

export interface SystemSettings {
  answerModel: { apiModel: string; temperature: number; maxTokens: number };
  filterModel: { apiModel: string; temperature: number; maxTokens: number; note?: string };
  updatedAt: string;
}

export interface ErrorLogItem {
  logId: number;
  userId: number | null;
  errorType: string | null;
  errorMessage: string;
  stackTrace: string | null;
  requestUrl: string | null;
  createdAt: string;
}

export interface ErrorLogList {
  totalCount: number;
  page: number;
  size: number;
  items: ErrorLogItem[];
}

export interface ChatStatItem {
  message_id: number;
  room_id: number;
  model_name: string | null;
  input_text: string | null;
  output_text: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  cost_usd: number | null;
  latency_ms: number | null;
  filter_result: string | null;
  created_at: string;
}

export interface ChatStatList {
  totalCount: number;
  page: number;
  size: number;
  items: ChatStatItem[];
}

// ── API Functions ──────────────────────────────────────────

export const adminApi = {
  login: (adminEmail: string, password: string) =>
    adminApiClient.post("/api/admin/auth/login", { adminEmail, password }),

  logout: () => adminApiClient.post("/api/admin/auth/logout"),

  getDashboardSummary: () =>
    adminApiClient.get("/api/admin/dashboard/summary"),

  getDashboardChart: (params: {
    type: string;
    period: string;
    startDate?: string;
    endDate?: string;
  }) => adminApiClient.get("/api/admin/dashboard/chart", { params }),

  getUsers: (params: { page?: number; size?: number; keyword?: string; status?: string }) =>
    adminApiClient.get("/api/admin/users", { params }),

  suspendUser: (userId: number) =>
    adminApiClient.patch(`/api/admin/users/${userId}/suspend`),

  unsuspendUser: (userId: number) =>
    adminApiClient.patch(`/api/admin/users/${userId}/unsuspend`),

  getSystemSettings: () =>
    adminApiClient.get("/api/admin/system/settings"),

  updateSystemSettings: (body: {
    answerModel: { apiModel: string; temperature: number; maxTokens: number };
    filterModel: { apiModel: string };
  }) => adminApiClient.put("/api/admin/system/settings", body),

  testLlm: (body: { apiModel: string; temperature: number; maxTokens: number }) =>
    adminApiClient.post("/api/admin/system/settings/test-llm", body),

  getErrors: (params: { page?: number; size?: number; error_type?: string; start_date?: string; end_date?: string }) =>
    adminApiClient.get("/api/admin/errors", { params }),

  getErrorTypes: () =>
    adminApiClient.get("/api/admin/errors/types"),

  deleteError: (logId: number) =>
    adminApiClient.delete(`/api/admin/errors/${logId}`),

  getChatStats: (params: {
    page?: number;
    size?: number;
    room_id?: number;
    model_name?: string;
    filter_result?: string;
    start_date?: string;
    end_date?: string;
  }) => adminApiClient.get("/api/admin/chat/stats", { params }),

  downloadChatStatsCsv: (params: {
    room_id?: number;
    model_name?: string;
    filter_result?: string;
    start_date?: string;
    end_date?: string;
  }) =>
    adminApiClient.get("/api/admin/chat/stats/download", {
      params,
      responseType: "blob",
    }),
};
