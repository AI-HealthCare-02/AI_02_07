"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

interface Medication {
  medication_name: string;
  dosage: string | null;
  frequency: string | null;
  timing: string | null;
  duration_days: number | null;
  confidence: number | null;
}

interface ResultDetail {
  doc_result_id: number;
  hospital_name: string | null;
  visit_date: string | null;
  diagnosis_name: string | null;
  medications: Medication[];
  overall_confidence: number | null;
  raw_summary: string | null;
  ocr_raw_text: string | null;
  created_at: string;
}

const TIMING_OPTIONS = ["식전", "식후즉시", "식후30분", "취침전"];

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-orange-400">⚠️ 미확인</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.9 ? "bg-teal-500" : value >= 0.7 ? "bg-yellow-500" : "bg-red-500";
  const textColor = value >= 0.9 ? "text-teal-500" : value >= 0.7 ? "text-yellow-500" : "text-red-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor}`}>{pct}%</span>
    </div>
  );
}

export default function ResultDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [result, setResult] = useState<ResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 편집 state
  const [hospitalName, setHospitalName] = useState("");
  const [visitDate, setVisitDate] = useState("");
  const [diagnosisName, setDiagnosisName] = useState("");
  const [medications, setMedications] = useState<Medication[]>([]);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [showDirectInput, setShowDirectInput] = useState<Record<number, boolean>>({});
  const [directInputVal, setDirectInputVal] = useState<Record<number, string>>({});

  const [confirming, setConfirming] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [showOcr, setShowOcr] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    apiClient
      .get(`/api/v1/medical-doc/results/${id}`)
      .then(({ data }) => {
        const d: ResultDetail = data.data;
        setResult(d);
        setHospitalName(d.hospital_name ?? "");
        setVisitDate(d.visit_date ?? "");
        setDiagnosisName(d.diagnosis_name ?? "");
        setMedications(d.medications ?? []);
      })
      .catch(() => setError("결과를 불러오는 데 실패했습니다."))
      .finally(() => setLoading(false));
  }, [id]);

  const updateMedication = (idx: number, field: keyof Medication, value: string | number | null) => {
    setMedications((prev) => prev.map((m, i) => i === idx ? { ...m, [field]: value } : m));
  };

  const handleConfirm = async () => {
    if (!result) return;
    setConfirming(true);
    try {
      // ① 변경된 내용 PATCH
      const medUpdates = medications.map((m, i) => ({
        medication_index: i,
        medication_name: m.medication_name,
        dosage: m.dosage,
        frequency: m.frequency,
        timing: m.timing,
        duration_days: m.duration_days,
      }));

      await apiClient.patch(`/api/v1/medical-doc/results/${result.doc_result_id}`, {
        hospital_name: hospitalName || null,
        visit_date: visitDate || null,
        diagnosis_name: diagnosisName || null,
        medications: medUpdates,
      });

      // ② 가이드 생성
      const today = new Date().toISOString().slice(0, 10);
      const { data: guideData } = await apiClient.post("/api/v1/guides/from-doc", {
        doc_result_id: result.doc_result_id,
        med_start_date: today,
      });
      const guideId: number = (guideData.data ?? guideData).guide_id;

      // ③ AI 가이드 생성
      await apiClient.post(`/api/v1/guides/${guideId}/ai-generate`, { result_types: null });

      // ④ 가이드 페이지로 이동
      router.push(`/guide/${guideId}`);
    } catch {
      showToast("가이드 생성에 실패했습니다.");
      setConfirming(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-red-500">{error ?? "결과를 찾을 수 없습니다."}</p>
        <button onClick={() => router.back()} className="text-sm text-teal-500 underline">돌아가기</button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 면책 고지 */}
      <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/5 px-4 py-2.5 text-xs text-orange-500">
        ⚠️ 본 서비스는 참고용이며, 정확한 복약은 의사/약사와 상담하세요.
      </div>

      {/* 헤더 */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">📋 분석 결과 확인</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(result.created_at).toLocaleDateString("ko-KR", {
              year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
            })}
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
        >
          ← 목록
        </button>
      </div>

      {/* 섹션 1: 기본 정보 */}
      <div className="mb-4 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold text-teal-500">🏥 기본 정보</h2>
        <div className="space-y-3">
          {/* 의료기관명 */}
          <div className="flex items-center justify-between gap-3">
            <span className="w-20 shrink-0 text-xs text-muted-foreground">의료기관명</span>
            {editingField === "hospital_name" ? (
              <input
                autoFocus
                value={hospitalName}
                onChange={(e) => setHospitalName(e.target.value)}
                onBlur={() => setEditingField(null)}
                className="flex-1 rounded-lg border border-teal-500/40 bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none"
                placeholder="의료기관명 입력"
              />
            ) : (
              <span
                onClick={() => setEditingField("hospital_name")}
                className="flex-1 cursor-pointer rounded-lg px-3 py-1.5 text-sm hover:bg-muted"
              >
                {hospitalName || <span className="text-muted-foreground">미입력 — 탭하여 입력</span>}
              </span>
            )}
          </div>

          {/* 진료일 */}
          <div className="flex items-center justify-between gap-3">
            <span className="w-20 shrink-0 text-xs text-muted-foreground">진료일</span>
            {editingField === "visit_date" ? (
              <input
                autoFocus
                type="date"
                value={visitDate}
                onChange={(e) => setVisitDate(e.target.value)}
                onBlur={() => setEditingField(null)}
                className="flex-1 rounded-lg border border-teal-500/40 bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none"
              />
            ) : (
              <span
                onClick={() => setEditingField("visit_date")}
                className="flex-1 cursor-pointer rounded-lg px-3 py-1.5 text-sm hover:bg-muted"
              >
                {visitDate || <span className="text-muted-foreground">미입력 — 탭하여 입력</span>}
              </span>
            )}
          </div>

          {/* 진단명 */}
          <div className="flex items-center justify-between gap-3">
            <span className="w-20 shrink-0 text-xs text-muted-foreground">진단명</span>
            {editingField === "diagnosis_name" ? (
              <input
                autoFocus
                value={diagnosisName}
                onChange={(e) => setDiagnosisName(e.target.value)}
                onBlur={() => setEditingField(null)}
                className="flex-1 rounded-lg border border-teal-500/40 bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none"
                placeholder="진단명 입력"
              />
            ) : (
              <span
                onClick={() => setEditingField("diagnosis_name")}
                className="flex-1 cursor-pointer rounded-lg px-3 py-1.5 text-sm hover:bg-muted"
              >
                {diagnosisName || <span className="text-muted-foreground">미입력 — 탭하여 입력</span>}
              </span>
            )}
          </div>

          {/* 전체 신뢰도 */}
          <div className="flex items-center justify-between gap-3">
            <span className="w-20 shrink-0 text-xs text-muted-foreground">전체 신뢰도</span>
            <div className="flex-1 px-3">
              <ConfidenceBar value={result.overall_confidence} />
            </div>
          </div>
        </div>
      </div>

      {/* 섹션 2: 약물 목록 */}
      {medications.length > 0 && (
        <div className="mb-4 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 text-sm font-semibold text-teal-500">💊 처방 약물</h2>
          <div className="space-y-4">
            {medications.map((med, idx) => (
              <div
                key={idx}
                className={`rounded-lg border p-4 ${
                  !med.timing || med.confidence === null || med.confidence < 0.7
                    ? "border-orange-500/30 bg-orange-500/5"
                    : "border-border bg-background"
                }`}
              >
                {/* 약품명 */}
                <div className="mb-3 flex items-center justify-between gap-2">
                  {editingField === `med_name_${idx}` ? (
                    <input
                      autoFocus
                      value={med.medication_name}
                      onChange={(e) => updateMedication(idx, "medication_name", e.target.value)}
                      onBlur={() => setEditingField(null)}
                      className="flex-1 rounded-lg border border-teal-500/40 bg-background px-3 py-1.5 text-sm font-semibold text-foreground focus:outline-none"
                    />
                  ) : (
                    <span
                      onClick={() => setEditingField(`med_name_${idx}`)}
                      className="cursor-pointer text-sm font-semibold text-foreground hover:text-teal-400"
                    >
                      {med.medication_name}
                    </span>
                  )}
                  <ConfidenceBar value={med.confidence} />
                </div>

                {/* 용량 / 횟수 / 기간 */}
                <div className="mb-3 grid grid-cols-3 gap-2">
                  {(["dosage", "frequency", "duration_days"] as const).map((field) => {
                    const labels: Record<string, string> = { dosage: "용량", frequency: "횟수", duration_days: "기간(일)" };
                    const val = med[field];
                    const editKey = `med_${field}_${idx}`;
                    return (
                      <div key={field}>
                        <p className="mb-1 text-[10px] text-muted-foreground">{labels[field]}</p>
                        {editingField === editKey ? (
                          <input
                            autoFocus
                            type={field === "duration_days" ? "number" : "text"}
                            value={val ?? ""}
                            onChange={(e) => updateMedication(idx, field, field === "duration_days" ? Number(e.target.value) : e.target.value)}
                            onBlur={() => setEditingField(null)}
                            className="w-full rounded-lg border border-teal-500/40 bg-background px-2 py-1 text-xs text-foreground focus:outline-none"
                          />
                        ) : (
                          <span
                            onClick={() => setEditingField(editKey)}
                            className="block cursor-pointer rounded px-2 py-1 text-xs text-foreground hover:bg-muted"
                          >
                            {val ?? <span className="text-muted-foreground">미입력</span>}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* 복용시점 */}
                <div>
                  <p className="mb-1.5 text-[10px] text-muted-foreground">복용시점</p>
                  {!med.timing && (
                    <p className="mb-1.5 text-xs text-orange-400">⚠️ 미확인 — 아래에서 선택하세요</p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {TIMING_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => {
                          updateMedication(idx, "timing", opt);
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
                        className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-teal-500/40 focus:outline-none"
                      />
                      <button
                        onClick={() => {
                          updateMedication(idx, "timing", directInputVal[idx] ?? "");
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
            ))}
          </div>
        </div>
      )}

      {/* OCR 원문 */}
      {result.ocr_raw_text && (
        <div className="mb-4 rounded-xl border border-border bg-card p-5">
          <button
            onClick={() => setShowOcr((v) => !v)}
            className="flex w-full items-center justify-between text-sm font-semibold text-muted-foreground hover:text-foreground"
          >
            <span>🔍 OCR 원문</span>
            <span>{showOcr ? "▲" : "▼"}</span>
          </button>
          {showOcr && (
            <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {result.ocr_raw_text}
            </pre>
          )}
        </div>
      )}

      {/* 버튼 */}
      <div className="flex gap-3">
        <button
          onClick={() => router.push("/docs")}
          disabled={confirming}
          className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-40"
        >
          새 문서 분석
        </button>
        <button
          onClick={handleConfirm}
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

      {toast && (
        <div className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-3 text-sm text-red-400 shadow-lg lg:bottom-6">
          {toast}
        </div>
      )}
    </div>
  );
}
