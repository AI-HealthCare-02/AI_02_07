"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";
import ReactMarkdown from "react-markdown";

// ── 타입 ──────────────────────────────────────────────────
type Step = "upload" | "analyzing" | "result";

interface UploadedFile {
  file: File;
  id: string;
}

interface MedItem {
  name: string;
  dosage: string | null;
  frequency: string | null;
  instructions: string | null;
  confidence: number | null;
  editingInstructions: boolean;
  editValue: string;
}

interface AnalysisResult {
  doc_result_id: number;
  document_type: string;
  overall_confidence: number | null;
  raw_summary: string | null;
  medications: MedItem[];
  cautions: string | null;
  hospital_name: string | null;
  prescription_date: string | null;
  processing_time: number;
}

const DOC_TYPES = ["자동인식", "처방전", "진료기록", "약봉투", "검진결과"] as const;

const INSTRUCTIONS_OPTIONS = ["식전", "식후즉시", "식후30분", "취침전", "직접입력"];

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
  const [docType, setDocType] = useState<string>("자동인식");
  const [dragging, setDragging] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    formData.append("document_type", docType);

    try {
      const { data } = await apiClient.post("/api/v1/medical-doc/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const raw = data.data;

      // medications 파싱 (raw_summary JSON 또는 medications 필드)
      let meds: MedItem[] = [];
      if (Array.isArray(raw.medications)) {
        meds = raw.medications.map((m: Record<string, unknown>) => ({
          name: String(m.name ?? ""),
          dosage: m.dosage ? String(m.dosage) : null,
          frequency: m.frequency ? String(m.frequency) : null,
          instructions: m.instructions ? String(m.instructions) : null,
          confidence: m.confidence != null ? Number(m.confidence) : null,
          editingInstructions: false,
          editValue: "",
        }));
      }

      setResult({
        doc_result_id: raw.doc_result_id,
        document_type: raw.document_type ?? docType,
        overall_confidence: raw.overall_confidence ?? null,
        raw_summary: raw.raw_summary ?? null,
        medications: meds,
        cautions: raw.cautions ?? null,
        hospital_name: raw.hospital_name ?? null,
        prescription_date: raw.prescription_date ?? null,
        processing_time: raw.processing_time ?? 0,
      });
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
    setDocType("자동인식");
    setResult(null);
    setElapsedSec(0);
  };

  // ── 복용법 수정 ──
  const toggleEditInstructions = (idx: number) => {
    setResult((prev) => {
      if (!prev) return prev;
      const meds = [...prev.medications];
      meds[idx] = { ...meds[idx], editingInstructions: !meds[idx].editingInstructions, editValue: meds[idx].instructions ?? "" };
      return { ...prev, medications: meds };
    });
  };

  const saveInstructions = (idx: number, value: string) => {
    setResult((prev) => {
      if (!prev) return prev;
      const meds = [...prev.medications];
      meds[idx] = { ...meds[idx], instructions: value, editingInstructions: false, confidence: Math.max(meds[idx].confidence ?? 0, 0.9) };
      return { ...prev, medications: meds };
    });
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

          {/* 문서 종류 선택 */}
          <div className="rounded-xl border border-border bg-card p-5">
            <p className="mb-3 text-sm font-semibold text-foreground">문서 종류 선택</p>
            <div className="space-y-2">
              {DOC_TYPES.map((t) => (
                <label key={t} className="flex cursor-pointer items-center gap-3">
                  <input
                    type="radio"
                    name="docType"
                    value={t}
                    checked={docType === t}
                    onChange={() => setDocType(t)}
                    className="accent-teal-500"
                  />
                  <span className="text-sm text-foreground">{t}{t === "자동인식" ? " (기본값)" : ""}</span>
                </label>
              ))}
            </div>
          </div>

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
            {result.overall_confidence !== null && (
              <ConfidenceBar value={result.overall_confidence} />
            )}
          </div>

          {/* 문서 요약 */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold text-teal-500">📋 문서 요약</h2>
            <div className="space-y-2 text-sm">
              <Row label="문서 종류" value={result.document_type} />
              {result.hospital_name && <Row label="병원/약국" value={result.hospital_name} />}
              {result.prescription_date && <Row label="조제일" value={result.prescription_date} />}
            </div>
          </div>

          {/* 약품 목록 */}
          {result.medications.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="mb-3 text-sm font-semibold text-teal-500">💊 약품 목록</h2>
              <div className="space-y-4">
                {result.medications.map((med, idx) => {
                  const lowConf = med.confidence === null || med.confidence < 0.7;
                  return (
                    <div key={idx} className={`rounded-lg border p-4 ${lowConf ? "border-red-500/30 bg-red-500/5" : "border-border bg-background"}`}>
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="font-medium text-foreground">{med.name}</span>
                        <ConfidenceBar value={med.confidence} />
                      </div>
                      {med.dosage && <p className="text-xs text-muted-foreground">{med.dosage}</p>}
                      {med.frequency && <p className="text-xs text-muted-foreground">{med.frequency}</p>}

                      {/* 복용법 */}
                      <div className="mt-2">
                        {med.editingInstructions ? (
                          <div className="space-y-2">
                            <p className="text-xs font-medium text-foreground">복용법 선택</p>
                            <div className="flex flex-wrap gap-2">
                              {INSTRUCTIONS_OPTIONS.map((opt) => (
                                <button
                                  key={opt}
                                  onClick={() => opt === "직접입력"
                                    ? setResult((prev) => {
                                        if (!prev) return prev;
                                        const meds = [...prev.medications];
                                        meds[idx] = { ...meds[idx], editValue: "" };
                                        return { ...prev, medications: meds };
                                      })
                                    : saveInstructions(idx, opt)
                                  }
                                  className="rounded-lg border border-border bg-muted px-3 py-1.5 text-xs text-foreground transition hover:border-teal-500/50 hover:bg-teal-500/10"
                                >
                                  {opt}
                                </button>
                              ))}
                            </div>
                            {med.editValue !== undefined && (
                              <div className="flex gap-2">
                                <input
                                  value={med.editValue}
                                  onChange={(e) => setResult((prev) => {
                                    if (!prev) return prev;
                                    const meds = [...prev.medications];
                                    meds[idx] = { ...meds[idx], editValue: e.target.value };
                                    return { ...prev, medications: meds };
                                  })}
                                  placeholder="직접 입력"
                                  className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
                                />
                                <button
                                  onClick={() => saveInstructions(idx, med.editValue)}
                                  className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs text-white hover:bg-teal-500"
                                >
                                  저장
                                </button>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">
                              복용법: {med.instructions ?? "-"}
                              {!med.instructions && <span className="ml-1 text-red-500">⚠️ 미확인</span>}
                            </span>
                            {lowConf && (
                              <button
                                onClick={() => toggleEditInstructions(idx)}
                                className="text-xs text-teal-500 underline hover:text-teal-400"
                              >
                                입력하기
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 주의사항 */}
          {result.cautions && (
            <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-5">
              <h2 className="mb-2 text-sm font-semibold text-yellow-500">⚠️ 주의사항</h2>
              <p className="text-sm text-foreground">{result.cautions}</p>
            </div>
          )}

          {/* AI 요약 */}
          {result.raw_summary && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="mb-2 text-sm font-semibold text-teal-500">📝 AI 요약</h2>
              <div className="prose prose-sm max-w-none text-sm text-foreground">
                <ReactMarkdown>{result.raw_summary}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* 버튼 */}
          <div className="flex gap-3">
            <button
              onClick={resetAll}
              className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
            >
              다시 분석
            </button>
            <button
              onClick={() => router.push("/docs/results")}
              className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500"
            >
              확인 완료 →
            </button>
          </div>
        </div>
      )}

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}
