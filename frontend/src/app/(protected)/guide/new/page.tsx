"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
type Screen = "modal" | "step1" | "step2" | "generating";

interface MedInput {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  duration_days: string;
  time_slots: string[];
}

interface Step1Data {
  visit_date: string;
  hospital_name: string;
  department: string;
  input_method: "prescription" | "manual";
  diagnoses: string[];
  memo: string;
}

const TIME_SLOTS = [
  { value: "morning_before", label: "아침 식전" },
  { value: "morning_after",  label: "아침 식후" },
  { value: "lunch_before",   label: "점심 식전" },
  { value: "lunch_after",    label: "점심 식후" },
  { value: "evening_before", label: "저녁 식전" },
  { value: "evening_after",  label: "저녁 식후" },
  { value: "bedtime",        label: "취침 전"   },
];

const AI_STEPS = [
  { key: "save",      label: "약물 정보 저장",              doneAt: 2  },
  { key: "edr",       label: "e약은요 API 조회",            doneAt: 5  },
  { key: "dur",       label: "DUR 금기 데이터 조회",        doneAt: 8  },
  { key: "med",       label: "RT_MEDICATION 복약 안내 생성", doneAt: 12 },
  { key: "life",      label: "RT_LIFESTYLE 생활습관 가이드", doneAt: 16 },
  { key: "caution",   label: "RT_CAUTION 주의사항 정리",    doneAt: 20 },
];

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

