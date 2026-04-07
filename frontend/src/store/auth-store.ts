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
  setAuth: (user: User, accessToken: string) => void;
  clearAuth: () => void;
  setHasHydrated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      _hasHydrated: false,

      setAuth: (user, accessToken) => {
        localStorage.setItem("access_token", accessToken);
        set({ user, accessToken, isAuthenticated: true });
      },

      clearAuth: () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        if (typeof document !== "undefined") {
          document.cookie = "access_token=; path=/; max-age=0";
          document.cookie = "refresh_token=; path=/; max-age=0";
        }
        set({ user: null, accessToken: null, isAuthenticated: false });
      },

      setHasHydrated: (v) => set({ _hasHydrated: v }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
