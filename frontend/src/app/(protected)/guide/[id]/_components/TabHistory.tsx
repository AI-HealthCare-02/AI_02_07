"use client";

import { useState } from "react";

type DayStatus = "done" | "partial" | "missed" | "future" | "none";

interface MedRecord {
  date: string;
  drug: string;
  time_slot: string;
  taken_at: string | null;
  status: "done" | "missed" | "pending";
}

// Mock 복약 리스트
const MOCK_RECORDS: MedRecord[] = [
  { date: "04.10", drug: "오메프라졸 20mg",    time_slot: "아침 식전", taken_at: "08:10", status: "done"    },
  { date: "04.10", drug: "아모디핀 5mg",       time_slot: "아침 식후", taken_at: "08:28", status: "done"    },
  { date: "04.10", drug: "로수바스타틴 10mg",  time_slot: "저녁 식후", taken_at: null,    status: "pending" },
  { date: "04.09", drug: "오메프라졸 20mg",    time_slot: "아침 식전", taken_at: "07:55", status: "done"    },
  { date: "04.08", drug: "오메프라졸 20mg",    time_slot: "아침 식전", taken_at: null,    status: "missed"  },
];

const STATUS_BADGE: Record<MedRecord["status"], string> = {
  done:    "bg-teal-500/15 text-teal-400",
  pending: "bg-muted/50 text-muted-foreground",
  missed:  "bg-red-500/15 text-red-400",
};
const STATUS_LABEL: Record<MedRecord["status"], string> = {
  done: "완료", pending: "대기", missed: "누락",
};

// Mock: 날짜별 상태
function getMockStatus(year: number, month: number, day: number): DayStatus {
  const today = new Date();
  const d = new Date(year, month, day);
  if (d > today) return "future";
  const seed = (year * 100 + month) * 31 + day;
  const r = seed % 4;
  if (r === 0) return "missed";
  if (r === 1) return "partial";
  return "done";
}

const STATUS_STYLE: Record<DayStatus, string> = {
  done:    "bg-teal-500/20 text-teal-300",
  partial: "bg-orange-500/15 text-orange-300",
  missed:  "bg-red-500/15 text-red-400",
  future:  "bg-muted/40 text-muted-foreground",
  none:    "",
};

const LEGEND = [
  { status: "done",    label: "완료",   color: "bg-teal-500/30"   },
  { status: "partial", label: "일부",   color: "bg-orange-500/25" },
  { status: "missed",  label: "누락",   color: "bg-red-500/20"    },
  { status: "future",  label: "예정",   color: "bg-muted/50"      },
];

export default function TabHistory({ guideId }: { guideId: number }) {
  const today = new Date();
  const [year,  setYear]  = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth()); // 0-indexed

  const firstDay   = new Date(year, month, 1).getDay(); // 0=일
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const prevMonth = () => {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  };

  // 최근 7일 이행률 (Mock)
  const recentDone  = 6;
  const recentTotal = 7;
  const recentPct   = Math.round((recentDone / recentTotal) * 100);

  return (
    <div className="space-y-4">
      {/* 이행률 요약 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">{recentPct}%</p>
          <p className="text-xs text-muted-foreground">최근 7일 복약 이행률</p>
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
        {/* 헤더 */}
        <div className="mb-4 flex items-center justify-between">
          <button onClick={prevMonth} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40">◀</button>
          <p className="text-sm font-semibold text-foreground">
            📅 {year}년 {month + 1}월
          </p>
          <button onClick={nextMonth} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40">▶</button>
        </div>

        {/* 요일 헤더 */}
        <div className="mb-2 grid grid-cols-7 text-center">
          {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
            <p key={d} className="text-[10px] font-medium text-muted-foreground py-1">{d}</p>
          ))}
        </div>

        {/* 날짜 그리드 */}
        <div className="grid grid-cols-7 gap-1">
          {/* 빈 칸 */}
          {Array.from({ length: firstDay }).map((_, i) => <div key={`e-${i}`} />)}

          {/* 날짜 */}
          {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
            const isToday =
              day === today.getDate() &&
              month === today.getMonth() &&
              year === today.getFullYear();
            const status = getMockStatus(year, month, day);

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

        {/* 범례 */}
        <div className="mt-4 flex flex-wrap gap-3 justify-center">
          {LEGEND.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className={`h-3 w-3 rounded-sm ${color}`} />
              <span className="text-[10px] text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>
      {/* 달력 아래 복약 리스트 */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-semibold text-foreground">복약 기록</p>
        </div>
        <div className="divide-y divide-border">
          {MOCK_RECORDS.map((r, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3 text-xs">
              <span className="w-10 shrink-0 text-muted-foreground">{r.date}</span>
              <span className="flex-1 font-medium text-foreground truncate">{r.drug}</span>
              <span className="shrink-0 text-muted-foreground">{r.time_slot}</span>
              <span className="w-10 shrink-0 text-center text-muted-foreground">{r.taken_at ?? "—"}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 font-medium ${STATUS_BADGE[r.status]}`}>
                {STATUS_LABEL[r.status]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
