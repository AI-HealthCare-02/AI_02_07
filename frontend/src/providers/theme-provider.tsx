"use client";

import { useEffect, useState } from 'react';
import { useThemeStore } from '@/store/theme-store';

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme } = useThemeStore();
  const [mounted, setMounted] = useState(false);

  // 마운트 전: localStorage에서 직접 읽어 즉시 적용 (깜빡임 방지)
  useEffect(() => {
    try {
      const stored = localStorage.getItem('theme-storage');
      const savedTheme = stored ? JSON.parse(stored).state.theme : 'dark';
      document.documentElement.classList.remove('light', 'dark');
      document.documentElement.classList.add(savedTheme);
    } catch {
      document.documentElement.classList.add('dark');
    }
    setMounted(true);
  }, []);

  // theme 변경 시 DOM 동기화
  useEffect(() => {
    if (!mounted) return;
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(theme);
  }, [theme, mounted]);

  return <>{children}</>;
}
