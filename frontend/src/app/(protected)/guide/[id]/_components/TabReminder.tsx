"use client";

import { useState } from "react";
// import apiClient from "@/lib/axios";

interface Reminder {
  reminder_id: number;
  alias: string;
  reminder_time: string;
  repeat_type_code: string;
  is_active: boolean;
  medication_names: string[];
}

const REPEAT_LABEL: Record<string, string> = {
  RPT_DAILY:   "매일",
  RPT_WEEKDAY: "평일",
  RPT_CUSTOM:  "사용자 지정",
};

const MOCK_REMINDERS: Reminder[] = [
  { reminder_id: 1, alias: "아침 혈압약", reminder_time: "07:50", repeat_type_code: "RPT_DAILY", is_active: true,  medication_names: ["오메프라졸캡슐 20mg", "아모디핀정 5mg"] },
  { reminder_id: 2, alias: "저녁 콜레스테롤약", reminder_time: "19:00", repeat_type_code: "RPT_DAILY", is_active: false, medication_names: ["로수바스타틴정 10mg"] },
];

const MOCK_MEDS = [
  { id: 1, name: "오메프라졸캡슐 20mg", time_slot: "아침 식전" },
  { id: 2, name: "아모디핀정 5mg",      time_slot: "아침 식후" },
  { id: 3, name: "로수바스타틴정 10mg", time_slot: "저녁 식후" },
];

