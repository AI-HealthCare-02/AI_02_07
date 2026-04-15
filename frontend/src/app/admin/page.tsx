"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/admin-api";

// ── 타입 ──────────────────────────────────────────────────
interface Dataset { label: string; data: number[]; }
interface ChartData { type: string; period: string; labels: string[]; datasets: Dataset[]; }
interface Summary {
  totalUsers: number;
  todayActiveUsers: number;
  ocrUsageCount: number;
  todayChatCount: number;
}

// ── 유틸 ──────────────────────────────────────────────────
// UTC가 아닌 로컬(KST) 기준 오늘 날짜 반환
function getLocalToday(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fmtLabel(lbl: string): string {
  if (lbl.length === 10) return lbl.slice(5);          // YYYY-MM-DD → MM-DD
  if (lbl.length === 7)  return lbl.slice(5) + "월";   // YYYY-MM    → MM월
  return lbl;                                           // YYYY
}

// ── 막대 차트 ──────────────────────────────────────────────
const BAR_H = 160; // 막대 영역 고정 높이(px)

function BarChart({ data, color }: { data: ChartData; color: string }) {
  const values = data.datasets[0]?.data ?? [];
  const max    = Math.max(...values, 1);
  const today  = getLocalToday();
  const hasData = values.some((v) => v > 0);

  // 라벨 표시 간격 계산 (최대 20개)
  const step = Math.ceil(data.labels.length / 20);

  if (!hasData) {
    return (
      <div
        className="flex items-center justify-center text-xs text-slate-500"
        style={{ height: BAR_H + 20 }}
      >
        해당 기간에 데이터가 없습니다
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="flex items-end gap-[2px]" style={{ minWidth: data.labels.length * 16, height: BAR_H + 20 }}>
        {data.labels.map((label, i) => {
          const val     = values[i] ?? 0;
          const isToday = label === today;
          // 막대 높이: 값 있으면 최소 4px 보장, 없으면 0
          const barPx   = val > 0 ? Math.max(Math.round((val / max) * BAR_H), 4) : 0;
          const showLbl = i % step === 0 || isToday;

          return (
            <div
              key={label}
              className="group relative flex flex-1 flex-col items-center justify-end"
              style={{ minWidth: 14, height: BAR_H + 20 }}
            >
              {/* hover 툴팁 */}
              {val > 0 && (
                <span className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-700 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition-opacity group-hover:opacity-100 z-10">
                  {val.toLocaleString()}
                </span>
              )}

              {/* 막대 */}
              <div
                className="w-full rounded-t transition-all duration-300"
                style={{
                  height: barPx,
                  background: isToday ? "#f59e0b" : val === 0 ? "rgba(255,255,255,0.06)" : color,
                  minHeight: val === 0 ? 2 : undefined,
                }}
                title={`${label}: ${val}`}
              />

              {/* 라벨 */}
              <span
                className={`mt-1 w-full truncate text-center text-[8px] ${
                  isToday ? "font-bold text-yellow-400" : "text-slate-500"
                }`}
                style={{ height: 16, lineHeight: "16px", visibility: showLbl ? "visible" : "hidden" }}
              >
                {fmtLabel(label)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 요약 카드 ──────────────────────────────────────────────
function SummaryCard({
  label, value, sub, color, icon,
}: {
  label: string; value: string; sub: string; color: string; icon: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-slate-400">{label}</p>
        <span className="text-xl">{icon}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{sub}</p>
    </div>
  );
}

// ── 차트 패널 ──────────────────────────────────────────────
const PERIODS = [
  { value: "DAILY",   label: "일별"  },
  { value: "MONTHLY", label: "월별"  },
  { value: "YEARLY",  label: "연별"  },
];

const CHART_CONFIGS = [
  { type: "SIGNUP",      label: "신규 가입자",   color: "#14b8a6", unit: "명" },
  { type: "CHAT_USAGE",  label: "챗봇 이용량",   color: "#818cf8", unit: "건" },
  { type: "OCR_SUCCESS", label: "의료문서 사용", color: "#34d399", unit: "건" },
];

function ChartPanel({ type, label, color, unit }: {
  type: string; label: string; color: string; unit: string;
}) {
  const [chart,   setChart]   = useState<ChartData | null>(null);
  const [period,  setPeriod]  = useState("DAILY");
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    adminApi
      .getDashboardChart({ type, period })
      .then((res) => {
        // 백엔드 응답: { status, message, data: ChartData }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = (res.data as any)?.data as ChartData | undefined;
        if (!result?.labels || !result?.datasets) {
          setError("데이터 형식 오류");
          return;
        }
        setChart(result);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, period]);

  useEffect(() => { load(); }, [load]);

  const values   = chart?.datasets[0]?.data ?? [];
  const total    = values.reduce((a, b) => a + b, 0);
  const today    = getLocalToday();
  const todayIdx = chart?.labels.findIndex((l) => l === today) ?? -1;
  const todayVal = todayIdx >= 0 ? (values[todayIdx] ?? 0) : 0;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      {/* 헤더 */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{label}</p>
          {!loading && !error && chart && (
            <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-400">
              <span>
                기간 합계{" "}
                <span className="font-medium text-white">
                  {total.toLocaleString()}{unit}
                </span>
              </span>
              {todayVal > 0 && (
                <span className="text-yellow-400">
                  오늘 {todayVal.toLocaleString()}{unit}
                </span>
              )}
            </div>
          )}
        </div>

        {/* 기간 탭 */}
        <div className="flex overflow-hidden rounded-lg border border-white/10">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                period === p.value
                  ? "bg-white/15 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 본문 */}
      {loading ? (
        <div className="animate-pulse rounded-xl bg-white/5" style={{ height: BAR_H + 20 }} />
      ) : error ? (
        <div
          className="flex items-center justify-center rounded-xl border border-red-500/20 bg-red-500/5 text-xs text-red-400"
          style={{ height: BAR_H + 20 }}
        >
          {error}
        </div>
      ) : chart ? (
        <BarChart data={chart} color={color} />
      ) : null}
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────
export default function AdminDashboardPage() {
  const [summary,        setSummary]        = useState<Summary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [summaryError,   setSummaryError]   = useState<string | null>(null);

  useEffect(() => {
    setLoadingSummary(true);
    adminApi
      .getDashboardSummary()
      .then((res) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const d = (res.data as any)?.data as Summary | undefined;
        if (!d) { setSummaryError("요약 데이터 없음"); return; }
        setSummary(d);
      })
      .catch((e: Error) => setSummaryError(e.message))
      .finally(() => setLoadingSummary(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* 타이틀 */}
      <div>
        <h1 className="text-xl font-bold text-white">대시보드</h1>
        <p className="mt-0.5 text-sm text-slate-400">서비스 현황을 한눈에 확인하세요.</p>
      </div>

      {summaryError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {summaryError}
        </div>
      )}

      {/* 요약 카드 */}
      {loadingSummary ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-white/5" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <SummaryCard label="총 가입자"         value={(summary.totalUsers        ?? 0).toLocaleString()} sub="명" color="text-teal-400"   icon="👥" />
          <SummaryCard label="오늘 활성 사용자"   value={(summary.todayActiveUsers   ?? 0).toLocaleString()} sub="명" color="text-blue-400"   icon="🟢" />
          <SummaryCard label="오늘 의료문서 사용" value={(summary.ocrUsageCount      ?? 0).toLocaleString()} sub="건" color="text-green-400"  icon="📄" />
          <SummaryCard label="오늘 챗봇 문의"     value={(summary.todayChatCount     ?? 0).toLocaleString()} sub="건" color="text-purple-400" icon="💬" />
        </div>
      ) : null}

      {/* 추이 차트 — 1열 */}
      <div className="flex flex-col gap-4">
        {CHART_CONFIGS.map((cfg) => (
          <ChartPanel
            key={cfg.type}
            type={cfg.type}
            label={cfg.label}
            color={cfg.color}
            unit={cfg.unit}
          />
        ))}
      </div>

      <p className="text-right text-[11px] text-slate-600">
        오늘 막대는 <span className="text-yellow-500">노란색</span>으로 표시됩니다
      </p>
    </div>
  );
}
