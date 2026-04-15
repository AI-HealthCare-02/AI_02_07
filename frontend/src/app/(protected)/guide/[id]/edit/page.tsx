"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
// import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
interface MedInput {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  duration_days: string;
  time_slot: string;
}

const TIME_SLOTS = [
  { value: "morning_before", label: "아침 식전" },
  { value: "morning_after",  label: "아침 식후" },
  { value: "evening_after",  label: "저녁 식후" },
  { value: "bedtime",        label: "취침 전"   },
];

// ── Mock 초기값 ────────────────────────────────────────────
const MOCK_INIT = {
  title:          "고혈압·고지혈증 관리 가이드",
  visit_date:     "2026-03-20",
  hospital_name:  "서울대학교병원",
  department:     "내과",
  diagnoses:      ["고혈압", "고지혈증"],
  memo:           "",
  med_start_date: "2026-03-20",
  duration_days:  "30",
  guide_status:   "GS_ACTIVE",
  diseases:       ["고혈압"],
  allergies:      [] as string[],
  meds: [
    { id: "1", name: "오메프라졸캡슐 20mg",  dosage: "1캡슐", frequency: "1회", duration_days: "30", time_slot: "morning_before" },
    { id: "2", name: "아모디핀정 5mg",       dosage: "1정",   frequency: "1회", duration_days: "30", time_slot: "morning_after"  },
    { id: "3", name: "로수바스타틴정 10mg",  dosage: "1정",   frequency: "1회", duration_days: "30", time_slot: "evening_after"  },
  ] as MedInput[],
};

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

