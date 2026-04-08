"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import UserProfile from "@/components/layout/UserProfile";
import ThemeToggle from "@/components/ui/theme-toggle";

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
const NAV_ITEMS = [
  { href: "/chat",  label: "AI 상담",    Icon: IconChat  },
  { href: "/guide", label: "건강 가이드", Icon: IconGuide },
  { href: "/pill",  label: "알약 분석",  Icon: IconPill  },
  { href: "/docs",  label: "의료 문서",  Icon: IconDoc   },
];

export default function Header() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();

  return (
    <>
      {/* 상단 헤더 */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-10">
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
          <div className="flex items-center gap-3">
            <ThemeToggle />
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
        </div>
      </header>

      {/* 모바일 / 태블릿 하단 고정 nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/90 backdrop-blur-xl lg:hidden">
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
                  <item.Icon size={20} color={isActive ? "#14b8a6" : "hsl(var(--muted-foreground))"} />
                </span>
                <span
                  className="text-[10px] font-medium"
                  style={{ color: isActive ? "#14b8a6" : "hsl(var(--muted-foreground))" }}
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
