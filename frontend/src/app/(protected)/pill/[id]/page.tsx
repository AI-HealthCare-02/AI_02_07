"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
interface PillDetail {
  analysis_id: number;
  product_name: string | null;
  active_ingredients: string | null;
  efficacy: string | null;
  usage_method: string | null;
  warning: string | null;
  caution: string | null;
  interactions: string | null;
  side_effects: string | null;
  storage_method: string | null;
  gpt_model_version: string | null;
  created_at: string;
}

// ── 정보 행 ────────────────────────────────────────────────
function InfoRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="border-b border-border py-3 last:border-0">
      <p className="mb-1 text-xs font-semibold text-teal-500">{label}</p>
      <p className="text-sm text-foreground">{value}</p>
    </div>
  );
}

// ── 경고 행 ────────────────────────────────────────────────
function WarnRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="border-b border-yellow-500/20 py-3 last:border-0">
      <p className="mb-1 text-xs font-semibold text-yellow-500">{label}</p>
      <p className="text-sm text-foreground">{value}</p>
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────
export default function PillDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [detail, setDetail] = useState<PillDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    apiClient
      .get(`/api/v1/pill-analysis/${id}`)
      .then(({ data }) => setDetail(data.data))
      .catch(() => setError("분석 결과를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [id]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await apiClient.delete(`/api/v1/pill-analysis/${id}`);
      router.replace("/pill");
    } catch {
      setError("삭제에 실패했습니다.");
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-center">
        <div className="mb-4 text-5xl">❌</div>
        <p className="text-sm text-muted-foreground">
          {error ?? "결과를 찾을 수 없습니다."}
        </p>
        <button
          onClick={() => router.back()}
          className="mt-6 rounded-xl border border-border px-6 py-2.5 text-sm text-muted-foreground transition hover:text-foreground"
        >
          ← 돌아가기
        </button>
      </div>
    );
  }

  const hasWarning = detail.warning || detail.caution || detail.interactions || detail.side_effects;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="text-muted-foreground transition hover:text-foreground"
        >
          ←
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold text-foreground">
            {detail.product_name ?? "알 수 없는 약품"}
          </h1>
          <p className="text-xs text-muted-foreground">
            분석일: {detail.created_at.slice(0, 10)}
            {detail.gpt_model_version && (
              <span className="ml-2 opacity-60">
                · {detail.gpt_model_version}
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* 기본 정보 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-1 text-sm font-semibold text-teal-500">
            💊 약품 기본 정보
          </h2>
          <InfoRow label="제품명" value={detail.product_name} />
          <InfoRow label="주성분" value={detail.active_ingredients} />
          <InfoRow label="효능 · 효과" value={detail.efficacy} />
          <InfoRow label="복용 방법" value={detail.usage_method} />
          <InfoRow label="보관 방법" value={detail.storage_method} />
        </div>

        {/* 주의사항 */}
        {hasWarning && (
          <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-5">
            <h2 className="mb-1 text-sm font-semibold text-yellow-500">
              ⚠️ 주의사항
            </h2>
            <WarnRow label="경고" value={detail.warning} />
            <WarnRow label="주의" value={detail.caution} />
            <WarnRow label="약물 상호작용" value={detail.interactions} />
            <WarnRow label="부작용" value={detail.side_effects} />
          </div>
        )}

        {/* 결과 없음 안내 */}
        {!detail.product_name && !detail.efficacy && (
          <div className="rounded-xl border border-border bg-card p-5 text-center text-sm text-muted-foreground">
            AI가 약품 정보를 인식하지 못했습니다.
            <br />
            더 선명한 이미지로 다시 분석해보세요.
          </div>
        )}

        {/* 면책 고지 */}
        <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 px-4 py-2.5 text-xs text-orange-500">
          ⚠️ 본 분석 결과는 참고용이며, 정확한 복약은 의사/약사와 상담하세요.
        </div>

        {/* 버튼 */}
        <div className="flex gap-3">
          <button
            onClick={() => router.push("/pill")}
            className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
          >
            새로 분석하기
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            className="rounded-xl border border-red-500/30 px-5 py-3 text-sm text-red-500 transition hover:bg-red-500/10"
          >
            삭제
          </button>
        </div>
      </div>

      {/* 삭제 확인 모달 */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6">
            <h3 className="mb-2 text-base font-bold text-foreground">
              분석 기록 삭제
            </h3>
            <p className="mb-6 text-sm text-muted-foreground">
              이 분석 기록을 삭제하면 복구할 수 없습니다. 삭제하시겠습니까?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(false)}
                className="flex-1 rounded-xl border border-border py-2.5 text-sm text-muted-foreground transition hover:text-foreground"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 rounded-xl bg-red-600 py-2.5 text-sm font-semibold text-white transition hover:bg-red-500 disabled:opacity-50"
              >
                {deleting ? "삭제 중..." : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