function TagInput({
  label, tags, onAdd, onRemove,
}: { label: string; tags: string[]; onAdd: (v: string) => void; onRemove: (v: string) => void }) {
  const [input, setInput] = useState("");
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</label>
      <div className="flex min-h-[44px] flex-wrap gap-2 rounded-xl border border-input bg-background px-3 py-2">
        {tags.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded-full bg-teal-500/15 px-2.5 py-0.5 text-xs font-medium text-teal-400">
            {t}
            <button onClick={() => onRemove(t)} className="opacity-60 hover:opacity-100">×</button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const v = input.trim();
              if (v && !tags.includes(v)) { onAdd(v); setInput(""); }
            }
          }}
          placeholder={tags.length === 0 ? "입력 후 Enter..." : ""}
          className="min-w-[120px] flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
      </div>
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────
export default function GuideEditPage() {
  const router  = useRouter();
  const params  = useParams();
  const guideId = Number(params.id);

  const [form, setForm] = useState({ ...MOCK_INIT, meds: MOCK_INIT.meds.map((m) => ({ ...m })) });
  const [saving, setSaving] = useState(false);
  const [toast, setToast]   = useState<{ msg: string; type: "ok" | "err" } | null>(null);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  // ── 약물 ──
  const addMed = () =>
    setForm((p) => ({
      ...p,
      meds: [...p.meds, { id: crypto.randomUUID(), name: "", dosage: "1정", frequency: "1회", duration_days: "30", time_slot: "morning_after" }],
    }));

  const removeMed = (id: string) => {
    if (form.meds.length <= 1) { showToast("약물은 최소 1개 이상 필요합니다.", "err"); return; }
    setForm((p) => ({ ...p, meds: p.meds.filter((m) => m.id !== id) }));
  };

  const updateMed = (id: string, field: keyof MedInput, value: string) =>
    setForm((p) => ({ ...p, meds: p.meds.map((m) => m.id === id ? { ...m, [field]: value } : m) }));

  // ── 저장 ──
  const handleSave = async () => {
    if (!form.title.trim()) { showToast("가이드 제목을 입력해주세요.", "err"); return; }
    setSaving(true);
    try {
      // await apiClient.patch(`/api/v1/guides/${guideId}`, { ... });
      await new Promise((r) => setTimeout(r, 500));
      showToast("가이드가 수정되었습니다 ✅");
      setTimeout(() => router.push(`/guide/${guideId}`), 800);
    } catch {
      showToast("저장에 실패했습니다.", "err");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">✏️ 가이드 수정</h1>
        <button onClick={() => router.push(`/guide/${guideId}`)} className="text-xs text-muted-foreground hover:text-foreground">
          ← 취소하고 돌아가기
        </button>
      </div>

      <div className="space-y-5">
        {/* 기본 정보 */}
        <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
          <p className="text-sm font-semibold text-foreground">기본 정보</p>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              가이드 제목 <span className="text-red-400">*</span>
            </label>
            <input
              value={form.title}
              onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
              className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">진료일</label>
              <input
                type="date"
                value={form.visit_date}
                onChange={(e) => setForm((p) => ({ ...p, visit_date: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">병원명</label>
              <input
                value={form.hospital_name}
                onChange={(e) => setForm((p) => ({ ...p, hospital_name: e.target.value }))}
                placeholder="서울대학교병원"
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">진료과</label>
              <input
                value={form.department}
                onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}
                placeholder="내과"
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">가이드 상태</label>
              <select
                value={form.guide_status}
                onChange={(e) => setForm((p) => ({ ...p, guide_status: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              >
                <option value="GS_ACTIVE">복약 중</option>
                <option value="GS_DONE">완료</option>
              </select>
            </div>
          </div>

          <TagInput
            label="진단명"
            tags={form.diagnoses}
            onAdd={(v) => setForm((p) => ({ ...p, diagnoses: [...p.diagnoses, v] }))}
            onRemove={(v) => setForm((p) => ({ ...p, diagnoses: p.diagnoses.filter((x) => x !== v) }))}
          />

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">메모</label>
            <textarea
              value={form.memo}
              onChange={(e) => setForm((p) => ({ ...p, memo: e.target.value }))}
              rows={3}
              placeholder="추가 메모를 입력하세요"
              className="w-full resize-none rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
            />
          </div>
        </div>

        {/* 복약 정보 */}
        <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
          <p className="text-sm font-semibold text-foreground">복약 정보</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">복약 시작일</label>
              <input
                type="date"
                value={form.med_start_date}
                onChange={(e) => setForm((p) => ({ ...p, med_start_date: e.target.value }))}
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">복약 기간 (일)</label>
              <input
                type="number"
                value={form.duration_days}
                onChange={(e) => setForm((p) => ({ ...p, duration_days: e.target.value }))}
                placeholder="30"
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* 처방 약물 */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground">처방 약물</p>
          {form.meds.map((med, idx) => (
            <div key={med.id} className="rounded-2xl border border-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-xs font-semibold text-teal-400">약물 {idx + 1}</span>
                <button onClick={() => removeMed(med.id)} className="text-xs text-muted-foreground hover:text-red-400">✕ 삭제</button>
              </div>

              <div className="mb-3">
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">약물명 <span className="text-red-400">*</span></label>
                <input
                  value={med.name}
                  onChange={(e) => updateMed(med.id, "name", e.target.value)}
                  placeholder="아모디핀정 5mg"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                />
              </div>

              <div className="mb-3 grid grid-cols-3 gap-3">
                {(["dosage", "frequency", "duration_days"] as const).map((field) => (
                  <div key={field}>
                    <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                      {field === "dosage" ? "용량" : field === "frequency" ? "횟수" : "기간(일)"}
                    </label>
                    <input
                      type={field === "duration_days" ? "number" : "text"}
                      value={med[field]}
                      onChange={(e) => updateMed(med.id, field, e.target.value)}
                      className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
                    />
                  </div>
                ))}
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium text-muted-foreground">복용 시점</label>
                <div className="flex flex-wrap gap-2">
                  {TIME_SLOTS.map((ts) => (
                    <label key={ts.value} className="flex cursor-pointer items-center gap-1.5 text-xs">
                      <input
                        type="radio"
                        name={`ts_${med.id}`}
                        value={ts.value}
                        checked={med.time_slot === ts.value}
                        onChange={() => updateMed(med.id, "time_slot", ts.value)}
                        className="accent-teal-500"
                      />
                      <span className={med.time_slot === ts.value ? "font-medium text-teal-400" : "text-muted-foreground"}>
                        {ts.label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          ))}

          <button
            onClick={addMed}
            className="w-full rounded-2xl border border-dashed border-teal-500/30 py-3.5 text-sm text-teal-400 transition hover:border-teal-500/60 hover:bg-teal-500/5"
          >
            + 약물 추가
          </button>
        </div>

        {/* 기저질환·알레르기 */}
        <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
          <p className="text-sm font-semibold text-foreground">기저질환 · 알레르기</p>
          <TagInput
            label="기저질환"
            tags={form.diseases}
            onAdd={(v) => setForm((p) => ({ ...p, diseases: [...p.diseases, v] }))}
            onRemove={(v) => setForm((p) => ({ ...p, diseases: p.diseases.filter((x) => x !== v) }))}
          />
          <TagInput
            label="알레르기"
            tags={form.allergies}
            onAdd={(v) => setForm((p) => ({ ...p, allergies: [...p.allergies, v] }))}
            onRemove={(v) => setForm((p) => ({ ...p, allergies: p.allergies.filter((x) => x !== v) }))}
          />
        </div>

        {/* 버튼 */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={() => router.push(`/guide/${guideId}`)}
            className="flex-1 rounded-xl border border-border py-3 text-sm text-muted-foreground transition hover:border-teal-500/30 hover:text-foreground"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:opacity-50"
          >
            {saving ? "저장 중..." : "💾 저장하기"}
          </button>
        </div>
      </div>

      {/* 면책 고지 */}
      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
