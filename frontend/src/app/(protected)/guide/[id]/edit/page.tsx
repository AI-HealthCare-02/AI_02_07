"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import apiClient from "@/lib/axios";

interface MedInput {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  duration_days: string;
  time_slots: string[];
}

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

interface FormState {
  title: string;
  visit_date: string;
  hospital_name: string;
  diagnosis_name: string;
  memo: string;
  med_start_date: string;
  guide_status: string;
  meds: MedInput[];
}

export default function GuideEditPage() {
  const router  = useRouter();
  const params  = useParams();
  const guideId = Number(params.id);

  const [form, setForm] = useState<FormState>({
    title: "",
    visit_date: "",
    hospital_name: "",
    diagnosis_name: "",
    memo: "",
    med_start_date: "",
    guide_status: "GS_ACTIVE",
    meds: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}`)
      .then(({ data }) => {
        setForm({
          title: data.title ?? "",
          visit_date: data.visit_date ?? "",
          hospital_name: data.hospital_name ?? "",
          diagnosis_name: data.diagnosis_name ?? "",
          memo: "",
          med_start_date: data.med_start_date ?? "",
          guide_status: data.guide_status === "ACTIVE" ? "GS_ACTIVE" : data.guide_status === "COMPLETED" ? "GS_COMPLETED" : (data.guide_status ?? "GS_ACTIVE"),
          meds: (data.medications ?? []).map((m: { guide_medication_id: number; medication_name: string; dosage: string | null; frequency: string | null; timing: string | null; duration_days: number | null }) => ({
            id: String(m.guide_medication_id),
            name: m.medication_name ?? "",
            dosage: m.dosage ?? "",
            frequency: m.frequency ?? "",
            duration_days: String(m.duration_days ?? ""),
            time_slots: m.timing ? [m.timing] : [],
          })),
        });
      })
      .catch(() => showToast("가이드 정보를 불러오지 못했습니다.", "err"))
      .finally(() => setLoading(false));
  }, [guideId]);

  const addMed = () =>
    setForm((p) => ({
      ...p,
      meds: [...p.meds, { id: crypto.randomUUID(), name: "", dosage: "1정", frequency: "1회", duration_days: "30", time_slots: [] }],
    }));

  const removeMed = (id: string) => {
    if (form.meds.length <= 1) { showToast("약물은 최소 1개 이상 필요합니다.", "err"); return; }
    setForm((p) => ({ ...p, meds: p.meds.filter((m) => m.id !== id) }));
  };

  const updateMed = (id: string, field: keyof MedInput, value: string | string[]) =>
    setForm((p) => ({ ...p, meds: p.meds.map((m) => m.id === id ? { ...m, [field]: value } : m) }));

  const handleSave = async () => {
    if (!form.title.trim()) { showToast("가이드 제목을 입력해주세요.", "err"); return; }
    setSaving(true);
    try {
      await apiClient.patch(`/api/v1/guides/${guideId}`, {
        title: form.title || undefined,
        hospital_name: form.hospital_name || undefined,
        diagnosis_name: form.diagnosis_name || undefined,
        visit_date: form.visit_date || undefined,
        med_start_date: form.med_start_date || undefined,
        guide_status: form.guide_status || undefined,
      });
      showToast("가이드가 수정되었습니다 ✅");
      setTimeout(() => router.push(`/guide/${guideId}`), 800);
    } catch {
      showToast("저장에 실패했습니다.", "err");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-xl px-4 pb-24 lg:pb-8">
        <div className="flex h-64 items-center justify-center">
          <p className="text-sm text-muted-foreground">불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-4 pb-24 lg:pb-8">
      {/* ── Sticky 헤더 ── */}
      <div className="sticky top-16 z-30 -mx-4 mb-6 border-b border-border bg-background/95 px-4 pb-3 pt-4 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-2">
          <button
            onClick={() => router.push(`/guide/${guideId}`)}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition hover:text-foreground"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            뒤로
          </button>
        </div>
        <h1 className="mt-2 text-lg font-bold text-foreground">가이드 수정</h1>
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
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">진단명</label>
              <input
                value={form.diagnosis_name}
                onChange={(e) => setForm((p) => ({ ...p, diagnosis_name: e.target.value }))}
                placeholder="고혈압"
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
                <option value="GS_COMPLETED">완료</option>
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">복약 시작일</label>
            <input
              type="date"
              value={form.med_start_date}
              onChange={(e) => setForm((p) => ({ ...p, med_start_date: e.target.value }))}
              className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
            />
          </div>
        </div>

        {/* 처방 약물 (읽기 전용 표시) */}
        {form.meds.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm font-semibold text-foreground">처방 약물 <span className="text-xs font-normal text-muted-foreground">(참고용)</span></p>
            {form.meds.map((med, idx) => (
              <div key={med.id} className="rounded-2xl border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-teal-400">약물 {idx + 1}</span>
                </div>
                <p className="text-sm font-medium text-foreground">{med.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {[med.dosage, med.frequency, med.duration_days ? `${med.duration_days}일` : null].filter(Boolean).join(" · ")}
                </p>
              </div>
            ))}
          </div>
        )}

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

      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
