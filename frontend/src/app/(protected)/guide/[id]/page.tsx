"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import TabToday      from "./_components/TabToday";
import TabDrugDetail from "./_components/TabDrugDetail";
import TabCaution    from "./_components/TabCaution";
import TabHistory    from "./_components/TabHistory";
import TabReminder   from "./_components/TabReminder";
// import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
interface GuideDetail {
  guide_id: number;
  title: string;
  hospital_name: string | null;
  department: string | null;
  visit_date: string;
  guide_status_code: string;
  diagnosis_name: string | null;
  medication_count: number;
  med_start_date: string | null;
  med_end_date: string | null;
  remaining_days: number | null;
  weekly_compliance_rate: number | null;
}

// ── Mock ──────────────────────────────────────────────────
const MOCK_DETAIL: GuideDetail = {
  guide_id: 1,
  title: "고혈압·고지혈증 관리 가이드",
  hospital_name: "서울대학교병원",
  department: "내과",
  visit_date: "2026-03-20",
  guide_status_code: "GS_ACTIVE",
  diagnosis_name: "고혈압, 고지혈증",
  medication_count: 3,
  med_start_date: "2026-03-20",
  med_end_date: "2026-04-19",
  remaining_days: 24,
  weekly_compliance_rate: 0.87,
};

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

// ── 탭 정의 ───────────────────────────────────────────────
const TABS = [
  { key: "today",  label: "💊 오늘의 복약" },
  { key: "drug",   label: "🔬 약물 상세"   },
  { key: "caution",label: "⚠️ 주의사항"    },
  { key: "history",label: "📆 복약 기록"   },
  { key: "remind", label: "🔔 복약 알림"   },
] as const;
type TabKey = typeof TABS[number]["key"];

// ── 메인 ──────────────────────────────────────────────────
export default function GuideDetailPage() {
  const router = useRouter();
  const params = useParams();
  const guideId = Number(params.id);

  const [guide]   = useState<GuideDetail>(MOCK_DETAIL);
  const [tab, setTab] = useState<TabKey>("today");
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  const handleDelete = async () => {
    if (!confirm(`"${guide.title}" 가이드를 삭제할까요?`)) return;
    setDeleting(true);
    try {
      // await apiClient.delete(`/api/v1/guides/${guideId}`);
      await new Promise((r) => setTimeout(r, 400));
      router.replace("/guide");
    } catch {
      showToast("삭제에 실패했습니다.", "err");
      setDeleting(false);
    }
  };

  const handlePrint = () => window.print();

  const compliancePct = guide.weekly_compliance_rate
    ? Math.round(guide.weekly_compliance_rate * 100)
    : 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 pb-24 lg:pb-8">

      {/* ── 헤더 ── */}
      <div className="mb-5">
        <button onClick={() => router.push("/guide")} className="mb-3 text-xs text-muted-foreground hover:text-foreground">
          ← 목록으로
        </button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-foreground">{guide.title}</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {guide.visit_date}
              {guide.hospital_name && ` · ${guide.hospital_name}`}
              {guide.department && ` ${guide.department}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push(`/guide/${guideId}/edit`)}
              className="rounded-xl border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:border-teal-500/40 hover:text-teal-400"
            >
              ✏️ 수정
            </button>
            <button
              onClick={handlePrint}
              className="rounded-xl border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:border-teal-500/40 hover:text-teal-400"
            >
              🖨️ PDF
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-xl border border-red-500/30 px-3 py-1.5 text-xs text-red-400 transition hover:bg-red-500/10 disabled:opacity-40"
            >
              🗑 삭제
            </button>
          </div>
        </div>
      </div>

      {/* ── 요약 바 ── */}
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {[
          { label: "진단",     value: guide.diagnosis_name ?? "-" },
          { label: "처방약물", value: `${guide.medication_count}종` },
          { label: "복약기간", value: guide.med_start_date ? `${guide.med_start_date} ~` : "-" },
          { label: "남은일수", value: guide.remaining_days !== null ? `D-${guide.remaining_days}` : "상시" },
          { label: "이번주 복약 이행률", value: `${compliancePct}%` },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border border-border bg-card px-3 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground">{label}</p>
            <p className="mt-0.5 text-xs font-semibold text-foreground truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* ── 탭 바 ── */}
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border pb-0">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`shrink-0 border-b-2 px-3 pb-2.5 pt-1 text-xs font-medium transition-colors ${
              tab === t.key
                ? "border-teal-400 text-teal-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── 탭 콘텐츠 ── */}
      {tab === "today"   && <TabToday      guideId={guideId} showToast={showToast} />}
      {tab === "drug"    && <TabDrugDetail guideId={guideId} />}
      {tab === "caution" && <TabCaution    guideId={guideId} />}
      {tab === "history" && <TabHistory    guideId={guideId} />}
      {tab === "remind"  && <TabReminder   guideId={guideId} showToast={showToast} />}

      {/* 면책 고지 */}
      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다. 의료적 판단은 반드시 담당 의사 또는 약사와 상담하세요.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
