"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  animate,
  MotionValue,
} from "framer-motion";
import { useAuthStore } from "@/store/auth-store";
import UserProfile from "@/components/layout/UserProfile";

// ── SVG 아이콘 ────────────────────────────────────────────
function IconChat({ size = 20, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M8 10h8M8 14h5" />
    </svg>
  );
}
function IconDoc({ size = 20, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  );
}
function IconPill({ size = 20, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.5 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v7" />
      <circle cx="17" cy="17" r="5" />
      <path d="m14.5 19.5 5-5" />
    </svg>
  );
}
function IconGuide({ size = 20, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}
// ── 고정 파티클 데이터 ────────────────────────────────────
const PARTICLES_SEED = [
  { id: 0,  x: 8,  y: 12, size: 2,   opacity: 0.25, duration: 9,  delay: 0   },
  { id: 1,  x: 23, y: 45, size: 1.5, opacity: 0.15, duration: 11, delay: 1.2 },
  { id: 2,  x: 37, y: 78, size: 2.5, opacity: 0.30, duration: 8,  delay: 0.5 },
  { id: 3,  x: 52, y: 22, size: 1,   opacity: 0.20, duration: 13, delay: 2.1 },
  { id: 4,  x: 67, y: 55, size: 2,   opacity: 0.18, duration: 10, delay: 0.8 },
  { id: 5,  x: 81, y: 33, size: 3,   opacity: 0.12, duration: 14, delay: 3.0 },
  { id: 6,  x: 14, y: 88, size: 1.5, opacity: 0.22, duration: 7,  delay: 1.5 },
  { id: 7,  x: 44, y: 66, size: 2,   opacity: 0.28, duration: 12, delay: 0.3 },
  { id: 8,  x: 72, y: 91, size: 1,   opacity: 0.16, duration: 9,  delay: 2.7 },
  { id: 9,  x: 91, y: 14, size: 2.5, opacity: 0.20, duration: 11, delay: 1.0 },
  { id: 10, x: 5,  y: 52, size: 1.5, opacity: 0.14, duration: 15, delay: 3.5 },
  { id: 11, x: 29, y: 37, size: 2,   opacity: 0.26, duration: 8,  delay: 0.6 },
  { id: 12, x: 58, y: 82, size: 1,   opacity: 0.18, duration: 10, delay: 2.3 },
  { id: 13, x: 76, y: 48, size: 3,   opacity: 0.10, duration: 13, delay: 1.8 },
  { id: 14, x: 88, y: 72, size: 1.5, opacity: 0.24, duration: 9,  delay: 0.9 },
  { id: 15, x: 19, y: 61, size: 2,   opacity: 0.20, duration: 11, delay: 2.0 },
  { id: 16, x: 42, y: 18, size: 1,   opacity: 0.30, duration: 7,  delay: 0.4 },
  { id: 17, x: 63, y: 94, size: 2.5, opacity: 0.15, duration: 14, delay: 3.2 },
  { id: 18, x: 85, y: 27, size: 1.5, opacity: 0.22, duration: 10, delay: 1.4 },
  { id: 19, x: 33, y: 73, size: 2,   opacity: 0.18, duration: 12, delay: 2.6 },
  { id: 20, x: 55, y: 41, size: 1,   opacity: 0.28, duration: 8,  delay: 0.7 },
  { id: 21, x: 78, y: 59, size: 3,   opacity: 0.12, duration: 15, delay: 3.8 },
  { id: 22, x: 11, y: 29, size: 1.5, opacity: 0.20, duration: 9,  delay: 1.1 },
  { id: 23, x: 47, y: 85, size: 2,   opacity: 0.16, duration: 11, delay: 2.4 },
  { id: 24, x: 69, y: 11, size: 1,   opacity: 0.24, duration: 13, delay: 0.2 },
  { id: 25, x: 93, y: 44, size: 2.5, opacity: 0.14, duration: 10, delay: 1.7 },
  { id: 26, x: 26, y: 97, size: 1.5, opacity: 0.26, duration: 8,  delay: 2.9 },
  { id: 27, x: 50, y: 50, size: 2,   opacity: 0.20, duration: 12, delay: 0.1 },
];

const ORBS = [
  { size: 420, color: "rgba(20,184,166,0.06)", blur: 80, left: "60%", top: "20%", duration: 18, dir: -1 },
  { size: 320, color: "rgba(16,185,129,0.05)", blur: 60, left: "15%", top: "65%", duration: 22, dir:  1 },
  { size: 200, color: "rgba(6,182,212,0.07)",  blur: 50, left: "80%", top: "70%", duration: 15, dir: -1 },
];

const FEATURES = [
  { Icon: IconChat,  label: "AI 챗봇 상담",   desc: "3단계 필터링 기반 실시간 의료 상담",  href: "/chat",  accent: "#14b8a6" },
  { Icon: IconDoc,   label: "의료 문서 분석", desc: "vLLM 기반 처방전·진단서 즉시 분석",  href: "/docs",  accent: "#10b981" },
  { Icon: IconPill,  label: "알약 분석",      desc: "이미지 AI로 약품 정보 즉시 식별",     href: "/pill",  accent: "#06b6d4" },
  { Icon: IconGuide, label: "건강 가이드",    desc: "맞춤형 복약 일정 및 생활습관 관리",  href: "/guide", accent: "#14b8a6" },
];

const NAV_ITEMS = [
  { href: "/chat",  label: "AI 상담",    Icon: IconChat  },
  { href: "/guide", label: "건강 가이드", Icon: IconGuide },
  { href: "/pill",  label: "알약 분석",  Icon: IconPill  },
  { href: "/docs",  label: "의료 문서",  Icon: IconDoc   },
];

// ── EKG 모니터 (Canvas 기반) ─────────────────────────────
// 왼쪽→오른쪽으로 빠르게 흘러가며 랜덤 진폭, 끝에서 즉시 리셋
const EKG_TEMPLATE = [
  0, 0, 0, 0,
  -4, 0, 2, 0,
  0, 0,
  -55, 32, -16, 0,
  0,
  6, 12, 6, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
];

function generateWave(cycles: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < cycles; i++) {
    const amp  = 0.8 + Math.random() * 0.6;
    const flip = Math.random() > 0.5 ? 1 : -1;
    EKG_TEMPLATE.forEach((v) => result.push(v * amp * flip));
  }
  return result;
}

