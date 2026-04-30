"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
type Step = "upload" | "analyzing" | "result";

interface UploadedFile {
  file: File;
  id: string;
}

interface MedItem {
  medication_name: string;
  dosage: string;
  frequency: string;
  timing: string;
  duration_days: number | null;
  confidence: number | null;
}

interface AnalysisResult {
  doc_result_id: number;
  overall_confidence: number | null;
  processing_time: number;
}

const TIMING_OPTIONS = ["식전", "식후즉시", "식후30분", "취침전"];

// ── 신뢰도 바 ──────────────────────────────────────────────
function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500">
        ⚠️ 미확인
      </span>
    );
  }
  const pct = Math.round(value * 100);
  const color = value >= 0.9 ? "bg-teal-500" : value >= 0.7 ? "bg-yellow-500" : "bg-red-500";
  const textColor = value >= 0.9 ? "text-teal-500" : value >= 0.7 ? "text-yellow-500" : "text-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor}`}>{pct}%</span>
    </div>
  );
}

// ── 토스트 ─────────────────────────────────────────────────
function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-3 text-sm text-red-500 shadow-lg lg:bottom-6">
      {message}
      <button onClick={onClose} className="ml-3 opacity-60 hover:opacity-100">✕</button>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────
export default function DocsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>("upload");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [confirming, setConfirming] = useState(false);

  // 편집 state
  const [hospitalName, setHospitalName] = useState("");
  const [visitDate, setVisitDate] = useState("");
  const [diagnosisName, setDiagnosisName] = useState("");
  const [medications, setMedications] = useState<MedItem[]>([]);
  const [showDirectInput, setShowDirectInput] = useState<Record<number, boolean>>({});
  const [directInputVal, setDirectInputVal] = useState<Record<number, string>>({});

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const validateAndAdd = (incoming: File[]) => {
    const allowed = ["image/jpeg", "image/png", "application/pdf"];
    for (const f of incoming) {
      if (!allowed.includes(f.type)) {
        showToast(`${f.name}: JPG, PNG, PDF 파일만 업로드 가능합니다.`);
        return;
      }
      const maxSize = f.type === "application/pdf" ? 20 * 1024 * 1024 : 10 * 1024 * 1024;
      if (f.size > maxSize) {
        const mb = f.type === "application/pdf" ? 20 : 10;
        showToast(`${f.name}: 파일 크기가 ${mb}MB를 초과합니다.`);
        return;
      }
    }
    setFiles((prev) => {
      const combined = [...prev, ...incoming.map((f) => ({ file: f, id: crypto.randomUUID() }))];
      if (combined.length > 5) {
        showToast("최대 5개까지 업로드 가능합니다.");
        return prev;
      }
      return combined;
    });
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    validateAndAdd(Array.from(e.dataTransfer.files));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) validateAndAdd(Array.from(e.target.files));
    e.target.value = "";
  };

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  const formatSize = (bytes: number) => {
    if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
    return `${(bytes / 1024).toFixed(0)}KB`;
  };

  // ── 분석 시작 ──
  const startAnalysis = async () => {
    if (files.length === 0) return;
    setStep("analyzing");
    setElapsedSec(0);
    timerRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);

    const formData = new FormData();
    files.forEach((f, i) => formData.append(`file${i + 1}`, f.file));

    try {
      const { data } = await apiClient.post("/api/v1/medical-doc/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const raw = data.data;

      const meds: MedItem[] = Array.isArray(raw.medications)
        ? raw.medications.map((m: Record<string, unknown>) => ({
            medication_name: String(m.medication_name ?? ""),
            dosage: String(m.dosage ?? ""),
            frequency: String(m.frequency ?? ""),
            timing: String(m.timing ?? ""),
            duration_days: m.duration_days != null ? Number(m.duration_days) : null,
            confidence: m.confidence != null ? Number(m.confidence) : null,
          }))
        : [];

      setResult({
        doc_result_id: raw.doc_result_id,
        overall_confidence: raw.overall_confidence ?? null,
        processing_time: raw.processing_time ?? 0,
      });
      setHospitalName(raw.hospital_name ?? "");
      setVisitDate(raw.visit_date ?? raw.prescription_date ?? "");
      setDiagnosisName(raw.diagnosis_name ?? "");
      setMedications(meds);
      setShowDirectInput({});
      setDirectInputVal({});
      setStep("result");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "분석 중 오류가 발생했습니다.";
      showToast(msg);
      setStep("upload");
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const resetAll = () => {
    setStep("upload");
    setFiles([]);
    setResult(null);
    setElapsedSec(0);
    setHospitalName("");
    setVisitDate("");
    setDiagnosisName("");
    setMedications([]);
    setShowDirectInput({});
    setDirectInputVal({});
  };

  const updateMed = (idx: number, field: keyof MedItem, value: string | number | null) => {
    setMedications((prev) => prev.map((m, i) => i === idx ? { ...m, [field]: value } : m));
  };

  // ── 확인 완료: PATCH → from-doc → ai-generate → /guide/{id} ──
  const confirmAndGenerate = async () => {
    if (!result) return;
    setConfirming(true);
    try {
      await apiClient.patch(`/api/v1/medical-doc/results/${result.doc_result_id}`, {
        hospital_name: hospitalName || null,
        visit_date: visitDate || null,
        diagnosis_name: diagnosisName || null,
        medications: medications.map((m, i) => ({
          medication_index: i,
          medication_name: m.medication_name,
          dosage: m.dosage || null,
          frequency: m.frequency || null,
          timing: m.timing || null,
          duration_days: m.duration_days,
        })),
      });

      const today = new Date().toISOString().slice(0, 10);
      const { data: guideData } = await apiClient.post("/api/v1/guides/from-doc", {
        doc_result_id: result.doc_result_id,
        med_start_date: today,
      });
      const guideId: number = (guideData.data ?? guideData).guide_id;

      await apiClient.post(`/api/v1/guides/${guideId}/ai-generate`, { result_types: null });
      router.push(`/guide/${guideId}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "가이드 생성에 실패했습니다.";
      showToast(msg);
      setConfirming(false);
    }
  };

  // ── 분석 진행 단계 표시 ──
  const STEPS_LABEL = [
    { label: "이미지 전처리", doneAt: 3 },
    { label: "OCR 텍스트 추출", doneAt: 8 },
    { label: "AI 구조화 분석", doneAt: 18 },
    { label: "결과 저장", doneAt: 22 },
  ];

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 면책 고지 */}
      <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/5 px-4 py-2.5 text-xs text-orange-500">
        ⚠️ 본 서비스는 참고용이며, 정확한 복약은 의사/약사와 상담하세요.
      </div>

      {/* ── 화면 1: 업로드 ── */}
      {step === "upload" && (
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">📄 의료 문서 업로드</h1>
            <p className="mt-1 text-sm text-muted-foreground">처방전, 진료기록, 약봉투 등을 업로드하면 AI가 자동으로 분석합니다.</p>
          </div>

          {/* 드래그앤드롭 영역 */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
              dragging
                ? "border-teal-500 bg-teal-500/5"
                : "border-border bg-card hover:border-teal-500/50 hover:bg-teal-500/5"
            }`}
          >
            <div className="mb-3 text-4xl">📎</div>
            <p className="text-sm font-medium text-foreground">클릭 또는 드래그하여 파일을 업로드하세요</p>
            <p className="mt-2 text-xs text-muted-foreground">JPG · PNG · PDF 지원</p>
            <p className="text-xs text-muted-foreground">이미지 최대 10MB · PDF 최대 20MB · 최대 5개</p>
            <input ref={fileInputRef} type="file" multiple accept=".jpg,.jpeg,.png,.pdf" className="hidden" onChange={onFileChange} />
          </div>

          {/* 팁 */}
          <p className="text-xs text-muted-foreground">
            💡 약봉투는 앞면과 뒷면을 함께 올리면 더 정확하게 분석돼요.
          </p>

          {/* 파일 목록 */}
          {files.length > 0 && (
            <div className="rounded-xl border border-border bg-card divide-y divide-border">
              {files.map((f) => (
                <div key={f.id} className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg">📄</span>
                    <div className="min-w-0">
                      <p className="truncate text-sm text-foreground">{f.file.name}</p>
                      <p className="text-xs text-muted-foreground">{formatSize(f.file.size)}</p>
                    </div>
                  </div>
                  <button onClick={() => removeFile(f.id)} className="ml-3 shrink-0 text-muted-foreground transition hover:text-red-500">✕</button>
                </div>
              ))}
            </div>
          )}

          {/* 분석 시작 버튼 */}
          <button
            onClick={startAnalysis}
            disabled={files.length === 0}
            className="w-full rounded-xl bg-teal-600 py-3.5 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            분석 시작하기 →
          </button>

          {/* 기록 보기 링크 */}
          <button
            onClick={() => router.push("/docs/results")}
            className="w-full rounded-xl border border-border py-3 text-sm text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
          >
            📂 내 분석 기록 보기
          </button>
        </div>
      )}

      {/* ── 화면 2: 분석 중 ── */}
      {step === "analyzing" && (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 text-center">
          <div>
            <div className="mb-4 text-5xl animate-pulse">🔄</div>
            <h2 className="text-xl font-bold text-foreground">AI 분석 중...</h2>
            <p className="mt-1 text-sm text-muted-foreground">평균 소요 시간: 15~20초</p>
            {elapsedSec >= 30 && (
              <p className="mt-2 text-xs text-yellow-500">시간이 걸리고 있어요, 잠시만 기다려주세요.</p>
            )}
          </div>

          {/* 진행 바 */}
          <div className="w-full max-w-sm">
            <div className="mb-2 flex justify-between text-xs text-muted-foreground">
              <span>진행 중</span>
              <span>{Math.min(Math.round((elapsedSec / 22) * 100), 95)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-teal-500 transition-all duration-1000"
                style={{ width: `${Math.min(Math.round((elapsedSec / 22) * 100), 95)}%` }}
              />
            </div>
          </div>

          {/* 단계별 상태 */}
          <div className="w-full max-w-sm space-y-3 text-left">
            {STEPS_LABEL.map((s) => {
              const done = elapsedSec >= s.doneAt;
              const active = !done && elapsedSec >= s.doneAt - 5;
              return (
                <div key={s.label} className="flex items-center gap-3 text-sm">
                  <span className="text-base">
                    {done ? "✅" : active ? "🔄" : "⏳"}
                  </span>
                  <span className={done ? "text-foreground" : "text-muted-foreground"}>
                    {s.label}{active ? " 중..." : done ? " 완료" : " 대기"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 화면 3: 결과 ── */}
      {step === "result" && result && (
        <div className="space-y-5">
          {/* 헤더 */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-foreground">✅ 분석 완료</h1>
              <p className="mt-0.5 text-xs text-muted-foreground">처리 시간: {result.processing_time}초</p>
            </div>
            {result.overall_confidence !== null && <ConfidenceBar value={result.overall_confidence} />}
          </div>

          {/* 기본 정보 */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="mb-4 text-sm font-semibold text-teal-500">🏥 기본 정보</h2>
            <div className="space-y-3">
              {([
                { label: "의료기관명", value: hospitalName, setter: setHospitalName, placeholder: "의료기관명 입력" },
                { label: "진료일", value: visitDate, setter: setVisitDate, placeholder: "YYYY-MM-DD", type: "date" },
                { label: "진단명", value: diagnosisName, setter: setDiagnosisName, placeholder: "진단명 입력" },
              ] as { label: string; value: string; setter: (v: string) => void; placeholder: string; type?: string }[]).map(({ label, value, setter, placeholder, type }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-xs text-muted-foreground">{label}</span>
                  <input
                    type={type ?? "text"}
                    value={value}
                    onChange={(e) => setter(e.target.value)}
                    placeholder={placeholder}
                    className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* 약물 목록 */}
          {medications.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="mb-4 text-sm font-semibold text-teal-500">💊 처방 약물</h2>
              <div className="space-y-5">
                {medications.map((med, idx) => {
                  const lowConf = med.confidence === null || med.confidence < 0.7;
                  const noTiming = !med.timing;
                  return (
                    <div
                      key={idx}
                      className={`rounded-lg border p-4 ${
                        lowConf || noTiming ? "border-orange-500/30 bg-orange-500/5" : "border-border bg-background"
                      }`}
                    >
                      {/* 약품명 + 신뢰도 */}
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <input
                          value={med.medication_name}
                          onChange={(e) => updateMed(idx, "medication_name", e.target.value)}
                          className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-semibold text-foreground focus:border-teal-500/50 focus:outline-none"
                          placeholder="약품명"
                        />
                        <ConfidenceBar value={med.confidence} />
                      </div>

                      {/* 용량 / 횟수 / 기간 */}
                      <div className="mb-3 grid grid-cols-3 gap-2">
                        {([
                          { field: "dosage" as const, label: "투약량", placeholder: "1정" },
                          { field: "frequency" as const, label: "복용횟수", placeholder: "1일 2회" },
                          { field: "duration_days" as const, label: "투약일수", placeholder: "5", type: "number" },
                        ]).map(({ field, label, placeholder, type }) => (
                          <div key={field}>
                            <p className="mb-1 text-[10px] text-muted-foreground">{label}</p>
                            <input
                              type={type ?? "text"}
                              value={med[field] ?? ""}
                              onChange={(e) => updateMed(idx, field, field === "duration_days" ? (e.target.value ? Number(e.target.value) : null) : e.target.value)}
                              placeholder={placeholder}
                              className="w-full rounded-lg border border-input bg-background px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                            />
                          </div>
                        ))}
                      </div>

                      {/* 복용시점 */}
                      <div>
                        <p className="mb-1.5 text-[10px] text-muted-foreground">복용시점</p>
                        {noTiming && (
                          <p className="mb-1.5 text-xs text-orange-400">⚠️ 미확인 — 아래에서 선택하세요</p>
                        )}
                        <div className="flex flex-wrap gap-1.5">
                          {TIMING_OPTIONS.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => {
                                updateMed(idx, "timing", opt);
                                setShowDirectInput((p) => ({ ...p, [idx]: false }));
                              }}
                              className="rounded-lg border px-3 py-1 text-xs transition"
                              style={{
                                borderColor: med.timing === opt ? "#14b8a6" : undefined,
                                backgroundColor: med.timing === opt ? "rgba(20,184,166,0.15)" : undefined,
                                color: med.timing === opt ? "#14b8a6" : undefined,
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                          <button
                            type="button"
                            onClick={() => setShowDirectInput((p) => ({ ...p, [idx]: !p[idx] }))}
                            className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
                          >
                            직접입력
                          </button>
                        </div>
                        {showDirectInput[idx] && (
                          <div className="mt-2 flex gap-2">
                            <input
                              value={directInputVal[idx] ?? ""}
                              onChange={(e) => setDirectInputVal((p) => ({ ...p, [idx]: e.target.value }))}
                              placeholder="복용시점 직접 입력"
                              className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                            />
                            <button
                              type="button"
                              onClick={() => {
                                updateMed(idx, "timing", directInputVal[idx] ?? "");
                                setShowDirectInput((p) => ({ ...p, [idx]: false }));
                              }}
                              className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs text-white hover:bg-teal-500"
                            >
                              확인
                            </button>
                          </div>
                        )}
                        {med.timing && !showDirectInput[idx] && (
                          <p className="mt-1.5 text-xs text-teal-400">선택됨: {med.timing}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 버튼 */}
          <div className="flex gap-3">
            <button
              onClick={resetAll}
              disabled={confirming}
              className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-40"
            >
              다시 분석
            </button>
            <button
              onClick={confirmAndGenerate}
              disabled={confirming}
              className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:opacity-50"
            >
              {confirming ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  가이드 생성 중...
                </span>
              ) : "확인 완료 →"}
            </button>
          </div>
        </div>
      )}

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
