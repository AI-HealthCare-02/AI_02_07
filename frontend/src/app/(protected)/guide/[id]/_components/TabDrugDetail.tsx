"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

function Section({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-teal-400">{label}</p>
      <p className="text-muted-foreground leading-relaxed">{value}</p>
    </div>
  );
}

interface Medication {
  guide_medication_id: number;
  medication_name: string;
  dosage: string | null;
  frequency: string | null;
  timing: string | null;
}

interface AiResult {
  result_type: string;
  content: Record<string, unknown>;
}

interface DrugDetail {
  name: string;
  mechanism_summary?: string;
  how_to_take?: string;
  side_effects?: string[];
  side_effect_tips?: string;
  food_interactions?: string;
  warnings?: string[];
  faq?: { q: string; a: string }[];
  error?: string;
}

interface MedSummary {
  name: string;
  summary?: string;
  how_to_take?: string;
  caution?: string;
}

export default function TabDrugDetail({
  guideId,
  medications,
}: {
  guideId: number;
  medications: Medication[];
}) {
  const [selected, setSelected] = useState<Medication | null>(medications[0] ?? null);
  const [aiResults, setAiResults] = useState<AiResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}/ai-results`)
      .then(({ data }) => setAiResults(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [guideId]);

  // RT_DRUG_DETAIL: { drugs: [{name, mechanism_summary, how_to_take, side_effects, food_interactions, warnings, faq}] }
  // RT_MEDICATION:   { medications: [{name, summary, how_to_take, caution}] }
  const drugDetailResult = aiResults.find((r) => r.result_type === "RT_DRUG_DETAIL");
  const medicationResult = aiResults.find((r) => r.result_type === "RT_MEDICATION");

  // 선택된 약물에 해당하는 상세 데이터 추출
  const getDrugDetail = (): DrugDetail | null => {
    if (!drugDetailResult?.content) return null;
    const drugs = ((drugDetailResult.content as Record<string, unknown>).drugs ?? []) as DrugDetail[];
    if (drugs.length === 0) return null;
    if (selected)
      return (
        drugs.find((d) => d.name?.includes(selected.medication_name.split(" ")[0])) ?? drugs[0]
      );
    return drugs[0];
  };

  const getMedSummary = (): MedSummary | null => {
    if (!medicationResult?.content) return null;
    const meds = ((medicationResult.content as Record<string, unknown>).medications ?? []) as MedSummary[];
    if (meds.length === 0) return null;
    if (selected)
      return (
        meds.find((m) => m.name?.includes(selected.medication_name.split(" ")[0])) ?? meds[0]
      );
    return meds[0];
  };

  const drugDetail = getDrugDetail();
  const medSummary = getMedSummary();

  return (
    <div className="space-y-4">
      {/* 약물 선택 탭 */}
      {medications.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {medications.map((m) => (
            <button
              key={m.guide_medication_id}
              onClick={() => setSelected(m)}
              className={`shrink-0 rounded-xl border px-3 py-1.5 text-xs font-medium transition ${
                selected?.guide_medication_id === m.guide_medication_id
                  ? "border-teal-500/50 bg-teal-500/10 text-teal-400"
                  : "border-border bg-card text-muted-foreground hover:border-teal-500/30"
              }`}
            >
              {m.medication_name}
            </button>
          ))}
        </div>
      )}

      {/* 선택된 약물 기본 정보 */}
      {selected && (
        <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
          <h3 className="text-base font-bold text-foreground">{selected.medication_name}</h3>
          <div className="space-y-1.5 text-sm">
            {selected.dosage    && <p className="text-muted-foreground">용량: {selected.dosage}</p>}
            {selected.frequency && <p className="text-muted-foreground">횟수: {selected.frequency}</p>}
            {selected.timing    && <p className="text-muted-foreground">복용 시점: {selected.timing}</p>}
          </div>
        </div>
      )}

      {/* AI 생성 약물 상세 */}
      <div className="rounded-2xl border border-border bg-card p-5">
        <p className="mb-3 text-xs font-semibold text-teal-400">💬 AI 생성 약물 가이드</p>
        {loading ? (
          <div className="flex justify-center py-6">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : drugDetail ? (
          <div className="space-y-4 text-sm">
            {drugDetail.mechanism_summary && (
              <Section label="작용 원리" value={String(drugDetail.mechanism_summary)} />
            )}
            {drugDetail.how_to_take && (
              <Section label="복용법" value={String(drugDetail.how_to_take)} />
            )}
            {Array.isArray(drugDetail.side_effects) && drugDetail.side_effects.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold text-teal-400">부작용</p>
                <ul className="space-y-1">
                  {(drugDetail.side_effects as string[]).map((s, i) => (
                    <li key={i} className="text-muted-foreground">• {s}</li>
                  ))}
                </ul>
              </div>
            )}
            {drugDetail.food_interactions && (
              <Section label="식품 상호작용" value={String(drugDetail.food_interactions)} />
            )}
            {Array.isArray(drugDetail.warnings) && drugDetail.warnings.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold text-teal-400">주의사항</p>
                <ul className="space-y-1">
                  {(drugDetail.warnings as string[]).map((w, i) => (
                    <li key={i} className="text-muted-foreground">• {w}</li>
                  ))}
                </ul>
              </div>
            )}
            {Array.isArray(drugDetail.faq) && drugDetail.faq.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold text-foreground">💬 자주 묻는 질문</p>
                <div className="space-y-2">
                  {(drugDetail.faq as {q: string; a: string}[]).map((f, i) => (
                    <div key={i} className="rounded-xl border border-border p-3">
                      <p className="text-xs font-medium text-foreground">Q. {f.q}</p>
                      <p className="mt-1 text-xs text-muted-foreground">A. {f.a}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : medSummary ? (
          <div className="space-y-3 text-sm">
            {medSummary.summary && <Section label="요약" value={String(medSummary.summary)} />}
            {medSummary.how_to_take && <Section label="복용법" value={String(medSummary.how_to_take)} />}
            {medSummary.caution && <Section label="주의사항" value={String(medSummary.caution)} />}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">AI 가이드가 아직 생성되지 않았습니다.</p>
        )}
      </div>
    </div>
  );
}
