"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi, ChatStatItem, ChatStatList } from "@/lib/admin-api";

const FILTER_OPTIONS = ["", "PASS", "DOMAIN", "EMERGENCY", "OTHER", "GREETING"];

function truncate(text: string | null, len = 60) {
  if (!text) return "-";
  return text.length > len ? text.slice(0, len) + "…" : text;
}

function filterBadge(v: string | null) {
  if (!v) return <span className="text-slate-500">-</span>;
  const map: Record<string, string> = {
    PASS: "bg-teal-500/15 text-teal-400",
    DOMAIN: "bg-yellow-500/15 text-yellow-400",
    EMERGENCY: "bg-red-500/15 text-red-400",
    OTHER: "bg-slate-500/15 text-slate-400",
    GREETING: "bg-blue-500/15 text-blue-400",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${map[v] ?? "bg-slate-500/15 text-slate-400"}`}>
      {v}
    </span>
  );
}

export default function ChatStatsPage() {
  const [data, setData] = useState<ChatStatList | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [page, setPage] = useState(1);
  const SIZE = 50;

  // 필터
  const [roomId, setRoomId] = useState("");
  const [modelName, setModelName] = useState("");
  const [filterResult, setFilterResult] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const fetchData = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page: p, size: SIZE };
        if (roomId) params.room_id = Number(roomId);
        if (modelName) params.model_name = modelName;
        if (filterResult) params.filter_result = filterResult;
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;

        const { data: res } = await adminApi.getChatStats(params as Parameters<typeof adminApi.getChatStats>[0]);
        setData(res.data);
      } finally {
        setLoading(false);
      }
    },
    [roomId, modelName, filterResult, startDate, endDate]
  );

  useEffect(() => {
    fetchData(page);
  }, [fetchData, page]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchData(1);
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const params: Record<string, string | number> = {};
      if (roomId) params.room_id = Number(roomId);
      if (modelName) params.model_name = modelName;
      if (filterResult) params.filter_result = filterResult;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const { data: blob } = await adminApi.downloadChatStatsCsv(params as Parameters<typeof adminApi.downloadChatStatsCsv>[0]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `chat_stats_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.totalCount / SIZE) : 1;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">채팅 통계</h1>
          <p className="mt-0.5 text-sm text-slate-400">모델별 AI 상담 토큰·비용·응답시간 통계</p>
        </div>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-2 rounded-lg border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-400 transition hover:bg-teal-500/20 disabled:opacity-50"
        >
          {downloading ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border border-teal-400 border-t-transparent" />
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          )}
          CSV 다운로드
        </button>
      </div>

      {/* 필터 */}
      <form
        onSubmit={handleSearch}
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-white/10 bg-white/5 p-4"
      >
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-slate-400">채팅방 ID</label>
          <input
            type="number"
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
            placeholder="전체"
            className="w-28 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-slate-500 outline-none focus:border-teal-500/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-slate-400">모델명</label>
          <input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="전체"
            className="w-36 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-slate-500 outline-none focus:border-teal-500/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-slate-400">필터 결과</label>
          <select
            value={filterResult}
            onChange={(e) => setFilterResult(e.target.value)}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-sm text-white outline-none focus:border-teal-500/50"
          >
            {FILTER_OPTIONS.map((o) => (
              <option key={o} value={o}>{o || "전체"}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-slate-400">시작일</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-sm text-white outline-none focus:border-teal-500/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-slate-400">종료일</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-sm text-white outline-none focus:border-teal-500/50"
          />
        </div>
        <button
          type="submit"
          className="rounded-lg bg-teal-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-teal-500"
        >
          조회
        </button>
      </form>

      {/* 테이블 */}
      <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-[11px] font-medium text-slate-400">
                  <th className="px-4 py-3 whitespace-nowrap">채팅방</th>
                  <th className="px-4 py-3 whitespace-nowrap">모델</th>
                  <th className="px-4 py-3 whitespace-nowrap">입력</th>
                  <th className="px-4 py-3 whitespace-nowrap">출력</th>
                  <th className="px-4 py-3 whitespace-nowrap text-right">입력 토큰</th>
                  <th className="px-4 py-3 whitespace-nowrap text-right">출력 토큰</th>
                  <th className="px-4 py-3 whitespace-nowrap text-right">합계</th>
                  <th className="px-4 py-3 whitespace-nowrap text-right">비용(USD)</th>
                  <th className="px-4 py-3 whitespace-nowrap text-right">응답(ms)</th>
                  <th className="px-4 py-3 whitespace-nowrap">필터</th>
                  <th className="px-4 py-3 whitespace-nowrap">일시</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.length === 0 && (
                  <tr>
                    <td colSpan={11} className="py-12 text-center text-sm text-slate-500">
                      데이터가 없습니다.
                    </td>
                  </tr>
                )}
                {data?.items.map((row: ChatStatItem) => (
                  <tr
                    key={row.message_id}
                    className="border-b border-white/5 transition hover:bg-white/5"
                  >
                    <td className="px-4 py-3 text-slate-300">{row.room_id}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-teal-400 text-xs">
                      {row.model_name ?? "-"}
                    </td>
                    <td className="px-4 py-3 max-w-[180px] text-slate-300 text-xs">
                      {truncate(row.input_text)}
                    </td>
                    <td className="px-4 py-3 max-w-[180px] text-slate-300 text-xs">
                      {truncate(row.output_text)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {row.prompt_tokens?.toLocaleString() ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {row.completion_tokens?.toLocaleString() ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-white">
                      {row.total_tokens?.toLocaleString() ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right text-yellow-400 text-xs">
                      {row.cost_usd != null ? `$${row.cost_usd.toFixed(6)}` : "-"}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {row.latency_ms?.toLocaleString() ?? "-"}
                    </td>
                    <td className="px-4 py-3">{filterBadge(row.filter_result)}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
                      {row.created_at ? new Date(row.created_at).toLocaleString("ko-KR") : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 페이지네이션 */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            총 {data?.totalCount.toLocaleString()}건
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-slate-400 transition hover:bg-white/5 disabled:opacity-30"
            >
              이전
            </button>
            <span className="text-slate-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-slate-400 transition hover:bg-white/5 disabled:opacity-30"
            >
              다음
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
