"use client";

interface CautionItem {
  drug_name: string;
  content: string;
  note: string;
}

const MOCK_CAUTIONS: CautionItem[] = [
  { drug_name: "아모디핀정 5mg",      content: "자몽 주스와 병용 시 혈중 농도 상승",  note: "자몽 주스 섭취 금지" },
  { drug_name: "로수바스타틴정 10mg", content: "근육독성 위험 증가 (피브레이트 계열)", note: "의사 처방 필수"       },
];

export default function TabCaution({ guideId }: { guideId: number }) {
  return (
    <div className="space-y-4">
      {/* 출처 */}
      <p className="text-xs text-muted-foreground">
        출처: 식품의약품안전처 의약품 안전사용 서비스
      </p>

      {/* 응급 상황 */}
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4">
        <p className="mb-2 text-sm font-bold text-red-400">🚨 응급 상황 안내</p>
        <ul className="space-y-1 text-xs text-muted-foreground">
          <li>• 가슴 통증, 호흡 곤란, 심한 두통이 갑자기 발생하면 즉시 119에 연락하세요.</li>
          <li>• 심한 근육통·근육 약화가 나타나면 즉시 복약을 중단하고 의사와 상담하세요.</li>
          <li>• 심한 알레르기 반응(두드러기, 얼굴 부종)이 나타나면 즉시 응급실을 방문하세요.</li>
        </ul>
      </div>

      {/* 병용 주의 */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <p className="text-sm font-semibold text-foreground">🚫 병용 주의</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">약물명</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">주의 내용</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">비고</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {MOCK_CAUTIONS.map((c, i) => (
                <tr key={i} className="hover:bg-muted/20">
                  <td className="px-4 py-3 text-xs font-medium text-foreground">{c.drug_name}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{c.content}</td>
                  <td className="px-4 py-3 text-xs text-orange-400">{c.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 연령·임부 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[
          { label: "✅ 연령 제한", value: "해당 없음" },
          { label: "✅ 임부 주의", value: "해당 없음" },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-2xl border border-border bg-card px-4 py-3">
            <p className="text-xs font-semibold text-teal-400">{label}</p>
            <p className="mt-1 text-sm text-muted-foreground">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
