"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
interface TodayProgress { done: number; total: number; }
interface Guide {
  guide_id: number;
  title: string;
  hospital_name: string | null;
  department: string | null;
  visit_date: string;
  guide_status_code: string;
  medication_period_days: number | null;
  remaining_days: number | null;
  weekly_compliance_rate: number | null;
  today_progress: TodayProgress;
}
interface MedCheck {
  check_id: number;
  medication_id: number;
  medication_name: string;
  time_slot: string;
  taken_at: string | null;
  check_date: string;
  is_done: boolean;
}
interface GuidesResponse {
  total_count: number;
  page: number;
  size: number;
  guides: Guide[];
  today_streak?: number;
  today_done?: number;
  today_total?: number;
}

// ── 토스트 ─────────────────────────────────────────────────
function Toast({ message, type, onClose }: { message: string; type: "ok" | "err"; onClose: () => void }) {
  const isOk = type === "ok";
  return (
    <div className={`fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-5 py-3 text-sm shadow-lg lg:bottom-6 ${
      isOk
        ? "border-teal-500/30 bg-teal-500/10 text-teal-400"
        : "border-red-500/30 bg-red-500/10 text-red-400"
    }`}>
      {message}
      <button onClick={onClose} className="ml-3 opacity-60 hover:opacity-100">✕</button>
    </div>
  );
}