export default function TabReminder({
  guideId,
  showToast,
}: {
  guideId: number;
  showToast: (msg: string, type?: "ok" | "err") => void;
}) {
  const [kakaoEnabled, setKakaoEnabled] = useState(true);
  const [reminders, setReminders]       = useState<Reminder[]>(MOCK_REMINDERS);
  const [showForm, setShowForm]         = useState(false);
  const [form, setForm] = useState({
    alias: "", reminder_time: "08:00",
    repeat_type_code: "RPT_DAILY", medication_ids: [] as number[],
  });

  const toggleKakao = () => {
    setKakaoEnabled((p) => !p);
    showToast(kakaoEnabled ? "카카오 알림톡 수신이 비활성화되었습니다." : "카카오 알림톡 수신이 활성화되었습니다.");
  };

  const toggleReminder = async (id: number) => {
    // await apiClient.patch(`/api/v1/guides/${guideId}/reminder/${id}`, { is_active: !cur.is_active });
    setReminders((p) => p.map((r) => r.reminder_id === id ? { ...r, is_active: !r.is_active } : r));
  };

  const deleteReminder = async (id: number) => {
    // await apiClient.delete(`/api/v1/guides/${guideId}/reminder/${id}`);
    setReminders((p) => p.filter((r) => r.reminder_id !== id));
    showToast("알림이 삭제되었습니다.");
  };

  const saveReminder = async () => {
    if (form.medication_ids.length === 0) { showToast("대상 약물을 1개 이상 선택하세요.", "err"); return; }
    // await apiClient.post(`/api/v1/guides/${guideId}/reminder`, form);
    const newR: Reminder = {
      reminder_id: Date.now(),
      alias: form.alias || form.reminder_time,
      reminder_time: form.reminder_time,
      repeat_type_code: form.repeat_type_code,
      is_active: true,
      medication_names: MOCK_MEDS.filter((m) => form.medication_ids.includes(m.id)).map((m) => m.name),
    };
    setReminders((p) => [...p, newR]);
    setShowForm(false);
    setForm({ alias: "", reminder_time: "08:00", repeat_type_code: "RPT_DAILY", medication_ids: [] });
    showToast("알림이 저장되었습니다.");
  };

  const toggleMedId = (id: number) =>
    setForm((p) => ({
      ...p,
      medication_ids: p.medication_ids.includes(id)
        ? p.medication_ids.filter((x) => x !== id)
        : [...p.medication_ids, id],
    }));

  return (
    <div className="space-y-4">
      {/* 카카오 알림톡 전체 토글 */}
      <div className="flex items-center justify-between rounded-2xl border border-border bg-card px-4 py-3.5">
        <div>
          <p className="text-sm font-semibold text-foreground">💬 카카오 알림톡 수신</p>
          <p className="text-xs text-muted-foreground">설정 시각에 자동 발송</p>
        </div>
        <button
          onClick={toggleKakao}
          className={`relative h-6 w-11 rounded-full transition-colors ${kakaoEnabled ? "bg-teal-500" : "bg-muted"}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${kakaoEnabled ? "translate-x-5" : "translate-x-0.5"}`} />
        </button>
      </div>

      {/* 알림 목록 헤더 */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">알림 목록</p>
        <button
          onClick={() => setShowForm((p) => !p)}
          className="rounded-xl border border-teal-500/40 px-3 py-1.5 text-xs text-teal-400 transition hover:bg-teal-500/10"
        >
          + 알림 추가
        </button>
      </div>

      {/* 알림 추가 폼 */}
      {showForm && (
        <div className="rounded-2xl border border-teal-500/20 bg-teal-500/5 p-4 space-y-3">
          <p className="text-xs font-semibold text-teal-400">새 알림 설정</p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">별칭 (선택)</label>
              <input
                value={form.alias}
                onChange={(e) => setForm((p) => ({ ...p, alias: e.target.value }))}
                placeholder="아침 혈압약"
                className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">알림 시각</label>
              <input
                type="time"
                value={form.reminder_time}
                onChange={(e) => setForm((p) => ({ ...p, reminder_time: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted-foreground">반복</label>
            <select
              value={form.repeat_type_code}
              onChange={(e) => setForm((p) => ({ ...p, repeat_type_code: e.target.value }))}
              className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
            >
              {Object.entries(REPEAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>

          {/* 대상 약물 표 */}
          <div>
            <label className="mb-1.5 block text-xs text-muted-foreground">대상 약물</label>
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="w-10 px-3 py-2 text-left text-muted-foreground">선택</th>
                    <th className="px-3 py-2 text-left text-muted-foreground">약물명</th>
                    <th className="px-3 py-2 text-left text-muted-foreground">복용 시점</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {MOCK_MEDS.map((m) => (
                    <tr key={m.id} className="hover:bg-muted/20">
                      <td className="px-3 py-2.5">
                        <input
                          type="checkbox"
                          checked={form.medication_ids.includes(m.id)}
                          onChange={() => toggleMedId(m.id)}
                          className="accent-teal-500"
                        />
                      </td>
                      <td className="px-3 py-2.5 font-medium text-foreground">{m.name}</td>
                      <td className="px-3 py-2.5 text-muted-foreground">{m.time_slot}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowForm(false)} className="flex-1 rounded-xl border border-border py-2 text-xs text-muted-foreground hover:text-foreground">취소</button>
            <button onClick={saveReminder} className="flex-1 rounded-xl bg-teal-600 py-2 text-xs font-semibold text-white hover:bg-teal-500">저장</button>
          </div>
        </div>
      )}

      {/* 알림 카드 목록 */}
      <div className="space-y-3" style={{ opacity: kakaoEnabled ? 1 : 0.4, transition: "opacity 0.3s" }}>
        {reminders.map((r) => (
          <div
            key={r.reminder_id}
            className={`rounded-2xl border bg-card p-4 transition-opacity ${r.is_active ? "border-border" : "border-border/50 opacity-60"}`}
            style={{ borderLeftWidth: 3, borderLeftColor: r.is_active ? "#14b8a6" : "rgba(255,255,255,0.1)" }}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {r.alias || r.reminder_time}
                </p>
                <p className="text-xs text-muted-foreground">
                  {r.medication_names.join(" · ")}
                  <span className="ml-2">⏰ {r.reminder_time}</span>
                  <span className="ml-2">🔄 {REPEAT_LABEL[r.repeat_type_code] ?? r.repeat_type_code}</span>
                </p>
              </div>
              <button
                onClick={() => toggleReminder(r.reminder_id)}
                className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${r.is_active ? "bg-teal-500" : "bg-muted"}`}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${r.is_active ? "translate-x-4" : "translate-x-0.5"}`} />
              </button>
            </div>
            <div className="flex gap-2">
              <button className="text-xs text-muted-foreground hover:text-teal-400">✏️ 수정</button>
              <button onClick={() => deleteReminder(r.reminder_id)} className="text-xs text-muted-foreground hover:text-red-400">🗑 삭제</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
