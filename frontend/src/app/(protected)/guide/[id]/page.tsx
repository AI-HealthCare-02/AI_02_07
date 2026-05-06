"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import apiClient from "@/lib/axios";
import TabToday      from "./_components/TabToday";
import TabDrugDetail from "./_components/TabDrugDetail";
import TabCaution    from "./_components/TabCaution";
import TabHistory    from "./_components/TabHistory";
import TabReminder   from "./_components/TabReminder";
import { useAuthStore } from "@/store/auth-store";

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

// ── 스켈레톤 ──────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-muted ${className ?? ""}`} />;
}

function GuideDetailSkeleton() {
  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 lg:pb-8">
      {/* sticky 헤더 자리 */}
      <div className="sticky top-16 z-30 -mx-4 mb-5 border-b border-border bg-background/95 px-4 pb-3 pt-4 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-20" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-14 rounded-xl" />
            <Skeleton className="h-7 w-12 rounded-xl" />
            <Skeleton className="h-7 w-12 rounded-xl" />
          </div>
        </div>
        <Skeleton className="mt-2 h-5 w-48" />
        <Skeleton className="mt-1 h-3 w-32" />
      </div>
      {/* 요약 바 */}
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-xl border border-border bg-card px-3 py-2.5 text-center">
            <Skeleton className="mx-auto mb-1 h-2.5 w-10" />
            <Skeleton className="mx-auto h-3.5 w-14" />
          </div>
        ))}
      </div>
      {/* 탭 바 */}
      <div className="mb-5 flex gap-1 border-b border-border">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-8 w-16 rounded-none" />
        ))}
      </div>
      {/* 탭 콘텐츠 */}
      <div className="space-y-3">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    </div>
  );
}

const TABS = [
  { key: "today",   label: "오늘의 복약" },
  { key: "drug",    label: "약물 상세"   },
  { key: "caution", label: "주의사항"    },
  { key: "history", label: "복약 기록"   },
  { key: "remind",  label: "복약 알림"   },
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
  const user = useAuthStore((s) => s.user);

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

  const handlePrint = () => {
    if (!guide) return;
    const printArea = document.getElementById("guide-print-area");
    const content = printArea?.innerHTML ?? "";
    const tabLabel = TABS.find((t) => t.key === tab)?.label ?? tab;
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"/><title>${guide.title}</title><style>body{font-family:sans-serif;padding:32px;color:#111;font-size:13px;}h1{font-size:18px;margin-bottom:4px;}.meta{font-size:11px;color:#666;margin-bottom:20px;}.tab-label{font-size:13px;font-weight:700;margin:0 0 12px;border-bottom:1px solid #ddd;padding-bottom:4px;}button{display:none!important;}@media print{button{display:none!important;}}</style></head><body><h1>${guide.title}</h1><p class="meta">${guide.med_start_date}${guide.hospital_name ? " · " + guide.hospital_name : ""}${guide.diagnosis_name ? " · " + guide.diagnosis_name : ""}</p><div class="tab-label">${tabLabel}</div>${content}<p style="font-size:10px;color:#999;margin-top:32px;">본 자료는 건강 정보 제공 목적이며 의료적 판단을 대체하지 않습니다.</p></body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => { w.print(); w.close(); }, 400);
  };

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

  if (loading) return <GuideDetailSkeleton />;

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
    <div className="mx-auto max-w-3xl px-4 pb-24 lg:pb-8">

      {/* ── Sticky 헤더 ── */}
      <div className="sticky top-16 z-30 -mx-4 mb-5 border-b border-border bg-background/95 px-4 pb-3 pt-4 backdrop-blur-sm">
        {/* 뒤로가기 + 액션 버튼 */}
        <div className="flex items-center justify-between gap-2">
          <button
            onClick={() => router.push("/guide")}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition hover:text-foreground"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            목록
          </button>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => router.push(`/guide/${guideId}/edit`)}
              className="inline-flex items-center gap-1 rounded-xl border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition hover:border-teal-500/40 hover:text-teal-400"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              수정
            </button>
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1 rounded-xl border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition hover:border-teal-500/40 hover:text-teal-400"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
              PDF
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="inline-flex items-center gap-1 rounded-xl border border-red-500/30 px-2.5 py-1.5 text-xs text-red-400 transition hover:bg-red-500/10 disabled:opacity-40"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
              삭제
            </button>
          </div>
        </div>
        {/* 제목 */}
        <h1 className="mt-2 text-lg font-bold text-foreground leading-snug">{guide.title}</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {guide.med_start_date}
          {guide.hospital_name && ` · ${guide.hospital_name}`}
        </p>
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
            <p className="mt-0.5 truncate text-xs font-semibold text-foreground">{value}</p>
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
      <div id="guide-print-area">
        {tab === "today"   && <TabToday      guideId={guideId} showToast={showToast} />}
        {tab === "drug"    && <TabDrugDetail guideId={guideId} medications={guide.medications} />}
        {tab === "caution" && <TabCaution    guideId={guideId} />}
        {tab === "history" && <TabHistory    guideId={guideId} />}
        {tab === "remind"  && <TabReminder   guideId={guideId} showToast={showToast} medications={guide.medications} isKakaoUser={user?.provider_code === "KAKAO"} />}
      </div>

      <p className="mt-8 text-center text-[11px] text-muted-foreground">
        본 서비스는 건강 정보 제공 목적이며, 진단·치료·처방 변경을 대신하지 않습니다. 의료적 판단은 반드시 담당 의사 또는 약사와 상담하세요.
      </p>

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
