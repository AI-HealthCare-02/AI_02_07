"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi, ErrorLogItem } from "@/lib/admin-api";

export default function AdminErrorsPage() {
  const [items, setItems] = useState<ErrorLogItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [errorTypes, setErrorTypes] = useState<string[]>([]);
  const [selectedType, setSelectedType] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const SIZE = 20;
  const totalPages = Math.ceil(totalCount / SIZE);

  // 오류 타입 목록 로드
  useEffect(() => {
    adminApi
      .getErrorTypes()
      .then(({ data }) => setErrorTypes(data.data))
      .catch(() => {});
  }, []);

  const fetchErrors = useCallback(() => {
    setLoading(true);
    setError(null);
    adminApi
      .getErrors({
        page,
        size: SIZE,
        error_type: selectedType || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then(({ data }) => {
        setItems(data.data.items);
        setTotalCount(data.data.totalCount);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, selectedType, startDate, endDate]);

  useEffect(() => { fetchErrors(); }, [fetchErrors]);

  const handleDelete = async (logId: number) => {
    if (!confirm("이 오류 로그를 삭제하시겠습니까?")) return;
    setDeletingId(logId);
    try {
      await adminApi.deleteError(logId);
      setItems((prev) => prev.filter((i) => i.logId !== logId));
      setTotalCount((prev) => prev - 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setDeletingId(null);
    }
  };

  const handleFilterReset = () => {
    setSelectedType("");
    setStartDate("");
    setEndDate("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">오류 로그</h1>
        <p className="mt-0.5 text-sm text-slate-400">전체 {totalCount.toLocaleString()}건</p>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* 필터 */}
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-white/10 bg-white/5 p-4">
        <div>
          <label className="mb-1 block text-xs text-slate-400">오류 타입</label>
          <select
            value={selectedType}
            onChange={(e) => { setSelectedType(e.target.value); setPage(1); }}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-teal-500/50"
          >
            <option value="">전체</option>
            {errorTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">시작일</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-teal-500/50 [color-scheme:dark]"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">종료일</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-teal-500/50 [color-scheme:dark]"
          />
        </div>
        {(selectedType || startDate || endDate) && (
          <button
            onClick={handleFilterReset}
            className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-400 transition hover:bg-white/5 hover:text-slate-200"
          >
            초기화
          </button>
        )}
      </div>

      {/* 목록 */}
      <div className="space-y-2">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-white/5" />
          ))
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 py-16 text-center text-sm text-slate-500">
            오류 로그가 없습니다.
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.logId}
              className="rounded-xl border border-white/10 bg-white/5 overflow-hidden"
            >
              {/* 헤더 행 */}
              <div className="flex items-center gap-3 px-4 py-3">
                {/* 오류 타입 배지 */}
                <span className="shrink-0 rounded-md bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-400">
                  {item.errorType ?? "UNKNOWN"}
                </span>

                {/* 메시지 */}
                <p className="flex-1 truncate text-sm text-slate-300">{item.errorMessage}</p>

                {/* 메타 */}
                <div className="hidden shrink-0 items-center gap-3 sm:flex">
                  {item.userId && (
                    <span className="text-xs text-slate-500">uid:{item.userId}</span>
                  )}
                  <span className="text-xs text-slate-500">
                    {new Date(item.createdAt).toLocaleString("ko-KR")}
                  </span>
                </div>

                {/* 액션 버튼 */}
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => setExpandedId(expandedId === item.logId ? null : item.logId)}
                    className="rounded-lg p-1.5 text-slate-500 transition hover:bg-white/10 hover:text-slate-300"
                    title="상세 보기"
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className={`transition-transform ${expandedId === item.logId ? "rotate-180" : ""}`}
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </button>
                  <button
                    onClick={() => handleDelete(item.logId)}
                    disabled={deletingId === item.logId}
                    className="rounded-lg p-1.5 text-slate-500 transition hover:bg-red-500/10 hover:text-red-400 disabled:opacity-40"
                    title="삭제"
                  >
                    {deletingId === item.logId ? (
                      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border border-current border-t-transparent" />
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <path d="M10 11v6M14 11v6" />
                        <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* 상세 펼침 */}
              {expandedId === item.logId && (
                <div className="border-t border-white/10 bg-slate-900/50 px-4 py-4 space-y-3">
                  {item.requestUrl && (
                    <div>
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">Request URL</p>
                      <p className="text-xs text-slate-300 break-all">{item.requestUrl}</p>
                    </div>
                  )}
                  <div className="sm:hidden space-y-1">
                    {item.userId && <p className="text-xs text-slate-500">User ID: {item.userId}</p>}
                    <p className="text-xs text-slate-500">{new Date(item.createdAt).toLocaleString("ko-KR")}</p>
                  </div>
                  {item.stackTrace && (
                    <div>
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">Stack Trace</p>
                      <pre className="overflow-x-auto rounded-lg bg-black/40 p-3 text-[11px] leading-relaxed text-slate-400 scrollbar-thin">
                        {item.stackTrace}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 transition hover:bg-white/5 disabled:opacity-40"
          >
            이전
          </button>
          <span className="text-xs text-slate-400">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 transition hover:bg-white/5 disabled:opacity-40"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
