"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
// import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
interface Guide {
  guide_id: number;
  title: string;
  hospital_name: string | null;
  visit_date: string;
  guide_status_code: string;
  remaining_days: number | null;
  weekly_compliance_rate: number | null;
  today_progress: { done: number; total: number };
}

// ── 공통 컴포넌트 ──────────────────────────────────────────
function Toast({ msg, type, onClose }: { msg: string; type: "ok" | "err"; onClose: () => void }) {
  return (
    <div className={`fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-5 py-3 text-sm shadow-lg lg:bottom-6 ${
      type === "ok"
        ? "border-teal-500/30 bg-teal-500/10 text-teal-400"
        : "border-red-500/30 bg-red-500/10 text-red-400"
    }`}>
      {msg}
      <button onClick={onClose} className="ml-3 opacity-60 hover:opacity-100">✕</button>
    </div>
  );
}

function Badge({ status }: { status: string }) {
  const isActive = status === "GS_ACTIVE";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
      isActive ? "bg-teal-500/15 text-teal-400" : "bg-muted text-muted-foreground"
    }`}>
      {isActive ? "복약 중" : "완료"}
    </span>
  );
}

function GuideCard({ guide, onClick }: { guide: Guide; onClick: () => void }) {
  const pct = guide.today_progress.total > 0
    ? Math.round((guide.today_progress.done / guide.today_progress.total) * 100)
    : 0;

  return (
    <button
      onClick={onClick}
      className="group relative w-full overflow-hidden rounded-2xl border border-border bg-card p-5 text-left transition-all hover:-translate-y-0.5 hover:border-teal-500/35"
      style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
    >
      <div className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: "radial-gradient(circle at 50% 0%, rgba(20,184,166,0.08) 0%, transparent 70%)" }} />
      <div className="pointer-events-none absolute left-0 right-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: "linear-gradient(90deg, transparent, rgba(20,184,166,0.5), transparent)" }} />

      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{guide.title}</p>
        <Badge status={guide.guide_status_code} />
      </div>

      <p className="mb-2 text-[11px] text-muted-foreground">
        {guide.visit_date}{guide.hospital_name ? ` · ${guide.hospital_name}` : ""}
      </p>

      {guide.guide_status_code === "GS_ACTIVE" && guide.remaining_days !== null && (
        <span className="mb-3 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
          style={{ background: "rgba(251,146,60,0.12)", color: "#fb923c" }}>
          D-{guide.remaining_days}
        </span>
      )}

      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>오늘 복약</span>
          <span className="font-medium text-foreground">{guide.today_progress.done}/{guide.today_progress.total} · {pct}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full transition-all duration-700"
            style={{ width: `${pct}%`, background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }} />
        </div>
      </div>
    </button>
  );
}

// ── Mock 데이터 ────────────────────────────────────────────
const MOCK_GUIDES: Guide[] = [
  { guide_id: 1, title: "고혈압·고지혈증 관리 가이드", hospital_name: "서울대학교병원", visit_date: "2026-03-20", guide_status_code: "GS_ACTIVE", remaining_days: 24, weekly_compliance_rate: 0.87, today_progress: { done: 2, total: 3 } },
  { guide_id: 2, title: "비타민D + 철분제", hospital_name: null, visit_date: "2026-01-10", guide_status_code: "GS_ACTIVE", remaining_days: null, weekly_compliance_rate: 0.80, today_progress: { done: 1, total: 1 } },
  { guide_id: 3, title: "감기·소화불량 처방", hospital_name: "서울나우병원", visit_date: "2026-02-05", guide_status_code: "GS_DONE", remaining_days: 0, weekly_compliance_rate: 1.0, today_progress: { done: 0, total: 0 } },
  { guide_id: 4, title: "당뇨 관리 가이드", hospital_name: "강남세브란스병원", visit_date: "2026-04-01", guide_status_code: "GS_ACTIVE", remaining_days: 60, weekly_compliance_rate: 0.75, today_progress: { done: 0, total: 2 } },
];

// ── 메인 ──────────────────────────────────────────────────
export default function GuidePage() {
  const router = useRouter();
  const [guides, setGuides] = useState<Guide[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("전체");
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const observerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cursorRef = useRef<number | null>(null);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  const fetchGuides = useCallback(async (reset = true) => {
    if (reset) {
      setLoading(true);
      cursorRef.current = null;
    } else {
      setLoadingMore(true);
    }

    try {
      // ── 실제 API ──
      // const params: Record<string, string | number> = { size: 10 };
      // if (statusFilter !== "전체") params.status = statusFilter === "복약 중" ? "GS_ACTIVE" : "GS_DONE";
      // if (search) params.search = search;
      // if (!reset && cursorRef.current) params.cursor = cursorRef.current;
      // const { data } = await apiClient.get("/api/v1/guides", { params });
      // const res = data.data;
      // if (reset) setGuides(res.guides ?? []);
      // else setGuides((p) => [...p, ...(res.guides ?? [])]);
      // cursorRef.current = res.next_cursor ?? null;
      // setHasMore(res.has_more ?? false);

      // ── Mock ──
      await new Promise((r) => setTimeout(r, 400));
      let filtered = MOCK_GUIDES;
      if (statusFilter !== "전체") filtered = filtered.filter((g) => statusFilter === "복약 중" ? g.guide_status_code === "GS_ACTIVE" : g.guide_status_code === "GS_DONE");
      if (search) filtered = filtered.filter((g) => g.title.includes(search) || g.hospital_name?.includes(search));
      if (reset) setGuides(filtered);
      else setGuides((p) => [...p, ...filtered]);
      setHasMore(false);
    } catch {
      showToast("가이드 목록을 불러오지 못했습니다.", "err");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [statusFilter, search]);

  // 검색 debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchGuides(true), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search, statusFilter, fetchGuides]);

  // 무한 스크롤 IntersectionObserver
  useEffect(() => {
    const el = observerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting && hasMore && !loadingMore) fetchGuides(false); },
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, fetchGuides]);

  const today = new Date();
  const todayStr = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일`;
  const activeGuides = guides.filter((g) => g.guide_status_code === "GS_ACTIVE");
  const todayDone = activeGuides.reduce((s, g) => s + g.today_progress.done, 0);
  const todayTotal = activeGuides.reduce((s, g) => s + g.today_progress.total, 0);
  const totalPct = todayTotal > 0 ? Math.round((todayDone / todayTotal) * 100) : 0;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 pb-24 lg:pb-8">

      {/* ── 오늘 현황 배너 ── */}
      <div className="relative mb-6 overflow-hidden rounded-2xl border border-border bg-card p-5">
        <div className="pointer-events-none absolute left-0 right-0 top-0 h-0.5"
          style={{ background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">{todayStr}</p>
            <p className="mt-0.5 text-base font-bold text-foreground">
              💊 맞춤 건강 가이드
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                오늘 {todayDone}/{todayTotal} 완료
              </span>
            </p>
          </div>
        </div>
        <div className="mt-4">
          <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
            <span>오늘 전체 복약 진행률</span>
            <span className="font-medium text-foreground">{totalPct}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: `${totalPct}%`, background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }} />
          </div>
        </div>
      </div>

      {/* ── 검색 + 필터 + 새 가이드 ── */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">🔍</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="가이드 검색..."
            className="w-full rounded-xl border border-border bg-card py-2 pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-border bg-card px-3 py-2 text-xs text-foreground focus:border-teal-500/50 focus:outline-none"
        >
          {["전체", "복약 중", "완료"].map((v) => <option key={v}>{v}</option>)}
        </select>
        <button
          onClick={() => router.push("/guide/new")}
          className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-teal-500"
        >
          + 새 가이드
        </button>
      </div>

      {/* ── 가이드 카드 그리드 ── */}
      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
        </div>
      ) : guides.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16 text-center">
          <p className="mb-3 text-4xl">💊</p>
          <p className="text-sm font-medium text-foreground">아직 가이드가 없어요</p>
          <p className="mt-1 text-xs text-muted-foreground">처방전을 업로드하거나 직접 입력해 첫 가이드를 만들어보세요</p>
          <button
            onClick={() => router.push("/guide/new")}
            className="mt-4 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-500"
          >
            + 새 가이드 만들기
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {guides.map((g) => (
            <GuideCard key={g.guide_id} guide={g} onClick={() => router.push(`/guide/${g.guide_id}`)} />
          ))}
        </div>
      )}

      {/* 무한 스크롤 트리거 */}
      <div ref={observerRef} className="h-4" />
      {loadingMore && (
        <div className="flex justify-center py-4">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
        </div>
      )}

      {/* 면책 고지 */}
      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다. 의료적 판단은 반드시 담당 의사 또는 약사와 상담하세요.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
