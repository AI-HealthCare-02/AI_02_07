"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";

export default function UserProfile() {
  const router = useRouter();
  const { user, clearAuth } = useAuthStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 닫기
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleLogout = () => {
    clearAuth();
    setOpen(false);
    router.replace("/");
  };

  const handleProfile = () => {
    setOpen(false);
    router.push("/profile");
  };

  const handleHealthProfile = () => {
    setOpen(false);
    router.push("/health-profile");
  };

  const handleBookmarks = () => {
    setOpen(false);
    router.push("/bookmarks");
  };

  if (!user) return null;

  // 닉네임 첫 글자로 아바타 생성
  const initial = (user.nickname || user.name || "U").charAt(0).toUpperCase();

  return (
    <div ref={ref} className="relative">
      {/* 프로필 버튼 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/5 px-3 py-1.5 backdrop-blur-sm transition-all hover:border-teal-400/60 hover:bg-teal-500/15"
      >
        {/* 아바타 */}
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 text-xs font-bold text-white shadow-sm">
          {initial}
        </div>
        {/* 닉네임 */}
        <span className="max-w-[80px] truncate text-sm font-medium text-teal-300">
          {user.nickname || user.name}
        </span>
        {/* 화살표 */}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`text-teal-400/70 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* 드롭다운 */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-44 overflow-hidden rounded-xl border border-border bg-card/95 shadow-xl backdrop-blur-xl">
          {/* 유저 정보 */}
          <div className="border-b border-border px-4 py-3">
            <p className="text-xs font-semibold text-foreground truncate">{user.nickname || user.name}</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground truncate">{user.email}</p>
          </div>

          {/* 메뉴 */}
          <div className="py-1">
            <button
              onClick={handleHealthProfile}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-teal-500/10 hover:text-teal-500"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
              헬스정보 수정
            </button>
            <button
              onClick={handleBookmarks}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-teal-500/10 hover:text-teal-500"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
              </svg>
              북마크
            </button>
            <button
              onClick={handleProfile}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-teal-500/10 hover:text-teal-500"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              개인정보
            </button>
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-red-500 transition-colors hover:bg-red-500/10"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              로그아웃
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