function StepBar({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { n: 1, label: "진료 정보" },
    { n: 2, label: "약물 정보" },
    { n: 3, label: "생성"     },
  ];
  return (
    <div className="mb-8 flex items-center gap-0">
      {steps.map((s, i) => (
        <div key={s.n} className="flex items-center">
          <div className="flex flex-col items-center gap-1">
            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
              current > s.n
                ? "bg-teal-500 text-white"
                : current === s.n
                  ? "border-2 border-teal-500 bg-teal-500/10 text-teal-400"
                  : "border border-border bg-muted text-muted-foreground"
            }`}>
              {current > s.n ? "✓" : s.n}
            </div>
            <span className={`text-[10px] font-medium ${current === s.n ? "text-teal-400" : "text-muted-foreground"}`}>
              {s.label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`mb-4 h-px w-12 sm:w-20 transition-colors ${current > s.n + 1 || (current > s.n) ? "bg-teal-500/50" : "bg-border"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────
export default function NewGuidePage() {
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>("modal");
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [timerRef, setTimerRef] = useState<ReturnType<typeof setInterval> | null>(null);

  // STEP1 상태
  const [title, setTitle] = useState("");
  const [step1, setStep1] = useState<Step1Data>({
    visit_date: new Date().toISOString().split("T")[0],
    hospital_name: "",
    department: "",
    input_method: "manual",
    diagnoses: [],
    memo: "",
  });
  const [diagInput, setDiagInput] = useState("");

  // STEP2 상태
  const [meds, setMeds] = useState<MedInput[]>([newMed()]);

  function newMed(): MedInput {
    return { id: crypto.randomUUID(), name: "", dosage: "1정", frequency: "1회", duration_days: "30", time_slots: ["morning_after"] };
  }

  const showToast = (msg: string, type: "ok" | "err" = "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  // ── 진단명 태그 ──
  const addDiag = () => {
    const v = diagInput.trim();
    if (!v || step1.diagnoses.includes(v)) return;
    setStep1((p) => ({ ...p, diagnoses: [...p.diagnoses, v] }));
    setDiagInput("");
  };
  const removeDiag = (d: string) =>
    setStep1((p) => ({ ...p, diagnoses: p.diagnoses.filter((x) => x !== d) }));

  // ── STEP1 → STEP2 ──
  const goStep2 = () => {
    if (!title.trim()) {
      showToast("가이드 제목을 입력해주세요.");
      document.getElementById("guide-title")?.focus();
      return;
    }
    if (!step1.visit_date) { showToast("진료일을 입력해주세요."); return; }
    setScreen("step2");
    window.scrollTo(0, 0);
  };

  // ── 약물 추가/삭제 ──
  const addMed = () => setMeds((p) => [...p, newMed()]);
  const removeMed = (id: string) => setMeds((p) => p.filter((m) => m.id !== id));
  const updateMed = (id: string, field: keyof MedInput, value: string | string[]) =>
    setMeds((p) => p.map((m) => m.id === id ? { ...m, [field]: value } : m));

  // ── AI 가이드 생성 ──
  const generate = async () => {
    const validMeds = meds.filter((m) => m.name.trim());
    if (validMeds.length === 0) { showToast("약물명을 최소 1개 입력해주세요."); return; }

    setScreen("generating");
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    setTimerRef(t);
    window.scrollTo(0, 0);

    try {
      // 백엔드 GuideCreateRequest 필드명에 맞춰 전송
      const payload = {
        title: title.trim() || null,
        diagnosis_name: step1.diagnoses.join(", ") || null,
        hospital_name: step1.hospital_name || null,
        visit_date: step1.visit_date || null,
        med_start_date: step1.visit_date, // 진료일을 복약 시작일로 사용
        medications: validMeds.map((m) => ({
          medication_name: m.name.trim(),
          dosage: m.dosage || null,
          frequency: m.frequency || null,
          duration_days: m.duration_days ? parseInt(m.duration_days) : null,
          timing: m.time_slots[0] ?? null, // 첫 번째 시점을 timing으로
        })),
      };

      const { data: guideData } = await apiClient.post("/api/v1/guides", payload);
      const guideId: number = (guideData.data ?? guideData).guide_id;

      await apiClient.post(`/api/v1/guides/${guideId}/ai-generate`, { result_types: null });

      clearInterval(t);
      router.replace(`/guide/${guideId}`);
    } catch (e: unknown) {
      clearInterval(t);
      showToast(e instanceof Error ? e.message : "가이드 생성에 실패했습니다.", "err");
      setScreen("step2");
    }
  };

  // ── SCREEN: 모달 ──────────────────────────────────────────
  if (screen === "modal") {
    return (
      <div className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
          <h2 className="mb-1 text-lg font-bold text-foreground">새 가이드 만들기</h2>
          <p className="mb-6 text-sm text-muted-foreground">처방전을 업로드하거나 직접 입력하세요</p>

          {/* 문서 업로드 */}
          <button
            onClick={() => router.push("/docs")}
            className="group mb-3 w-full overflow-hidden rounded-xl border border-teal-500/30 bg-teal-500/10 p-4 text-left transition hover:bg-teal-500/15"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">📄</span>
              <div>
                <p className="text-sm font-semibold text-foreground">문서 업로드로 만들기</p>
                <p className="text-xs text-muted-foreground">처방전·진료기록을 업로드</p>
              </div>
            </div>
          </button>

          {/* 직접 입력 */}
          <button
            onClick={() => { setScreen("step1"); window.scrollTo(0, 0); }}
            className="w-full overflow-hidden rounded-xl border border-border bg-card p-4 text-left transition hover:border-teal-500/30 hover:bg-teal-500/5"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">✏️</span>
              <div>
                <p className="text-sm font-semibold text-foreground">직접 입력으로 만들기</p>
                <p className="text-xs text-muted-foreground">약 이름과 복용 정보 입력</p>
              </div>
            </div>
          </button>

          <button
            onClick={() => router.back()}
            className="mt-4 w-full rounded-xl py-2.5 text-sm text-muted-foreground transition hover:text-foreground"
          >
            취소
          </button>
        </div>
        {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      </div>
    );
  }

  // ── SCREEN: STEP1 진료 정보 ───────────────────────────────
  if (screen === "step1") {
    return (
      <div className="mx-auto max-w-xl px-4 py-8 pb-24 lg:pb-8">
        <StepBar current={1} />

        <h1 className="mb-1 text-xl font-bold text-foreground">진료 정보 입력</h1>
        <p className="mb-6 text-sm text-muted-foreground">기본 진료 정보를 입력해주세요</p>

        <div className="space-y-5">
          {/* 가이드 제목 */}
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="mb-4 text-sm font-semibold text-foreground">가이드 제목</p>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                제목 <span className="text-red-400">*</span>
              </label>
              <input
                id="guide-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="고혈압·고지혈증 관리 가이드"
                className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          </div>

          {/* 기본 정보 */}
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="mb-4 text-sm font-semibold text-foreground">기본 정보</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  진료일 <span className="text-red-400">*</span>
                </label>
                <input
                  type="date"
                  value={step1.visit_date}
                  onChange={(e) => setStep1((p) => ({ ...p, visit_date: e.target.value }))}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground focus:border-teal-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">병원명 (선택)</label>
                <input
                  type="text"
                  value={step1.hospital_name}
                  onChange={(e) => setStep1((p) => ({ ...p, hospital_name: e.target.value }))}
                  placeholder="서울대학교병원"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">진료과 (선택)</label>
                <input
                  type="text"
                  value={step1.department}
                  onChange={(e) => setStep1((p) => ({ ...p, department: e.target.value }))}
                  placeholder="내과"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">입력 방법</label>
                <div className="flex gap-3 pt-1">
                  {(["prescription", "manual"] as const).map((v) => (
                    <label key={v} className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="input_method"
                        value={v}
                        checked={step1.input_method === v}
                        onChange={() => setStep1((p) => ({ ...p, input_method: v }))}
                        className="accent-teal-500"
                      />
                      <span className="text-foreground">{v === "prescription" ? "처방전" : "직접 입력"}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 진단 정보 */}
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="mb-4 text-sm font-semibold text-foreground">진단 정보</p>
            <div className="mb-3">
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">진단명</label>
              <div className="flex flex-wrap gap-2 rounded-xl border border-input bg-background px-3 py-2 min-h-[44px]">
                {step1.diagnoses.map((d) => (
                  <span key={d} className="inline-flex items-center gap-1 rounded-full bg-teal-500/15 px-2.5 py-0.5 text-xs font-medium text-teal-400">
                    {d}
                    <button onClick={() => removeDiag(d)} className="opacity-60 hover:opacity-100">×</button>
                  </span>
                ))}
                <input
                  value={diagInput}
                  onChange={(e) => setDiagInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDiag(); } }}
                  placeholder={step1.diagnoses.length === 0 ? "입력 후 Enter..." : ""}
                  className="flex-1 min-w-[120px] bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">메모 (선택)</label>
              <textarea
                value={step1.memo}
                onChange={(e) => setStep1((p) => ({ ...p, memo: e.target.value }))}
                placeholder="추가 메모를 입력하세요"
                rows={3}
                className="w-full resize-none rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          </div>

          {/* 버튼 */}
          <div className="flex gap-3">
            <button
              onClick={() => setScreen("modal")}
              className="flex-1 rounded-xl border border-border py-3 text-sm text-muted-foreground transition hover:border-teal-500/30 hover:text-foreground"
            >
              취소
            </button>
            <button
              onClick={goStep2}
              className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500"
            >
              다음 →
            </button>
          </div>
        </div>
        {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      </div>
    );
  }

  // ── SCREEN: STEP2 약물 정보 ───────────────────────────────
  if (screen === "step2") {
    return (
      <div className="mx-auto max-w-xl px-4 py-8 pb-24 lg:pb-8">
        <StepBar current={2} />

        <h1 className="mb-1 text-xl font-bold text-foreground">약물 정보 입력</h1>
        <p className="mb-6 text-sm text-muted-foreground">처방받은 약물 정보를 입력해주세요</p>

        <div className="space-y-3">
          {meds.map((med, idx) => (
            <div key={med.id} className="rounded-2xl border border-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-xs font-semibold text-teal-400">약물 {idx + 1}</span>
                {meds.length > 1 && (
                  <button
                    onClick={() => removeMed(med.id)}
                    className="text-xs text-muted-foreground transition hover:text-red-400"
                  >
                    ✕ 삭제
                  </button>
                )}
              </div>

              {/* 약물명 */}
              <div className="mb-3">
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  약물명 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={med.name}
                  onChange={(e) => updateMed(med.id, "name", e.target.value)}
                  placeholder="아모디핀정 5mg"
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                />
              </div>

              {/* 용량/횟수/기간 */}
              <div className="mb-3 grid grid-cols-3 gap-3">
                {(["dosage", "frequency", "duration_days"] as const).map((field) => (
                  <div key={field}>
                    <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                      {field === "dosage" ? "1회 용량" : field === "frequency" ? "1일 횟수" : "복약 기간"}
                    </label>
                    <input
                      type={field === "duration_days" ? "number" : "text"}
                      value={med[field]}
                      onChange={(e) => updateMed(med.id, field, e.target.value)}
                      placeholder={field === "dosage" ? "1정" : field === "frequency" ? "1회" : "30"}
                      className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                    />
                  </div>
                ))}
              </div>

              {/* 복용 시점 */}
              <div>
                <label className="mb-2 block text-xs font-medium text-muted-foreground">복용 시점 (중복 선택 가능)</label>
                <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                  {TIME_SLOTS.map((ts) => {
                    const checked = med.time_slots.includes(ts.value);
                    return (
                      <label key={ts.value} className="flex cursor-pointer items-center gap-1.5 text-xs">
                        <input
                          type="checkbox"
                          value={ts.value}
                          checked={checked}
                          onChange={() => {
                            const next = checked
                              ? med.time_slots.filter((v) => v !== ts.value)
                              : [...med.time_slots, ts.value];
                            updateMed(med.id, "time_slots", next);
                          }}
                          className="accent-teal-500"
                        />
                        <span className={checked ? "text-teal-400 font-medium" : "text-muted-foreground"}>
                          {ts.label}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}

          {/* 약물 추가 */}
          <button
            onClick={addMed}
            className="w-full rounded-2xl border border-dashed border-teal-500/30 py-3.5 text-sm text-teal-400 transition hover:border-teal-500/60 hover:bg-teal-500/5"
          >
            + 약물 추가
          </button>

          {/* 버튼 */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => { setScreen("step1"); window.scrollTo(0, 0); }}
              className="flex-1 rounded-xl border border-border py-3 text-sm text-muted-foreground transition hover:border-teal-500/30 hover:text-foreground"
            >
              ← 이전
            </button>
            <button
              onClick={generate}
              className="flex-1 rounded-xl py-3 text-sm font-semibold text-white transition"
              style={{ background: "linear-gradient(135deg, #14b8a6, #06b6d4)", boxShadow: "0 0 20px rgba(20,184,166,0.3)" }}
            >
              🤖 AI 가이드 생성하기
            </button>
          </div>
        </div>
        {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      </div>
    );
  }

  // ── SCREEN: 가이드 생성 중 ────────────────────────────────
  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center px-4 text-center">
      {/* 스피너 */}
      <div className="relative mb-8">
        <div className="h-20 w-20 animate-spin rounded-full border-4 border-teal-500/20 border-t-teal-400" />
        <div className="absolute inset-0 flex items-center justify-center text-2xl">🤖</div>
      </div>

      <h2 className="mb-2 text-xl font-bold text-foreground">AI가 복약 가이드를 생성하고 있습니다</h2>
      <p className="mb-8 max-w-sm text-sm text-muted-foreground">
        e약은요 · DUR 데이터베이스 조회 후 맞춤 가이드를 작성합니다
      </p>

      {/* 단계 목록 */}
      <div className="w-full max-w-sm space-y-3 text-left">
        {AI_STEPS.map((s) => {
          const done   = elapsed >= s.doneAt;
          const active = !done && elapsed >= s.doneAt - 4;
          return (
            <div key={s.key} className="flex items-center gap-3 text-sm">
              <span className="w-5 text-center text-base">
                {done ? "✅" : active ? "⏳" : "⬜"}
              </span>
              <span className={done ? "text-foreground" : active ? "text-orange-400 font-medium" : "text-muted-foreground"}>
                {s.label}
                {active && " 중..."}
                {done && " 완료"}
              </span>
            </div>
          );
        })}
      </div>

      {elapsed >= 30 && (
        <p className="mt-6 text-xs text-yellow-500">시간이 걸리고 있어요, 잠시만 기다려주세요.</p>
      )}
    </div>
  );
}
