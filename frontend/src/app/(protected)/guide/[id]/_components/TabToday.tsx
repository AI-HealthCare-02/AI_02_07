"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

interface MedCheckItem {
  check_id: number | null;
  guide_medication_id: number;
  medication_name: string;
  timing: string | null;
  timing_slot: string;
  slot_label: string;
  is_taken: boolean;
  taken_at: string | null;
}

// 시간대 고정 순서 (daily_slots 미설정 시 폴백값 포함)
const SLOT_ORDER = ["아침", "점심", "저녁", "취침전", "1회차", "2회차", "3회차"];

const SLOT_ICON: Record<string, string> = {
  아침: "🌅",
  점심: "☀️",
  저녁: "🌙",
  취침전: "🌜",
  "1회차": "1️⃣",
  "2회차": "2️⃣",
  "3회차": "3️⃣",
};

export default function TabToday({
  guideId,
  showToast,
}: {
  guideId: number;
  showToast: (msg: string, type?: "ok" | "err") => void;
}) {
  const [items, setItems] = useState<MedCheckItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null); // `${guide_medication_id}-${timing_slot}`
  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}/med-check`)
      .then(({ data }) => setItems(data.items ?? []))
      .catch(() => showToast("복약 현황을 불러오지 못했습니다.", "err"))
      .finally(() => setLoading(false));
  }, [guideId]); // eslint-disable-line react-hooks/exhaustive-deps

  const busyKey = (item: MedCheckItem) =>
    `${item.guide_medication_id}-${item.timing_slot}`;

  const handleCheck = async (item: MedCheckItem) => {
    setBusy(busyKey(item));
    try {
      if (item.is_taken && item.check_id) {
        await apiClient.delete(
          `/api/v1/guides/${guideId}/med-check/${item.check_id}`
        );
        setItems((prev) =>
          prev.map((c) =>
            c.guide_medication_id === item.guide_medication_id &&
            c.timing_slot === item.timing_slot
              ? { ...c, is_taken: false, check_id: null, taken_at: null }
              : c
          )
        );
        showToast("복약 완료가 취소되었습니다.");
      } else {
        const { data } = await apiClient.post(
          `/api/v1/guides/${guideId}/med-check`,
          {
            guide_medication_id: item.guide_medication_id,
            check_date: today,
            timing_slot: item.timing_slot,
          }
        );
        setItems((prev) =>
          prev.map((c) =>
            c.guide_medication_id === item.guide_medication_id &&
            c.timing_slot === item.timing_slot
              ? {
                  ...c,
                  is_taken: true,
                  check_id: data.check_id,
                  taken_at: data.taken_at,
                }
              : c
          )
        );
        showToast("복약 완료로 기록되었습니다 ✅");
      }
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "오류가 발생했습니다.", "err");
    } finally {
      setBusy(null);
    }
  };

  // 전체 진행률
  const done = items.filter((c) => c.is_taken).length;
  const total = items.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  // slot_label 기준 그룹핑
  const grouped = items.reduce<Record<string, MedCheckItem[]>>((acc, item) => {
    const label = item.slot_label || "기타";
    if (!acc[label]) acc[label] = [];
    acc[label].push(item);
    return acc;
  }, {});

  // SLOT_ORDER 기준 정렬 + 미포함 라벨은 뒤에 추가
  const orderedKeys = [
    ...SLOT_ORDER.filter((k) => grouped[k]),
    ...Object.keys(grouped).filter((k) => !SLOT_ORDER.includes(k)),
  ];

  const todayLabel = (() => {
    const d = new Date();
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  })();

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 날짜 + 전체 진행률 */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">{todayLabel}</p>
          <span className="text-xs text-muted-foreground">
            {done}/{total} 완료
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${pct}%`,
              background: "linear-gradient(90deg, #14b8a6, #06b6d4)",
            }}
          />
        </div>
        <p className="mt-1.5 text-right text-xs font-medium text-teal-400">
          {pct}%
        </p>
      </div>

      {/* 복약 목록 */}
      {items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          등록된 약물이 없습니다.
        </p>
      ) : (
        <div className="space-y-3">
          {orderedKeys.map((slotLabel) => {
            const slotItems = grouped[slotLabel];
            const slotDone = slotItems.filter((i) => i.is_taken).length;
            const slotTotal = slotItems.length;
            const slotPct =
              slotTotal > 0 ? Math.round((slotDone / slotTotal) * 100) : 0;
            const allDone = slotDone === slotTotal;

            return (
              <section key={slotLabel}>
                {/* 섹션 헤더 */}
                <div className="mb-2 flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base">
                      {SLOT_ICON[slotLabel] ?? "💊"}
                    </span>
                    <span
                      className={`text-sm font-semibold ${
                        allDone ? "text-teal-400" : "text-foreground"
                      }`}
                    >
                      {slotLabel}
                    </span>
                    {allDone && (
                      <span className="rounded-full bg-teal-500/15 px-2 py-0.5 text-[10px] font-medium text-teal-400">
                        완료
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {slotDone}/{slotTotal} · {slotPct}%
                  </span>
                </div>

                {/* 섹션 진행 바 */}
                <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-muted px-1">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${slotPct}%`,
                      background: allDone
                        ? "#14b8a6"
                        : "linear-gradient(90deg, #14b8a6, #06b6d4)",
                    }}
                  />
                </div>

                {/* 약물 카드 목록 */}
                <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
                  {slotItems.map((item) => (
                    <div
                      key={`${item.guide_medication_id}-${item.timing_slot}`}
                      className={`flex items-center gap-3 px-4 py-3.5 transition-colors ${
                        item.is_taken ? "bg-teal-500/5" : ""
                      }`}
                    >
                      <span
                        className={`text-lg ${
                          item.is_taken
                            ? "text-teal-400"
                            : "text-muted-foreground"
                        }`}
                      >
                        {item.is_taken ? "✅" : "⬜"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p
                          className={`truncate text-sm font-medium ${
                            item.is_taken
                              ? "text-muted-foreground line-through"
                              : "text-foreground"
                          }`}
                        >
                          {item.medication_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {item.timing ?? "복용 시점 미지정"}
                          {item.is_taken && item.taken_at && (
                            <span className="ml-2 text-teal-400">
                              {new Date(item.taken_at).toLocaleTimeString(
                                "ko-KR",
                                { hour: "2-digit", minute: "2-digit" }
                              )}
                            </span>
                          )}
                        </p>
                      </div>
                      {item.is_taken ? (
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span className="text-xs font-medium text-teal-400">
                            완료 ✓
                          </span>
                          <button
                            onClick={() => handleCheck(item)}
                            disabled={busy === busyKey(item)}
                            className="rounded-lg border border-border px-2 py-1 text-xs text-muted-foreground transition hover:border-red-500/40 hover:text-red-400 disabled:opacity-40"
                          >
                            {busy === busyKey(item) ? "..." : "취소"}
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleCheck(item)}
                          disabled={busy === busyKey(item)}
                          className="shrink-0 rounded-lg border border-teal-500/40 px-3 py-1 text-xs text-teal-400 transition hover:bg-teal-500/10 disabled:opacity-40"
                        >
                          {busy === busyKey(item) ? "..." : "복약하기"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
