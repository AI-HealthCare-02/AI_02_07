"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

interface Medication {
  guide_medication_id: number;
  medication_name: string;
  timing: string | null;
}

interface Reminder {
  reminder_id: number;
  reminder_time: string;
  repeat_type: string;
  custom_days: number[] | null;
  is_browser_noti: boolean;
  is_email_noti: boolean;
  is_kakao_noti: boolean;
  is_active: boolean;
}

const REPEAT_LABEL: Record<string, string> = {
  RPT_DAILY:   "매일",
  RPT_WEEKDAY: "평일",
  RPT_CUSTOM:  "사용자 지정",
};

export default function TabReminder({
  guideId,
  showToast,
  medications,
  isKakaoUser = false,
}: {
  guideId: number;
  showToast: (msg: string, type?: "ok" | "err") => void;
  medications: Medication[];
  isKakaoUser?: boolean;
}) {
  const [reminder, setReminder] = useState<Reminder | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [form, setForm] = useState({
    reminder_time: "08:00",
    repeat_type: "RPT_DAILY",
    is_browser_noti: false,
    is_email_noti: false,
    is_kakao_noti: false,
  });

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}/reminder`)
      .then(({ data }) => setReminder({
        ...data,
        reminder_time: String(data.reminder_time).slice(0, 5),
        is_kakao_noti: data.is_kakao_noti ?? false,
      }))
      .catch(() => setReminder(null))
      .finally(() => setLoading(false));
  }, [guideId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (reminder) {
        const { data } = await apiClient.patch(`/api/v1/guides/${guideId}/reminder`, form);
        setReminder((prev) => prev ? { ...prev, ...data, is_kakao_noti: data.is_kakao_noti ?? form.is_kakao_noti } : data);
        showToast("알림이 수정되었습니다.");
      } else {
        const { data } = await apiClient.post(`/api/v1/guides/${guideId}/reminder`, form);
        setReminder({ ...form, reminder_id: data.reminder_id, custom_days: null, is_active: true });
        showToast("알림이 등록되었습니다.");
      }
      setShowForm(false);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "저장에 실패했습니다.", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async () => {
    if (!reminder) return;
    try {
      await apiClient.patch(`/api/v1/guides/${guideId}/reminder`, { is_active: !reminder.is_active });
      setReminder((prev) => prev ? { ...prev, is_active: !prev.is_active } : prev);
      showToast(reminder.is_active ? "알림이 비활성화되었습니다." : "알림이 활성화되었습니다.");
    } catch {
      showToast("변경에 실패했습니다.", "err");
    }
  };

  const handleDelete = async () => {
    if (!reminder) return;
    try {
      await apiClient.delete(`/api/v1/guides/${guideId}/reminder`);
      setReminder(null);
      showToast("알림이 삭제되었습니다.");
    } catch {
      showToast("삭제에 실패했습니다.", "err");
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><span className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" /></div>;
  }

  return (
    <div className="space-y-4">
      {/* 등록된 알림 */}
      {reminder ? (
        <div
          className={`rounded-2xl border bg-card p-4 transition-opacity ${reminder.is_active ? "border-border" : "border-border/50 opacity-60"}`}
          style={{ borderLeftWidth: 3, borderLeftColor: reminder.is_active ? "#14b8a6" : "rgba(255,255,255,0.1)" }}
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-foreground">⏰ {reminder.reminder_time}</p>
              <p className="text-xs text-muted-foreground">
                {REPEAT_LABEL[reminder.repeat_type] ?? reminder.repeat_type}
                {reminder.is_browser_noti && " · 브라우저 알림"}
                {reminder.is_email_noti   && " · 이메일 알림"}
                {reminder.is_kakao_noti   && " · 카카오 알림"}
              </p>
            </div>
            <button
              onClick={handleToggle}
              className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${reminder.is_active ? "bg-teal-500" : "bg-muted"}`}
            >
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${reminder.is_active ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
          </div>
          <div className="flex gap-3">
            <button onClick={() => { setForm({ reminder_time: reminder.reminder_time.slice(0, 5), repeat_type: reminder.repeat_type, is_browser_noti: reminder.is_browser_noti, is_email_noti: reminder.is_email_noti, is_kakao_noti: reminder.is_kakao_noti }); setShowForm(true); }} className="text-xs text-muted-foreground hover:text-teal-400">✏️ 수정</button>
            <button onClick={handleDelete} className="text-xs text-muted-foreground hover:text-red-400">🗑 삭제</button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">등록된 복약 알림이 없습니다.</p>
        </div>
      )}

      {/* 추가/수정 버튼 */}
      {!showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="w-full rounded-xl border border-teal-500/40 py-2.5 text-xs text-teal-400 transition hover:bg-teal-500/10"
        >
          {reminder ? "✏️ 알림 수정" : "+ 알림 등록"}
        </button>
      )}

      {/* 폼 */}
      {showForm && (
        <div className="rounded-2xl border border-teal-500/20 bg-teal-500/5 p-4 space-y-3">
          <p className="text-xs font-semibold text-teal-400">{reminder ? "알림 수정" : "새 알림 설정"}</p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">알림 시각</label>
              <input
                type="time"
                value={form.reminder_time}
                onChange={(e) => setForm((p) => ({ ...p, reminder_time: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">반복</label>
              <select
                value={form.repeat_type}
                onChange={(e) => setForm((p) => ({ ...p, repeat_type: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              >
                {Object.entries(REPEAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input type="checkbox" checked={form.is_browser_noti} onChange={(e) => setForm((p) => ({ ...p, is_browser_noti: e.target.checked }))} className="accent-teal-500" />
              브라우저 알림
            </label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input type="checkbox" checked={form.is_email_noti} onChange={(e) => setForm((p) => ({ ...p, is_email_noti: e.target.checked }))} className="accent-teal-500" />
              이메일 알림
            </label>
            <label className={`flex items-center gap-2 text-xs cursor-pointer ${isKakaoUser ? "text-muted-foreground" : "text-muted-foreground/40"}`}>
              <input
                type="checkbox"
                checked={form.is_kakao_noti}
                disabled={!isKakaoUser}
                onChange={(e) => setForm((p) => ({ ...p, is_kakao_noti: e.target.checked }))}
                className="accent-teal-500 disabled:cursor-not-allowed"
              />
              카카오 알림
              {!isKakaoUser && (
                <span className="text-[10px] text-muted-foreground/50">(카카오 로그인 전용)</span>
              )}
            </label>
          </div>

          {/* 대상 약물 표시 (읽기 전용) */}
          {medications.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs text-muted-foreground">대상 약물</p>
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/30">
                      <th className="px-3 py-2 text-left text-muted-foreground">약물명</th>
                      <th className="px-3 py-2 text-left text-muted-foreground">복용 시점</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {medications.map((m) => (
                      <tr key={m.guide_medication_id}>
                        <td className="px-3 py-2.5 font-medium text-foreground">{m.medication_name}</td>
                        <td className="px-3 py-2.5 text-muted-foreground">{m.timing ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowForm(false)} className="flex-1 rounded-xl border border-border py-2 text-xs text-muted-foreground hover:text-foreground">취소</button>
            <button onClick={handleSave} disabled={saving} className="flex-1 rounded-xl bg-teal-600 py-2 text-xs font-semibold text-white hover:bg-teal-500 disabled:opacity-50">
              {saving ? "저장 중..." : "저장"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
