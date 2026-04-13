import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AdminInfo {
  adminId: number;
  adminEmail: string;
  adminName: string;
  roleCode: string;
}

interface AdminAuthState {
  admin: AdminInfo | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  _hasHydrated: boolean;
  setAuth: (admin: AdminInfo, accessToken: string) => void;
  clearAuth: () => void;
  setHasHydrated: (v: boolean) => void;
}

export const useAdminStore = create<AdminAuthState>()(
  persist(
    (set) => ({
      admin: null,
      accessToken: null,
      isAuthenticated: false,
      _hasHydrated: false,

      setAuth: (admin, accessToken) => {
        localStorage.setItem("admin_access_token", accessToken);
        set({ admin, accessToken, isAuthenticated: true });
      },

      clearAuth: () => {
        localStorage.removeItem("admin_access_token");
        set({ admin: null, accessToken: null, isAuthenticated: false });
      },

      setHasHydrated: (v) => set({ _hasHydrated: v }),
    }),
    {
      name: "admin-auth-storage",
      partialize: (state) => ({
        admin: state.admin,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state.setHasHydrated(true);
        else useAdminStore.setState({ _hasHydrated: true });
      },
    }
  )
);
