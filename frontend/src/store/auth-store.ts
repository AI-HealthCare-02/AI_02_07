import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
  user_id: number;
  email: string;
  nickname: string;
  name: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  _hasHydrated: boolean;
  setHasHydrated: (v: boolean) => void;
  setAuth: (user: User, accessToken: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      _hasHydrated: false,
      setHasHydrated: (v) => set({ _hasHydrated: v }),

      setAuth: (user, accessToken) => {
        localStorage.setItem("access_token", accessToken);
        set({ user, accessToken, isAuthenticated: true });
      },

      clearAuth: () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        // 미들웨어용 쿠키 삭제
        if (typeof document !== "undefined") {
          document.cookie = "access_token=; path=/; max-age=0";
          document.cookie = "refresh_token=; path=/; max-age=0";
        }
        set({ user: null, accessToken: null, isAuthenticated: false });
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        // state가 undefined인 경우(스토리지 파싱 오류 등)에도 반드시 hydrated 처리
        if (state) {
          state.setHasHydrated(true);
        } else {
          useAuthStore.setState({ _hasHydrated: true });
        }
      },
    }
  )
);
