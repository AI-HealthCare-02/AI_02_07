import type { Metadata } from "next";
import { Geist } from "next/font/google";
import QueryProvider from "@/providers/query-provider";
import ThemeProvider from "@/providers/theme-provider";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
});

export const metadata: Metadata = {
  title: {
    default: "HealthGuide",
    template: "%s | HealthGuide",
  },
  description: "AI 기반 헬스케어 상담 웹 서비스 — AI 챗봇 상담, 의료 문서 분석, 건강 가이드, 알약 분석",
  keywords: ["헬스케어", "AI 상담", "의료 문서", "알약 분석", "건강 가이드"],
  authors: [{ name: "HealthGuide Team" }],
  openGraph: {
    title: "HealthGuide",
    description: "AI 기반 헬스케어 상담 웹 서비스",
    type: "website",
    locale: "ko_KR",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('theme-storage');
                  var theme = stored ? JSON.parse(stored).state.theme : 'dark';
                  document.documentElement.classList.add(theme);
                } catch(e) {
                  document.documentElement.classList.add('dark');
                }
              })()
            `,
          }}
        />
      </head>
      <body className={`${geist.variable} font-sans antialiased`}>
        <ThemeProvider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
