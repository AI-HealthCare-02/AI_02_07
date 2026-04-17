"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

interface ResultItem {
  doc_result_id: number;
  document_type: string;
  overall_confidence: number | null;
  raw_summary: string | null;
  created_at: string;
}

interface Pagination {
  page: number;
  total_pages: number;
  total_count: number;
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted-foreground">신뢰도 -</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.9 ? "text-teal-500" : value >= 0.7 ? "text-yellow-500" : "text-red-500";
  return <span className={`text-xs font-medium ${color}`}>신뢰도 {pct}%</span>;
}

export default function ResultsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ResultItem[]>([]);
  const [pagination, setPagination] = useState<Pagination>({ page: 1, total_pages: 1, total_count: 0 });
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async (page: number) => {
    setLoading(true);
    try {
      const { data } = await apiClient.get(`/api/v1/medical-doc/results?page=${page}&page_size=10`);
      setItems(data.data.items ?? []);
      setPagination({
        page: data.data.page ?? page,
        total_pages: data.data.total_pages ?? 1,
        total_count: data.data.total_count ?? 0,
      });
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(1); }, [load]);

  const handleDelete = async () => {
    if (deleteTarget === null) return;
    setDeleting(true);
    try {
      await apiClient.delete(`/api/v1/medical-doc/results/${deleteTarget}`);
      setItems((prev) => prev.filter((i) => i.doc_result_id !== deleteTarget));
      setDeleteTarget(null);
    } catch {
      // 무시
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">📂 내 분석 기록</h1>
          {!loading && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              총 {pagination.total_count}건 · {pagination.page} / {pagination.total_pages} 페이지
            </p>
          )}
        </div>
        <button
          onClick={() => router.push("/docs")}
          className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-500 transition hover:bg-teal-500/20"
        >
          + 새 분석
        </button>
      </div>

      {/* 목록 */}
      {loading ? (
        <div className="flex justify-center py-20">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
          <div className="text-5xl">📄</div>
          <p className="text-sm text-muted-foreground">분석 기록이 없습니다.</p>
          <button
            onClick={() => router.push("/docs")}
            className="rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-teal-500"
          >
            첫 문서 분석하기
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.doc_result_id} className="rounded-xl border border-border bg-card p-5">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <span className="text-sm font-semibold text-foreground">{item.document_type}</span>
                  <div className="mt-0.5 flex items-center gap-2">
                    <ConfidenceBadge value={item.overall_confidence} />
                    <span className="text-xs text-muted-foreground">
                      {new Date(item.created_at).toLocaleDateString("ko-KR", {
                        year: "numeric", month: "short", day: "numeric",
                      })}
                    </span>
                  </div>
                </div>
              </div>
              {item.raw_summary && (
                <p className="mb-3 line-clamp-2 text-xs text-muted-foreground">{item.raw_summary}</p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => router.push(`/docs/results/${item.doc_result_id}`)}
                  className="flex-1 rounded-lg border border-border py-2 text-xs font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
                >
                  보기
                </button>
                <button
                  onClick={() => setDeleteTarget(item.doc_result_id)}
                  className="flex-1 rounded-lg border border-red-500/20 py-2 text-xs font-medium text-red-500 transition hover:bg-red-500/10"
                >
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {pagination.total_pages > 1 && (
        <div className="mt-6 flex justify-center gap-2">
          {Array.from({ length: pagination.total_pages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => load(p)}
              className={`h-8 w-8 rounded-lg text-sm transition ${
                p === pagination.page
                  ? "bg-teal-600 text-white"
                  : "border border-border text-muted-foreground hover:border-teal-500/40 hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {deleteTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
            <h2 className="mb-3 text-base font-semibold text-foreground">분석 기록 삭제</h2>
            <p className="mb-6 text-sm text-muted-foreground">이 분석 기록을 삭제하시겠습니까? 삭제 후 복구할 수 없습니다.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground transition hover:text-foreground disabled:opacity-40"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 rounded-lg bg-red-600 py-2.5 text-sm font-medium text-white transition hover:bg-red-500 disabled:opacity-50"
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