function EKGMonitor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef  = useRef<number>(0);
  const stateRef  = useRef({ x: 0, waveIdx: 0, wave: generateWave(20), prevY: 0, stopped: false });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W  = canvas.width;
    const H  = canvas.height;
    const CY = H / 2;
    const SPEED    = 6.3;
    const CURSOR_W = 36;

    const drawGrid = (x0 = 0, x1 = W) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(x0, 0, x1 - x0, H);
      ctx.clip();
      ctx.clearRect(x0, 0, x1 - x0, H);
      ctx.strokeStyle = "rgba(20,184,166,0.07)";
      ctx.lineWidth = 0.4;
      for (let gx = Math.floor(x0 / 16) * 16; gx <= x1; gx += 16) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (let gy = 0; gy <= H; gy += 16) {
        ctx.beginPath(); ctx.moveTo(x0, gy); ctx.lineTo(x1, gy); ctx.stroke();
      }
      ctx.strokeStyle = "rgba(20,184,166,0.13)";
      ctx.lineWidth = 0.6;
      for (let gx = Math.floor(x0 / 80) * 80; gx <= x1; gx += 80) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (let gy = 0; gy <= H; gy += 80) {
        ctx.beginPath(); ctx.moveTo(x0, gy); ctx.lineTo(x1, gy); ctx.stroke();
      }
      ctx.restore();
    };

    drawGrid();
    stateRef.current.prevY = CY;

    const tick = () => {
      const s = stateRef.current;
      if (s.stopped) {
        frameRef.current = requestAnimationFrame(tick);
        return;
      }

      const x = s.x;
      drawGrid(x, Math.min(x + CURSOR_W, W));

      const wv = s.wave[s.waveIdx % s.wave.length];
      const ny = CY + wv * 2.0;
      const px = Math.max(0, x - SPEED);
      const py = s.prevY;

      ctx.shadowColor = "rgba(20,184,166,0.7)";
      ctx.shadowBlur  = 6;
      ctx.strokeStyle = "rgba(20,184,166,0.20)";
      ctx.lineWidth   = 3;
      ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(x, ny); ctx.stroke();

      ctx.shadowBlur  = 3;
      ctx.strokeStyle = "rgba(20,184,166,0.55)";
      ctx.lineWidth   = 1.5;
      ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(x, ny); ctx.stroke();
      ctx.shadowBlur  = 0;

      ctx.beginPath();
      ctx.arc(x, ny, 1.8, 0, Math.PI * 2);
      ctx.fillStyle   = "rgba(20,184,166,0.75)";
      ctx.shadowColor = "rgba(20,184,166,0.9)";
      ctx.shadowBlur  = 8;
      ctx.fill();
      ctx.shadowBlur  = 0;

      s.prevY    = ny;
      s.x       += SPEED;
      s.waveIdx += 1;

      // 1사이클 완료 시 멈춤
      if (s.x >= W) {
        s.x       = W;
        s.stopped = true;
      }

      frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, []);

  return (
    <div className="pointer-events-none absolute top-1/2 left-0 right-0 -translate-y-1/2 px-0">
      <canvas
        ref={canvasRef}
        width={1400}
        height={100}
        className="w-full h-auto opacity-15"
      />
    </div>
  );
}

