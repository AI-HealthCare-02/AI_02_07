"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/axios";

interface CautionItem {
  medication_name: string;
  caution_text: string;
  similarity: number;
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
        <p className="mb-2 text-sm font-bold text-red-400">🚨 응급 상황 안내</p>
        <ul className="space-y-1 text-xs text-muted-foreground">
          <li>• 가슴 통증, 호흡 곤란, 심한 두통이 갑자기 발생하면 즉시 119에 연락하세요.</li>
          <li>• 심한 근육통·근육 약화가 나타나면 즉시 복약을 중단하고 의사와 상담하세요.</li>
          <li>• 심한 알레르기 반응(두드러기, 얼굴 부종)이 나타나면 즉시 응급실을 방문하세요.</li>
        </ul>
      </div>

      {/* AI 주의사항 */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">⚠️ 약물별 주의사항</p>
          <span className="text-[10px] text-muted-foreground">출처: 약품 DB (RAG)</span>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : data?.cautions && data.cautions.length > 0 ? (
          <div className="divide-y divide-border">
            {data.cautions.map((c, i) => (
              <div key={i} className="px-4 py-3">
                <p className="mb-1 text-xs font-semibold text-teal-400">{c.medication_name}</p>
                <p className="text-xs text-muted-foreground leading-relaxed">{c.caution_text}</p>
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
          <p className="mb-2 text-xs font-semibold text-yellow-500">⚠️ 약품 DB 미조회 항목</p>
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
