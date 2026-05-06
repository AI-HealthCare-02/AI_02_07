"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

interface CautionItem {
  medication_name: string;
  emergency_signs?: string[];
  drug_interactions?: string[];
  age_restrictions?: string;
  general?: string[];
}

interface CautionContent {
  cautions: CautionItem[];
  warnings: string[];
  disclaimer: string;
}

export default function TabCaution({ guideId }: { guideId: number }) {
  const [data, setData] = useState<CautionContent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}/ai-results?result_type=RT_CAUTION`)
      .then(({ data: res }) => {
        const results = Array.isArray(res) ? res : [];
        const r = results[0];
        if (r?.content) setData(r.content as CautionContent);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [guideId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      {/* 응급 상황 */}
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4">
        <div className="mb-2 flex items-center gap-1.5 text-sm font-bold text-red-400">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          응급 상황 안내
        </div>
        <ul className="space-y-1 text-xs text-muted-foreground">
          <li>• 가슴 통증, 호흡 곤란, 심한 두통이 갑자기 발생하면 즉시 119에 연락하세요.</li>
          <li>• 심한 근육통·근육 약화가 나타나면 즉시 복약을 중단하고 의사와 상담하세요.</li>
          <li>• 심한 알레르기 반응(두드러기, 얼굴 부종)이 나타나면 즉시 응급실을 방문하세요.</li>
        </ul>
      </div>

      {/* AI 주의사항 */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            약물별 주의사항
          </div>
          <span className="text-[10px] text-muted-foreground">출처: 약품 DB (RAG)</span>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : data?.cautions && data.cautions.length > 0 ? (
          <div className="divide-y divide-border">
            {data.cautions.map((c, i) => (
              <div key={i} className="px-4 py-4 space-y-3">
                <h3 className="text-xs font-semibold text-teal-400">{c.medication_name}</h3>

                {c.emergency_signs && c.emergency_signs.length > 0 && (
                  <section>
                    <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-red-400">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                      응급 증상
                    </div>
                    <ul className="space-y-0.5 text-xs text-muted-foreground">
                      {c.emergency_signs.map((s, j) => <li key={j}>• {s}</li>)}
                    </ul>
                  </section>
                )}

                {c.drug_interactions && c.drug_interactions.length > 0 && (
                  <section>
                    <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-yellow-400">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                      병용 주의
                    </div>
                    <ul className="space-y-0.5 text-xs text-muted-foreground">
                      {c.drug_interactions.map((s, j) => <li key={j}>• {s}</li>)}
                    </ul>
                  </section>
                )}

                {c.age_restrictions && (
                  <section>
                    <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-blue-400">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                      연령·특수 환자 주의
                    </div>
                    <p className="text-xs text-muted-foreground">{c.age_restrictions}</p>
                  </section>
                )}

                {c.general && c.general.length > 0 && (
                  <section>
                    <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                      일반 주의사항
                    </div>
                    <ul className="space-y-0.5 text-xs text-muted-foreground">
                      {c.general.map((s, j) => <li key={j}>• {s}</li>)}
                    </ul>
                  </section>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-6 text-sm text-muted-foreground">AI 주의사항이 아직 생성되지 않았습니다.</p>
        )}
      </div>

      {/* DB에서 못 찾은 약물 경고 */}
      {data?.warnings && data.warnings.length > 0 && (
        <div className="rounded-2xl border border-yellow-500/30 bg-yellow-500/5 p-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-yellow-500">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            약품 DB 미조회 항목
          </div>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {data.warnings.map((w, i) => <li key={i}>• {w}</li>)}
          </ul>
        </div>
      )}

      {/* 면책 */}
      {data?.disclaimer && (
        <p className="text-[11px] text-muted-foreground leading-relaxed">{data.disclaimer}</p>
      )}
    </div>
  );
}
