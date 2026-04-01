"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/chat",  icon: "🤖", label: "AI 상담" },
  { href: "/guide", icon: "📋", label: "건강 가이드" },
  { href: "/pill",  icon: "💊", label: "알약 분석" },
  { href: "/docs",  icon: "📄", label: "의료 문서" },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <>
      {/* ── 상단 헤더 ── */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl">🏥</span>
            <span className="text-xl font-bold text-primary">HealthGuide</span>
          </Link>

          {/* 데스크탑 전용 nav */}
          <nav className="hidden items-center gap-6 lg:flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium transition-colors hover:text-foreground ${
                  pathname === item.href ? "text-primary font-semibold" : "text-muted-foreground"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <Link
            href="/login"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            로그인
          </Link>
        </div>
      </header>

      {/* ── 모바일 / 태블릿 하단 고정 nav (lg 미만) ── */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:hidden">
        <div className="flex h-16 items-center justify-around">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-1 flex-col items-center justify-center gap-1 py-2 transition-colors ${
                  isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span className="text-xl leading-none">{item.icon}</span>
                <span className="text-[10px] font-medium">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
