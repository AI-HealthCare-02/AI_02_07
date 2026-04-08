"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { useThemeStore } from "@/store/theme-store";
import UserProfile from "@/components/layout/UserProfile";
import ThemeToggle from "@/components/ui/theme-toggle";

// ── 아이콘 ────────────────────────────────────────────────
function IconChat({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M8 10h8M8 14h5" />
    </svg>
  );
}
function IconDoc({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  );
}
function IconPill({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.5 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v7" />
      <circle cx="17" cy="17" r="5" />
      <path d="m14.5 19.5 5-5" />
    </svg>
  );
}
function IconGuide({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}
function IconHome({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}
function IconHealth({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}

const NAV_ITEMS = [
  { href: "/chat",  label: "AI 상담",    Icon: IconChat  },
  { href: "/guide", label: "건강 가이드", Icon: IconGuide },
  { href: "/pill",  label: "알약 분석",  Icon: IconPill  },
  { href: "/docs",  label: "의료 문서",  Icon: IconDoc   },
];

// 사이드 드로어 메뉴 (모바일 햄버거)
const DRAWER_ITEMS = [
  { href: "/",             label: "홈",         Icon: IconHome   },
  { href: "/chat",         label: "AI 상담",    Icon: IconChat   },
  { href: "/guide",        label: "건강 가이드", Icon: IconGuide  },
  { href: "/pill",         label: "알약 분석",  Icon: IconPill   },
  { href: "/docs",         label: "의료 문서",  Icon: IconDoc    },
  { href: "/health-profile", label: "헬스정보", Icon: IconHealth },
];

export default function Header() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();
  const { theme } = useThemeStore();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 라우트 변경 시 드로어 닫기
  useEffect(() => { setDrawerOpen(false); }, [pathname]);

  // 드로어 열릴 때 body 스크롤 잠금
  useEffect(() => {
    document.body.style.overflow = drawerOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [drawerOpen]);

  const activeColor = "#14b8a6";
  const inactiveColor = theme === "dark" ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.45)";

  return (
    <>
      {/* ── 상단 헤더 (fixed) ── */}
      <header className="fixed top-0 left-0 right-0 z-50 w-full border-b border-border bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-10">

          {/* 로고 */}
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-500/30 bg-teal-500/10">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <span className="text-lg font-bold tracking-widest text-foreground">
              HEALTH<span className="text-teal-400">GUIDE</span>
            </span>
          </Link>

          {/* 데스크탑 nav */}
          <nav className="hidden items-center gap-8 lg:flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium tracking-wide transition-colors ${
                  pathname === item.href ? "text-teal-400" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* 우측 영역 */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {/* 데스크탑: UserProfile 드롭다운 */}
            <div className="hidden lg:block">
              {isAuthenticated ? (
                <UserProfile />
              ) : (
                <Link
                  href="/login"
                  className="rounded-full border border-teal-500/30 bg-teal-500/5 px-5 py-2 text-sm font-medium text-teal-300 backdrop-blur-sm transition-all hover:border-teal-400/60 hover:bg-teal-500/15"
                >
                  로그인
                </Link>
              )}
            </div>
            {/* 모바일: 햄버거 버튼 */}
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground transition hover:text-foreground lg:hidden"
              aria-label="메뉴 열기"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* ── 모바일 사이드 드로어 ── */}
      {/* 오버레이 */}
      <div
        className={`fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          drawerOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setDrawerOpen(false)}
      />
      {/* 드로어 패널 */}
      <aside
        className={`fixed right-0 top-0 z-[70] flex h-full w-72 flex-col border-l border-border bg-background shadow-2xl transition-transform duration-300 ease-in-out lg:hidden ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* 드로어 헤더 */}
        <div className="flex h-16 items-center justify-between border-b border-border px-5">
          <span className="text-sm font-semibold text-foreground">메뉴</span>
          <button
            onClick={() => setDrawerOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
            aria-label="메뉴 닫기"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* 드로어 nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {DRAWER_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`mb-1 flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-teal-500/10 text-teal-500"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <item.Icon size={18} color={isActive ? activeColor : inactiveColor} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* 드로어 하단: 유저 정보 or 로그인 */}
        <div className="border-t border-border p-4">
          {isAuthenticated ? (
            <DrawerUserSection onClose={() => setDrawerOpen(false)} />
          ) : (
            <Link
              href="/login"
              className="flex w-full items-center justify-center rounded-xl bg-teal-600 py-3 text-sm font-medium text-white transition hover:bg-teal-500"
            >
              로그인
            </Link>
          )}
        </div>
      </aside>

      {/* ── 모바일 하단 고정 nav ── */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-around">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex flex-1 flex-col items-center justify-center gap-1 py-2"
              >
                <span style={{ filter: isActive ? "drop-shadow(0 0 6px rgba(20,184,166,0.7))" : "none" }}>
                  <item.Icon size={20} color={isActive ? activeColor : inactiveColor} />
                </span>
                <span
                  className="text-[10px] font-medium transition-colors"
                  style={{ color: isActive ? activeColor : inactiveColor }}
                >
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}

// ── 드로어 내 유저 섹션 ──────────────────────────────────
function DrawerUserSection({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const { user, clearAuth } = useAuthStore();
  if (!user) return null;

  const initial = (user.nickname || user.name || "U").charAt(0).toUpperCase();

  const handleLogout = () => {
    clearAuth();
    onClose();
    router.replace("/");
  };

  return (
    <div className="space-y-2">
      {/* 유저 정보 */}
      <div className="flex items-center gap-3 rounded-xl bg-muted px-3 py-2.5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 text-xs font-bold text-white">
          {initial}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{user.nickname || user.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{user.email}</p>
        </div>
      </div>
      {/* 메뉴 버튼들 */}
      <button
        onClick={() => { onClose(); router.push("/health-profile"); }}
        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
        헬스정보 수정
      </button>
      <button
        onClick={() => { onClose(); router.push("/profile"); }}
        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
        개인정보
      </button>
      <button
        onClick={handleLogout}
        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-red-500 transition hover:bg-red-500/10"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        로그아웃
      </button>
    </div>
  );
}

