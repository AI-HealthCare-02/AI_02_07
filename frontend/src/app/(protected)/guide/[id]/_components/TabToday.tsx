"use client";

import { useState } from "react";
// import apiClient from "@/lib/axios";

interface MedCheck {
  check_id: number;
  medication_id: number;
  medication_name: string;
  time_slot: string;
  taken_at: string | null;
  check_date: string;
  is_done: boolean;
}

const TIME_SLOT_LABEL: Record<string, string> = {
  morning_before: "🌅 아침 식전",
  morning_after:  "🌅 아침 식후",
  evening_after:  "🌆 저녁 식후",
  bedtime:        "🌃 취침 전",
};

const MOCK_CHECKS: MedCheck[] = [
  { check_id: 1, medication_id: 1, medication_name: "오메프라졸캡슐 20mg",  time_slot: "morning_before", taken_at: "2026-04-10T08:15:00", check_date: new Date().toISOString().split("T")[0], is_done: true  },
  { check_id: 0, medication_id: 2, medication_name: "아모디핀정 5mg",       time_slot: "morning_after",  taken_at: null,                  check_date: new Date().toISOString().split("T")[0], is_done: false },
  { check_id: 0, medication_id: 3, medication_name: "로수바스타틴정 10mg",  time_slot: "evening_after",  taken_at: null,                  check_date: new Date().toISOString().split("T")[0], is_done: false },
];

export default function TabToday({
  guideId,
  showToast,
}: {
  guideId: number;
  showToast: (msg: string, type?: "ok" | "err") => void;
}) {
  const [checks, setChecks] = useState<MedCheck[]>(MOCK_CHECKS);
  const [loading, setLoading] = useState<number | null>(null);
  const today = new Date().toISOString().split("T")[0];
  const done  = checks.filter((c) => c.is_done).length;
  const total = checks.length;
  const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

  const handleCheck = async (chk: MedCheck) => {
    setLoading(chk.medication_id);
    try {
      // ── 실제 API ──
      // if (chk.is_done && chk.check_id) {
      //   await apiClient.delete(`/api/v1/guides/${guideId}/med-check/${chk.check_id}`);
      // } else {
      //   const now = new Date();
      //   await apiClient.post(`/api/v1/guides/${guideId}/med-check`, {
      //     medication_id: chk.medication_id,
      //     check_date: today,
      //     taken_at: now.toISOString(),
      //   });
      // }

      // ── Mock ──
      await new Promise((r) => setTimeout(r, 300));
      setChecks((prev) =>
        prev.map((c) =>
          c.medication_id === chk.medication_id
            ? { ...c, is_done: !c.is_done, taken_at: !c.is_done ? new Date().toISOString() : null }
            : c
        )
      );
      showToast(chk.is_done ? "복약 완료가 취소되었습니다" : "복약 완료로 기록되었습니다 ✅");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "오류가 발생했습니다.", "err");
    } finally {
      setLoading(null);
    }
  };

  const todayLabel = (() => {
    const d = new Date();
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  })();

  return (
    <div className="space-y-4">
      {/* 날짜 + 진행률 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">{todayLabel}</p>
          <span className="text-xs text-muted-foreground">{done}/{total} 완료</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${pct}%`, background: "linear-gradient(90deg, #14b8a6, #06b6d4)" }}
          />
        </div>
        <p className="mt-1.5 text-right text-xs font-medium text-teal-400">{pct}%</p>
      </div>

      {/* 복약 목록 */}
      <div className="divide-y divide-border rounded-2xl border border-border bg-card overflow-hidden">
        {checks.map((chk) => {
          const isToday = chk.check_date === today;
          return (
            <div
              key={chk.medication_id}
              className={`flex items-center gap-3 px-4 py-3.5 transition-colors ${chk.is_done ? "bg-teal-500/5" : ""}`}
            >
              <span className={`text-lg ${chk.is_done ? "text-teal-400" : "text-muted-foreground"}`}>
                {chk.is_done ? "✅" : "⬜"}
              </span>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${chk.is_done ? "text-muted-foreground line-through" : "text-foreground"}`}>
                  {chk.medication_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {TIME_SLOT_LABEL[chk.time_slot] ?? chk.time_slot}
                  {chk.is_done && chk.taken_at && (
                    <span className="ml-2 text-teal-400">
                      {new Date(chk.taken_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                </p>
              </div>
              {chk.is_done ? (
                isToday ? (
                  <button
                    onClick={() => handleCheck(chk)}
                    disabled={loading === chk.medication_id}
                    className="shrink-0 rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground transition hover:border-red-500/40 hover:text-red-400 disabled:opacity-40"
                  >
                    {loading === chk.medication_id ? "..." : "취소"}
                  </button>
                ) : (
                  <span className="shrink-0 text-xs text-teal-400">완료</span>
                )
              ) : (
                <button
                  onClick={() => handleCheck(chk)}
                  disabled={loading === chk.medication_id}
                  className="shrink-0 rounded-lg border border-teal-500/40 px-3 py-1 text-xs text-teal-400 transition hover:bg-teal-500/10 disabled:opacity-40"
                >
                  {loading === chk.medication_id ? "..." : "복약 완료"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
