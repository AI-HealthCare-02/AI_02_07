"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import apiClient from "@/lib/axios";
import TabToday      from "./_components/TabToday";
import TabDrugDetail from "./_components/TabDrugDetail";
import TabCaution    from "./_components/TabCaution";
import TabHistory    from "./_components/TabHistory";
import TabReminder   from "./_components/TabReminder";

interface GuideDetail {
  guide_id: number;
  title: string;
  hospital_name: string | null;
  diagnosis_name: string | null;
  med_start_date: string;
  med_end_date: string | null;
  guide_status: string;
  input_method: string;
  medications: { guide_medication_id: number; medication_name: string; dosage: string | null; frequency: string | null; timing: string | null }[];
  created_at: string;
}

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

const TABS = [
  { key: "today",   label: "💊 오늘의 복약" },
  { key: "drug",    label: "🔬 약물 상세"   },
  { key: "caution", label: "⚠️ 주의사항"    },
  { key: "history", label: "📆 복약 기록"   },
  { key: "remind",  label: "🔔 복약 알림"   },
] as const;
type TabKey = typeof TABS[number]["key"];

export default function GuideDetailPage() {
  const router = useRouter();
  const params = useParams();
  const guideId = Number(params.id);

  const [guide, setGuide] = useState<GuideDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("today");
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2400);
  };

  useEffect(() => {
    apiClient
      .get(`/api/v1/guides/${guideId}`)
      .then(({ data }) => setGuide(data))
      .catch(() => showToast("가이드를 불러오지 못했습니다.", "err"))
      .finally(() => setLoading(false));
  }, [guideId]);

  const handleDelete = async () => {
    if (!guide || !confirm(`"${guide.title}" 가이드를 삭제할까요?`)) return;
    setDeleting(true);
    try {
      await apiClient.delete(`/api/v1/guides/${guideId}`);
      router.replace("/guide");
    } catch {
      showToast("삭제에 실패했습니다.", "err");
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  if (!guide) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-red-500">가이드를 찾을 수 없습니다.</p>
        <button onClick={() => router.push("/guide")} className="text-sm text-teal-500 underline">목록으로</button>
      </div>
    );
  }

  const remainingDays = guide.med_end_date
    ? Math.max(0, Math.ceil((new Date(guide.med_end_date).getTime() - Date.now()) / 86400000))
    : null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-5">
        <button onClick={() => router.push("/guide")} className="mb-3 text-xs text-muted-foreground hover:text-foreground">
          ← 목록으로
        </button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-foreground">{guide.title}</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {guide.med_start_date}
              {guide.hospital_name && ` · ${guide.hospital_name}`}
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
              onClick={() => window.print()}
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

      {/* 요약 바 */}
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: "진단",     value: guide.diagnosis_name ?? "-" },
          { label: "처방약물", value: `${guide.medications.length}종` },
          { label: "복약시작", value: guide.med_start_date },
          { label: "남은일수", value: remainingDays !== null ? `D-${remainingDays}` : "상시" },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border border-border bg-card px-3 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground">{label}</p>
            <p className="mt-0.5 text-xs font-semibold text-foreground truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* 탭 바 */}
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

      {/* 탭 콘텐츠 */}
      {tab === "today"   && <TabToday      guideId={guideId} showToast={showToast} />}
      {tab === "drug"    && <TabDrugDetail guideId={guideId} medications={guide.medications} />}
      {tab === "caution" && <TabCaution    guideId={guideId} />}
      {tab === "history" && <TabHistory    guideId={guideId} />}
      {tab === "remind"  && <TabReminder   guideId={guideId} showToast={showToast} medications={guide.medications} />}

      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다. 의료적 판단은 반드시 담당 의사 또는 약사와 상담하세요.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
