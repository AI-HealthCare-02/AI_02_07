"use client";

import { useState } from "react";

interface Drug {
  id: number;
  name: string;
  category: string;
  warnings: string[];
  description: string;
  dosage: string;
  side_effects: string;
  food_interaction: string;
  faq: { q: string; a: string }[];
}

const MOCK_DRUGS: Drug[] = [
  {
    id: 1,
    name: "아모디핀정 5mg",
    category: "칼슘채널차단제",
    warnings: ["병용 주의"],
    description: "혈압을 낮추고 협심증을 치료하는 칼슘채널차단제입니다. 혈관을 이완시켜 혈압을 조절합니다.",
    dosage: "1일 1회 1정, 식사와 무관하게 복용",
    side_effects: "두통, 안면홍조, 발목 부종이 나타날 수 있습니다. 심한 경우 의사와 상담하세요.",
    food_interaction: "자몽 주스와 함께 복용 시 약물 농도가 높아질 수 있으므로 피하세요.",
    faq: [
      { q: "약을 먹고 발목이 부었어요?", a: "경미한 부종은 흔한 부작용입니다. 심하거나 지속되면 의사와 상담하세요." },
      { q: "혈압이 정상이 되면 약을 끊어도 되나요?", a: "임의로 중단하지 마세요. 반드시 의사와 상담 후 결정하세요." },
    ],
  },
  {
    id: 2,
    name: "오메프라졸캡슐 20mg",
    category: "양성자펌프억제제",
    warnings: [],
    description: "위산 분비를 억제하여 위궤양, 역류성 식도염을 치료합니다.",
    dosage: "1일 1회 1캡슐, 식전 30분 복용",
    side_effects: "두통, 설사, 복통이 드물게 나타날 수 있습니다.",
    food_interaction: "특별한 음식 제한은 없으나 식전 복용을 권장합니다.",
    faq: [
      { q: "식후에 먹어도 되나요?", a: "식전 30분 복용이 효과적이지만, 잊었다면 식후에 복용하세요." },
    ],
  },
  {
    id: 3,
    name: "로수바스타틴정 10mg",
    category: "스타틴계",
    warnings: ["연령 제한 없음"],
    description: "콜레스테롤 합성을 억제하여 고지혈증을 치료합니다.",
    dosage: "1일 1회 1정, 저녁 식후 복용",
    side_effects: "근육통, 간 수치 상승이 드물게 나타날 수 있습니다.",
    food_interaction: "자몽 주스는 피하세요.",
    faq: [
      { q: "근육이 아픈데 약 때문인가요?", a: "스타틴 계열 약물의 드문 부작용입니다. 심하면 즉시 의사와 상담하세요." },
    ],
  },
];

export default function TabDrugDetail({ guideId }: { guideId: number }) {
  const [selected, setSelected] = useState<Drug>(MOCK_DRUGS[0]);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="space-y-4">
      {/* 약물 선택 탭 */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {MOCK_DRUGS.map((d) => (
          <button
            key={d.id}
            onClick={() => { setSelected(d); setOpenFaq(null); }}
            className={`shrink-0 rounded-xl border px-3 py-1.5 text-xs font-medium transition ${
              selected.id === d.id
                ? "border-teal-500/50 bg-teal-500/10 text-teal-400"
                : "border-border bg-card text-muted-foreground hover:border-teal-500/30"
            }`}
          >
            {d.name}
          </button>
        ))}
      </div>

      {/* 약물 카드 */}
      <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
        {/* 헤더 */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-foreground">{selected.name}</h3>
            <span className="mt-1 inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-400">
              {selected.category}
            </span>
          </div>
          <div className="flex flex-col gap-1 text-right">
            {selected.warnings.length > 0 ? (
              selected.warnings.map((w) => (
                <span key={w} className="inline-flex items-center rounded-full bg-orange-500/10 px-2 py-0.5 text-[10px] text-orange-400">
                  ⚠️ {w}
                </span>
              ))
            ) : (
              <span className="inline-flex items-center rounded-full bg-teal-500/10 px-2 py-0.5 text-[10px] text-teal-400">
                ✅ 주의사항 없음
              </span>
            )}
          </div>
        </div>

        {/* 상세 정보 */}
        {[
          { label: "작용 원리", value: selected.description },
          { label: "복용법",   value: selected.dosage },
          { label: "부작용",   value: selected.side_effects },
          { label: "식품 상호작용", value: selected.food_interaction },
        ].map(({ label, value }) => (
          <div key={label}>
            <p className="mb-1 text-xs font-semibold text-teal-400">{label}</p>
            <p className="text-sm text-muted-foreground leading-relaxed">{value}</p>
          </div>
        ))}

        {/* FAQ */}
        {selected.faq.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold text-foreground">💬 자주 묻는 질문 (AI 생성)</p>
            <div className="space-y-2">
              {selected.faq.map((f, i) => (
                <div key={i} className="rounded-xl border border-border overflow-hidden">
                  <button
                    onClick={() => setOpenFaq(openFaq === i ? null : i)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-foreground hover:bg-muted/30"
                  >
                    <span>Q. {f.q}</span>
                    <span className="text-muted-foreground">{openFaq === i ? "▲" : "▼"}</span>
                  </button>
                  {openFaq === i && (
                    <div className="border-t border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                      A. {f.a}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
