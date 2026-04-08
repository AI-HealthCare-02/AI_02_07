"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/header";
import { useAuthStore } from "@/store/auth-store";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, _hasHydrated } = useAuthStore();

  useEffect(() => {
    if (_hasHydrated && !isAuthenticated) router.replace("/login");
  }, [_hasHydrated, isAuthenticated, router]);

  if (!_hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090a0f]">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  return (
    <>
      <Header />
      <main className="min-h-screen bg-[#090a0f] pb-16 lg:pb-0">{children}</main>
    </>
  );
}
