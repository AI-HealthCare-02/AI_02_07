"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

type DayStatus = "done" | "partial" | "missed" | "future";

interface DayItem { date: string; status: DayStatus; }

interface HistoryItem {
  check_id: number;
  guide_medication_id: number;
  medication_name: string;
  timing_slot: string;
  slot_label: string;
  check_date: string;
  is_taken: boolean;
  taken_at: string | null;
}

interface HistoryPage {
  total_count: number;
  page: number;
  size: number;
  items: HistoryItem[];
}

const STATUS_STYLE: Record<DayStatus, string> = {
  done:    "bg-teal-500/20 text-teal-300",
  partial: "bg-orange-500/15 text-orange-300",
  missed:  "bg-red-500/15 text-red-400",
  future:  "bg-muted/40 text-muted-foreground",
};

const LEGEND = [
  { status: "done",    label: "완료", color: "bg-teal-500/30"   },
  { status: "partial", label: "일부", color: "bg-orange-500/25" },
  { status: "missed",  label: "누락", color: "bg-red-500/20"    },
  { status: "future",  label: "예정", color: "bg-muted/50"      },
];

export default function TabHistory({ guideId }: { guideId: number }) {
  const today = new Date();
  const [year,  setYear]  = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth()); // 0-indexed
  const [days,  setDays]  = useState<DayItem[]>([]);
  const [loading, setLoading] = useState(true);

  // 히스토리 페이징
  const [histPage, setHistPage] = useState(1);
  const [histData, setHistData] = useState<HistoryPage | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const HIST_SIZE = 20;

  useEffect(() => {
    setHistLoading(true);
    apiClient
      .get(`/api/v1/guides/${guideId}/med-check/history?page=${histPage}&size=${HIST_SIZE}`)
      .then(({ data }) => setHistData(data))
      .catch(() => {})
      .finally(() => setHistLoading(false));
  }, [guideId, histPage]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLoading(true);
    apiClient
      .get(`/api/v1/guides/${guideId}/med-check/monthly?year=${year}&month=${month + 1}`)
      .then(({ data }) => setDays(data.days ?? []))
      .catch(() => setDays([]))
      .finally(() => setLoading(false));
  }, [guideId, year, month]);

  const prevMonth = () => { if (month === 0) { setYear((y) => y - 1); setMonth(11); } else setMonth((m) => m - 1); };
  const nextMonth = () => { if (month === 11) { setYear((y) => y + 1); setMonth(0); } else setMonth((m) => m + 1); };

  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const doneDays    = days.filter((d) => d.status === "done").length;
  const totalPast   = days.filter((d) => d.status !== "future").length;
  const recentPct   = totalPast > 0 ? Math.round((doneDays / totalPast) * 100) : 0;

  const getStatus = (day: number): DayStatus => {
    const d = days.find((x) => new Date(x.date).getDate() === day);
    return d?.status ?? "future";
  };

  return (
    <div className="space-y-4">
      {/* 이행률 요약 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">{recentPct}%</p>
          <p className="text-xs text-muted-foreground">이번 달 복약 이행률</p>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${recentPct}%`, background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }}
          />
        </div>
      </div>

      {/* 달력 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-4 flex items-center justify-between">
          <button onClick={prevMonth} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40">◀</button>
          <p className="text-sm font-semibold text-foreground">📅 {year}년 {month + 1}월</p>
          <button onClick={nextMonth} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40">▶</button>
        </div>

        <div className="mb-2 grid grid-cols-7 text-center">
          {["일","월","화","수","목","금","토"].map((d) => (
            <p key={d} className="text-[10px] font-medium text-muted-foreground py-1">{d}</p>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: firstDay }).map((_, i) => <div key={`e-${i}`} />)}
            {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
              const isToday = day === today.getDate() && month === today.getMonth() && year === today.getFullYear();
              const status  = getStatus(day);
              return (
                <div
                  key={day}
                  className={`flex aspect-square items-center justify-center rounded-lg text-xs font-medium transition ${STATUS_STYLE[status]} ${
                    isToday ? "ring-2 ring-teal-400 ring-offset-1 ring-offset-card" : ""
                  }`}
                >
                  {day}
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-3 justify-center">
          {LEGEND.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className={`h-3 w-3 rounded-sm ${color}`} />
              <span className="text-[10px] text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 복약 기록 히스토리 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold text-foreground">📋 복약 기록</p>
        {histLoading ? (
          <div className="flex justify-center py-6">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : !histData || histData.items.length === 0 ? (
          <p className="py-4 text-center text-xs text-muted-foreground">기록이 없습니다.</p>
        ) : (
          <>
            <div className="divide-y divide-border">
              {histData.items.map((item) => (
                <div key={item.check_id} className="flex items-center gap-3 py-2.5">
                  <span className={`text-base ${item.is_taken ? "text-teal-400" : "text-muted-foreground"}`}>
                    {item.is_taken ? "✅" : "⬜"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm text-foreground">{item.medication_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.check_date} · {item.slot_label}
                      {item.taken_at && (
                        <span className="ml-1.5 text-teal-400">
                          {new Date(item.taken_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            {/* 페이지 버튼 */}
            {histData.total_count > HIST_SIZE && (
              <div className="mt-3 flex items-center justify-between">
                <button
                  onClick={() => setHistPage((p) => Math.max(1, p - 1))}
                  disabled={histPage === 1}
                  className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  ◀ 이전
                </button>
                <span className="text-xs text-muted-foreground">
                  {histPage} / {Math.ceil(histData.total_count / HIST_SIZE)}
                </span>
                <button
                  onClick={() => setHistPage((p) => p + 1)}
                  disabled={histPage * HIST_SIZE >= histData.total_count}
                  className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  다음 ▶
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