// ── 배지 ──────────────────────────────────────────────────
function Badge({ status }: { status: string }) {
  const isActive = status === "GS_ACTIVE";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
      isActive
        ? "bg-teal-500/15 text-teal-400"
        : "bg-white/5 text-white/40"
    }`}>
      {isActive ? "복약 중" : "완료"}
    </span>
  );
}

// ── 가이드 카드 ────────────────────────────────────────────
function GuideCard({ guide, onClick }: { guide: Guide; onClick: () => void }) {
  const pct = guide.today_progress.total > 0
    ? Math.round((guide.today_progress.done / guide.today_progress.total) * 100)
    : 0;
  const isActive = guide.guide_status_code === "GS_ACTIVE";

  return (
    <button
      onClick={onClick}
      className="group relative w-full overflow-hidden rounded-2xl border border-border bg-card p-5 text-left transition-all hover:-translate-y-0.5 hover:border-teal-500/35"
      style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
    >
      {/* hover glow */}
      <div className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: "radial-gradient(circle at 50% 0%, rgba(20,184,166,0.08) 0%, transparent 70%)" }} />
      <div className="pointer-events-none absolute left-0 right-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: "linear-gradient(90deg, transparent, rgba(20,184,166,0.5), transparent)" }} />

      <div className="mb-3 flex items-start justify-between gap-2">
        <p className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{guide.title}</p>
        <Badge status={guide.guide_status_code} />
      </div>

      {isActive && guide.remaining_days !== null && (
        <span className="mb-3 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
          style={{ background: "rgba(251,146,60,0.12)", color: "#fb923c" }}>
          D-{guide.remaining_days}
        </span>
      )}

      {/* 진행률 바 */}
      <div className="mt-auto">
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

// ── 메인 ──────────────────────────────────────────────────
export default function GuidePage() {
  const router = useRouter();
  const [guides, setGuides] = useState<Guide[]>([]);
  const [loading, setLoading] = useState(true);
  const [todayStreak, setTodayStreak] = useState(0);
  const [todayDone, setTodayDone] = useState(0);
  const [todayTotal, setTodayTotal] = useState(0);
  const [medChecks, setMedChecks] = useState<MedCheck[]>([]);
  const [activeGuideId, setActiveGuideId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [statusFilter, setStatusFilter] = useState("전체");
  const [periodFilter, setPeriodFilter] = useState("전체기간");
  const [checkLoading, setCheckLoading] = useState<number | null>(null);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  // TODO: 아래 API들은 백엔드 구현 후 주석 해제
  // GET  /api/v1/guides
  // GET  /api/v1/guides/{id}/med-check
  // POST /api/v1/guides/{id}/med-check
  // DELETE /api/v1/guides/{id}/med-check/{check_id}

  // ── Mock 데이터 ──
  const MOCK_GUIDES: Guide[] = [
    {
      guide_id: 1,
      title: "고혈압·고지혈증 관리 가이드",
      hospital_name: "서울대학교병원",
      department: "내과",
      visit_date: "2026-03-20",
      guide_status_code: "GS_ACTIVE",
      medication_period_days: 30,
      remaining_days: 24,
      weekly_compliance_rate: 0.87,
      today_progress: { done: 2, total: 3 },
    },
    {
      guide_id: 2,
      title: "비타민D + 철분제",
      hospital_name: null,
      department: null,
      visit_date: "2026-01-10",
      guide_status_code: "GS_ACTIVE",
      medication_period_days: null,
      remaining_days: null,
      weekly_compliance_rate: 0.80,
      today_progress: { done: 1, total: 1 },
    },
    {
      guide_id: 3,
      title: "감기·소화불량 처방",
      hospital_name: "서울나우병원",
      department: "가정의학과",
      visit_date: "2026-02-05",
      guide_status_code: "GS_DONE",
      medication_period_days: 7,
      remaining_days: 0,
      weekly_compliance_rate: 1.0,
      today_progress: { done: 0, total: 0 },
    },
  ];

  const MOCK_CHECKS: MedCheck[] = [
    { check_id: 0,  medication_id: 1, medication_name: "오메프라졸캡슐 20mg",  time_slot: "morning_before", taken_at: "2026-04-10T08:15:00", check_date: new Date().toISOString().split("T")[0], is_done: true  },
    { check_id: 0,  medication_id: 2, medication_name: "아모디핀정 5mg",       time_slot: "morning_after",  taken_at: "2026-04-10T08:32:00", check_date: new Date().toISOString().split("T")[0], is_done: true  },
    { check_id: 0,  medication_id: 3, medication_name: "로수바스타틴정 10mg",  time_slot: "evening_after",  taken_at: null,                  check_date: new Date().toISOString().split("T")[0], is_done: false },
  ];

  const fetchGuides = useCallback(async () => {
    setLoading(true);
    try {
      // ── 실제 API (백엔드 구현 후 주석 해제) ──
      // const params: Record<string, string> = {};
      // if (statusFilter !== "전체") params.status = statusFilter === "복약 중" ? "GS_ACTIVE" : "GS_DONE";
      // const { data } = await apiClient.get<{ data: GuidesResponse }>("/api/v1/guides", { params });
      // const res = data.data;
      // setGuides(res.guides ?? []);
      // setTodayStreak(res.today_streak ?? 0);
      // setTodayDone(res.today_done ?? 0);
      // setTodayTotal(res.today_total ?? 0);
      // const firstActive = res.guides?.find((g) => g.guide_status_code === "GS_ACTIVE");
      // if (firstActive) { setActiveGuideId(firstActive.guide_id); fetchMedChecks(firstActive.guide_id); }

      // ── Mock ──
      await new Promise((r) => setTimeout(r, 400));
      const filtered = statusFilter === "전체" ? MOCK_GUIDES
        : MOCK_GUIDES.filter((g) => statusFilter === "복약 중" ? g.guide_status_code === "GS_ACTIVE" : g.guide_status_code === "GS_DONE");
      setGuides(filtered);
      setTodayStreak(8);
      setTodayDone(2);
      setTodayTotal(3);
      const firstActive = filtered.find((g) => g.guide_status_code === "GS_ACTIVE");
      if (firstActive) { setActiveGuideId(firstActive.guide_id); fetchMedChecks(firstActive.guide_id); }
    } catch {
      showToast("가이드 목록을 불러오지 못했습니다.", "err");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchMedChecks = async (_guideId: number) => {
    try {
      // ── 실제 API (백엔드 구현 후 주석 해제) ──
      // const today = new Date().toISOString().split("T")[0];
      // const { data } = await apiClient.get(`/api/v1/guides/${_guideId}/med-check`, { params: { check_date: today } });
      // setMedChecks(data.data ?? []);

      // ── Mock ──
      setMedChecks(MOCK_CHECKS);
    } catch {
      setMedChecks([]);
    }
  };

  useEffect(() => { fetchGuides(); }, [fetchGuides]);

  const handleCheck = async (check: MedCheck) => {
    if (!activeGuideId) return;
    setCheckLoading(check.medication_id);
    try {
      // ── 실제 API (백엔드 구현 후 주석 해제) ──
      // if (check.is_done && check.check_id) {
      //   await apiClient.delete(`/api/v1/guides/${activeGuideId}/med-check/${check.check_id}`);
      // } else {
      //   const now = new Date();
      //   await apiClient.post(`/api/v1/guides/${activeGuideId}/med-check`, {
      //     medication_id: check.medication_id,
      //     check_date: now.toISOString().split("T")[0],
      //     taken_at: now.toISOString(),
      //   });
      // }

      // ── Mock: 즉시 UI 반영 ──
      await new Promise((r) => setTimeout(r, 300));
      setMedChecks((prev) => prev.map((c) =>
        c.medication_id === check.medication_id
          ? { ...c, is_done: !c.is_done, taken_at: !c.is_done ? new Date().toISOString() : null }
          : c
      ));
      if (check.is_done) {
        showToast("복약 완료가 취소되었습니다");
      } else {
        showToast("복약 완료로 기록되었습니다 ✅");
      }
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "오류가 발생했습니다.", "err");
    } finally {
      setCheckLoading(null);
    }
  };

  const today = new Date();
  const todayStr = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일`;
  const totalPct = todayTotal > 0 ? Math.round((todayDone / todayTotal) * 100) : 0;
  const activeGuide = guides.find((g) => g.guide_id === activeGuideId);

  const timeSlotLabel: Record<string, string> = {
    morning_before: "🌅 아침 식전",
    morning_after: "🌅 아침 식후",
    evening_after: "🌆 저녁 식후",
    bedtime: "🌃 취침 전",
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 pb-24 lg:pb-8">

      {/* ── 오늘의 현황 배너 ── */}
      <div className="relative mb-6 overflow-hidden rounded-2xl border border-border bg-card p-5">
        <div className="pointer-events-none absolute left-0 right-0 top-0 h-0.5"
          style={{ background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">{todayStr}</p>
            <p className="mt-0.5 text-base font-bold text-foreground">
              오늘의 복약 현황
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {todayDone}/{todayTotal} 완료
              </span>
            </p>
          </div>
          {todayStreak > 0 && (
            <div className="flex items-center gap-1.5 rounded-xl border border-orange-500/20 bg-orange-500/8 px-3 py-1.5">
              <span className="text-base">🔥</span>
              <span className="text-sm font-bold text-orange-400">{todayStreak}일</span>
              <span className="text-xs text-muted-foreground">연속</span>
            </div>
          )}
        </div>
        <div className="mt-4">
          <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
            <span>진행률</span>
            <span className="font-medium text-foreground">{totalPct}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: `${totalPct}%`, background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }} />
          </div>
        </div>
      </div>

      {/* ── 목록 헤더 ── */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-foreground">내 가이드 목록</h1>
        <div className="flex items-center gap-2">
          {/* 기간 필터 */}
          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground focus:border-teal-500/50 focus:outline-none"
          >
            {["전체기간", "최근 1개월", "최근 3개월"].map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
          {/* 상태 필터 */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground focus:border-teal-500/50 focus:outline-none"
          >
            {["전체", "복약 중", "완료"].map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
          {/* 새 가이드 */}
          <button
            onClick={() => router.push("/guide/new")}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-teal-500"
          >
            <span>+</span> 새 가이드
          </button>
        </div>
      </div>

      {/* ── 가이드 카드 그리드 ── */}
      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
        </div>
      ) : guides.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16 text-center">
          <p className="text-4xl mb-3">💊</p>
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
            <GuideCard
              key={g.guide_id}
              guide={g}
              onClick={() => router.push(`/guide/${g.guide_id}`)}
            />
          ))}
        </div>
      )}

      {/* ── 오늘의 복약 체크 ── */}
      {activeGuide && medChecks.length > 0 && (
        <div className="mt-6 rounded-2xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">오늘의 복약 체크</p>
              <p className="mt-0.5 text-sm font-semibold text-foreground">{activeGuide.title}</p>
            </div>
            <button
              onClick={() => router.push(`/guide/${activeGuide.guide_id}`)}
              className="text-xs text-teal-400 hover:text-teal-300"
            >
              상세 보기 →
            </button>
          </div>

          <div className="space-y-2">
            {medChecks.map((chk) => {
              const isToday = chk.check_date === new Date().toISOString().split("T")[0];
              return (
                <div
                  key={chk.medication_id}
                  className={`grid items-center gap-3 rounded-xl px-4 py-3 text-sm transition-colors ${
                    chk.is_done ? "bg-teal-500/5" : "bg-muted/40"
                  }`}
                  style={{ gridTemplateColumns: "20px 1fr 110px 90px" }}
                >
                  {/* 체크 아이콘 */}
                  <span className={chk.is_done ? "text-teal-400" : "text-muted-foreground"}>
                    {chk.is_done ? "✓" : "□"}
                  </span>
                  {/* 약물명 */}
                  <span className={`font-medium ${chk.is_done ? "text-muted-foreground line-through" : "text-foreground"}`}>
                    {chk.medication_name}
                  </span>
                  {/* 시간대 */}
                  <span className="text-xs text-muted-foreground">
                    {timeSlotLabel[chk.time_slot] ?? chk.time_slot}
                  </span>
                  {/* 버튼 */}
                  {chk.is_done ? (
                    isToday ? (
                      <button
                        onClick={() => handleCheck(chk)}
                        disabled={checkLoading === chk.medication_id}
                        className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground transition hover:border-red-500/40 hover:text-red-400 disabled:opacity-40"
                      >
                        {checkLoading === chk.medication_id ? "..." : "취소"}
                      </button>
                    ) : (
                      <span className="text-right text-xs text-teal-400">
                        {chk.taken_at ? new Date(chk.taken_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }) : "완료"}
                      </span>
                    )
                  ) : (
                    <button
                      onClick={() => handleCheck(chk)}
                      disabled={checkLoading === chk.medication_id}
                      className="rounded-lg border border-teal-500/40 px-3 py-1 text-xs text-teal-400 transition hover:bg-teal-500/10 disabled:opacity-40"
                    >
                      {checkLoading === chk.medication_id ? "..." : "완료"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 면책 고지 */}
      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다.
      </p>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