function useCounter(target: number, duration = 2) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    const controls = animate(0, target, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setValue(Math.floor(v)),
    });
    return controls.stop;
  }, [target, duration]);
  return value;
}

// ── Orb 컴포넌트 ──────────────────────────────────────────
function OrbItem({ orb, pX, pY }: { orb: (typeof ORBS)[number]; pX: MotionValue<number>; pY: MotionValue<number> }) {
  const tx = useTransform(pX, (v) => v * orb.dir * 1.4);
  const ty = useTransform(pY, (v) => v * orb.dir * 1.4);
  return (
    <motion.div
      className="pointer-events-none absolute rounded-full"
      style={{ width: orb.size, height: orb.size, left: orb.left, top: orb.top, background: orb.color, filter: `blur(${orb.blur}px)`, x: tx, y: ty }}
      animate={{ scale: [1, 1.12, 1], opacity: [0.7, 1, 0.7] }}
      transition={{ duration: orb.duration, repeat: Infinity, ease: "easeInOut" }}
    />
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────
export default function HeroSection() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();
  const containerRef = useRef<HTMLDivElement>(null);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const spotX = useSpring(mouseX, { stiffness: 120, damping: 18 });
  const spotY = useSpring(mouseY, { stiffness: 120, damping: 18 });
  const parallaxX = useSpring(mouseX, { stiffness: 30, damping: 25 });
  const parallaxY = useSpring(mouseY, { stiffness: 30, damping: 25 });
  const pX = useTransform(parallaxX, [0, 1440], [-50, 50]);
  const pY = useTransform(parallaxY, [0, 900],  [-50, 50]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
  };

  const users    = useCounter(12400);
  const accuracy = useCounter(98);
  const analyses = useCounter(34);

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      className="relative min-h-screen w-full overflow-hidden bg-[#090a0f]"
    >
      {/* Spotlight */}
      <motion.div
        className="pointer-events-none absolute z-10 h-[700px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          left: spotX,
          top: spotY,
          background: "radial-gradient(circle, rgba(20,184,166,0.22) 0%, rgba(6,182,212,0.10) 35%, rgba(16,185,129,0.04) 60%, transparent 75%)",
        }}
      />
      {/* Spotlight 내부 코어 */}
      <motion.div
        className="pointer-events-none absolute z-10 h-[120px] w-[120px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          left: spotX,
          top: spotY,
          background: "radial-gradient(circle, rgba(20,184,166,0.35) 0%, transparent 70%)",
          filter: "blur(8px)",
        }}
      />

      {/* Orbs */}
      {ORBS.map((orb, i) => <OrbItem key={i} orb={orb} pX={pX} pY={pY} />)}

      {/* 파티클 */}
      <motion.div className="pointer-events-none absolute inset-0" style={{ x: pX, y: pY }}>
        {PARTICLES_SEED.map((p) => (
          <motion.div
            key={p.id}
            className="absolute rounded-full bg-teal-400"
            style={{ left: `${p.x}%`, top: `${p.y}%`, width: p.size * 1.8, height: p.size * 1.8, opacity: p.opacity * 1.6 }}
            animate={{ opacity: [p.opacity * 1.6, p.opacity * 4, p.opacity * 1.6], scale: [1, 2.2, 1] }}
            transition={{ duration: p.duration, repeat: Infinity, delay: p.delay, ease: "easeInOut" }}
          />
        ))}
      </motion.div>

      {/* 그리드 */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage: "linear-gradient(rgba(20,184,166,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(20,184,166,0.8) 1px, transparent 1px)",
          backgroundSize: "80px 80px",
        }}
      />

      {/* EKG 모니터 */}
      <EKGMonitor />

      {/* ── 콘텐츠 ── */}
      <div className="relative z-20 flex min-h-screen flex-col pb-16 lg:pb-0">

        {/* 헤더 */}
        <header className="flex items-center justify-between px-6 py-5 sm:px-10">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="flex items-center gap-3"
          >
            <motion.div
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-500/30 bg-teal-500/10"
              animate={{ boxShadow: ["0 0 0px rgba(20,184,166,0.3)", "0 0 20px rgba(20,184,166,0.6)", "0 0 0px rgba(20,184,166,0.3)"] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </motion.div>
            <span className="text-lg font-bold tracking-widest text-white/90">
              HEALTH<span className="text-teal-400">GUIDE</span>
            </span>
          </motion.div>

          {/* 데스크탑 nav */}
          <nav className="hidden items-center gap-8 lg:flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium tracking-wide transition-colors ${
                  pathname === item.href ? "text-teal-400" : "text-white/40 hover:text-white/80"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

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
        </header>

        {/* Hero 본문 */}
        <main className="flex flex-1 flex-col items-center justify-center px-6 pb-8 pt-4 text-center sm:px-12">

          {/* 배지 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-teal-500/25 bg-teal-500/8 px-4 py-1.5 backdrop-blur-sm"
          >
            <motion.span
              className="h-1.5 w-1.5 rounded-full bg-teal-400"
              animate={{ opacity: [1, 0.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-xs font-medium uppercase tracking-widest text-teal-300/80">
              AI-Powered Healthcare Platform
            </span>
          </motion.div>

          {/* 타이틀 */}
          <motion.h1
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="mb-6 text-5xl font-black leading-[1.05] tracking-tight text-white sm:text-7xl lg:text-8xl"
          >
            당신의 건강을
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage: "linear-gradient(135deg, #14b8a6 0%, #06b6d4 40%, #10b981 100%)",
                filter: "drop-shadow(0 0 30px rgba(20,184,166,0.5))",
              }}
            >
              재정의합니다
            </span>
          </motion.h1>

          {/* 서브카피 */}
          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.65 }}
            className="mb-10 max-w-xl text-base leading-relaxed text-white/40 sm:text-lg"
          >
            첨단 AI가 의료 문서를 분석하고, 알약을 식별하며,
            <br className="hidden sm:block" />
            실시간으로 건강 상담을 제공합니다.
          </motion.p>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.85 }}
            className="mb-16"
          >
            {isAuthenticated ? (
              <Link href="/chat">
                <motion.div
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.97 }}
                  className="cursor-pointer rounded-full px-10 py-4 text-sm font-semibold text-white"
                  style={{
                    background: "linear-gradient(135deg, #14b8a6, #06b6d4)",
                    boxShadow: "0 0 30px rgba(20,184,166,0.35), inset 0 1px 0 rgba(255,255,255,0.15)",
                  }}
                >
                  AI 상담 시작하기
                </motion.div>
              </Link>
            ) : (
              <Link href="/login">
                <motion.div
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.97 }}
                  className="cursor-pointer rounded-full px-10 py-4 text-sm font-semibold text-white"
                  style={{
                    background: "linear-gradient(135deg, #14b8a6, #06b6d4)",
                    boxShadow: "0 0 30px rgba(20,184,166,0.35), inset 0 1px 0 rgba(255,255,255,0.15)",
                  }}
                >
                  지금 시작하기
                </motion.div>
              </Link>
            )}
          </motion.div>

          {/* 통계 */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 1.0 }}
            className="mb-16 flex flex-wrap justify-center gap-10 sm:gap-16"
          >
            {[
              { value: `${users.toLocaleString()}+`, label: "활성 사용자" },
              { value: `${accuracy}%`,               label: "AI 분석 정확도" },
              { value: `${analyses}만+`,             label: "누적 분석 건수" },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-3xl font-black tracking-tight sm:text-4xl">
                  <span className="text-teal-400">{stat.value}</span>
                </div>
                <div className="mt-1 text-xs uppercase tracking-widest text-white/30">{stat.label}</div>
              </div>
            ))}
          </motion.div>

          {/* 기능 카드 */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 1.15 }}
            className="grid w-full max-w-4xl grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
          >
            {FEATURES.map((f, i) => (
              <Link key={i} href={f.href}>
                <motion.div
                  whileHover={{ y: -6, scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  className="group relative overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-5 text-left backdrop-blur-md"
                  style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)" }}
                >
                  {/* 호버 글로우 */}
                  <div
                    className="absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                    style={{ background: `radial-gradient(circle at 50% 0%, ${f.accent}18 0%, transparent 70%)` }}
                  />
                  {/* 상단 보더 글로우 */}
                  <div
                    className="absolute left-0 right-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                    style={{ background: `linear-gradient(90deg, transparent, ${f.accent}80, transparent)` }}
                  />
                  {/* 아이콘 */}
                  <div
                    className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5"
                    style={{ boxShadow: `0 0 12px ${f.accent}30` }}
                  >
                    <f.Icon size={18} color={f.accent} />
                  </div>
                  <div className="mb-1 text-sm font-semibold text-white/85">{f.label}</div>
                  <div className="text-xs leading-relaxed text-white/35">{f.desc}</div>
                </motion.div>
              </Link>
            ))}
          </motion.div>
        </main>

        {/* 푸터 */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="hidden items-center justify-center gap-6 px-6 py-5 text-xs text-white/20 lg:flex"
        >
          <span>© 2026 HealthGuide</span>
          <span className="h-3 w-px bg-white/15" />
          <span>본 서비스는 전문 의료 행위를 대체하지 않습니다</span>
        </motion.footer>
      </div>

      {/* 모바일 / 태블릿 하단 고정 nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/8 bg-[#090a0f]/90 backdrop-blur-xl lg:hidden">
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
                  <item.Icon size={20} color={isActive ? "#14b8a6" : "rgba(255,255,255,0.35)"} />
                </span>
                <span
                  className="text-[10px] font-medium"
                  style={{ color: isActive ? "#14b8a6" : "rgba(255,255,255,0.30)" }}
                >
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
