"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import apiClient from "@/lib/axios";
import ReactMarkdown from "react-markdown";

interface Medication {
  medication_name: string;
  dosage: string;
  frequency: string;
  timing: string;
  duration_days: number;
  confidence: number;
}

interface ResultDetail {
  doc_result_id: number;
  document_type: string;
  overall_confidence: number | null;
  raw_summary: string | null;
  ocr_raw_text: string | null;
  created_at: string;
  analysis_json?: {
    medications?: Medication[];
    hospital_name?: string;
    document_type?: string;
  };
}

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted-foreground">신뢰도 정보 없음</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.9 ? "bg-teal-500" : value >= 0.7 ? "bg-yellow-500" : "bg-red-500";
  const textColor = value >= 0.9 ? "text-teal-500" : value >= 0.7 ? "text-yellow-500" : "text-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-32 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm font-semibold ${textColor}`}>{pct}%</span>
    </div>
  );
}

export default function ResultDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [result, setResult] = useState<ResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOcr, setShowOcr] = useState(false);

  useEffect(() => {
    apiClient
      .get(`/api/v1/medical-doc/results/${id}`)
      .then(({ data }) => setResult(data.data))
      .catch(() => setError("결과를 불러오는 데 실패했습니다."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4">
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
          <h1 className="text-xl font-bold text-foreground">✅ 분석 결과</h1>
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

      {/* 약품 목록 */}
      {result.analysis_json?.medications && result.analysis_json.medications.length > 0 && (
        <div className="mb-4 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold text-teal-500">💊 처방 약품 목록</h2>
          <div className="space-y-3">
            {result.analysis_json.medications.map((med, i) => {
              const pct = Math.round(med.confidence * 100);
              const color = med.confidence >= 0.9 ? "bg-teal-500" : med.confidence >= 0.7 ? "bg-yellow-500" : "bg-red-500";
              const textColor = med.confidence >= 0.9 ? "text-teal-500" : med.confidence >= 0.7 ? "text-yellow-500" : "text-red-500";
              return (
                <div key={i} className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">{med.medication_name}</span>
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className={`text-xs font-medium ${textColor}`}>{pct}%</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
                    <span>용량: {med.dosage}</span>
                    <span>횟수: {med.frequency}</span>
                    <span>복용법: {med.timing}</span>
                    <span>기간: {med.duration_days}일</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 문서 요약 */}
      <div className="mb-4 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-3 text-sm font-semibold text-teal-500">📋 문서 요약</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">문서 종류</span>
            <span className="font-medium text-foreground">{result.document_type}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">전체 신뢰도</span>
            <ConfidenceBar value={result.overall_confidence} />
          </div>
        </div>
      </div>

      {/* AI 요약 */}
      {result.raw_summary && (
        <div className="mb-4 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold text-teal-500">📝 AI 요약</h2>
          <div className="prose prose-sm max-w-none text-sm text-foreground">
            <ReactMarkdown>{result.raw_summary}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* OCR 원문 (접기/펼치기) */}
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
          className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
        >
          새 문서 분석
        </button>
        <button
          onClick={() => router.push("/docs/results")}
          className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500"
        >
          기록 목록
        </button>
      </div>
    </div>
  );
}
