"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi, AdminUserItem } from "@/lib/admin-api";

const STATUS_OPTIONS = [
  { value: "ALL", label: "전체" },
  { value: "ACTIVE", label: "활성" },
  { value: "SUSPENDED", label: "정지" },
];

export default function AdminUsersPage() {
  const [items, setItems] = useState<AdminUserItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [inputKeyword, setInputKeyword] = useState("");
  const [status, setStatus] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const SIZE = 20;
  const totalPages = Math.ceil(totalCount / SIZE);

  const fetchUsers = useCallback(() => {
    setLoading(true);
    setError(null);
    adminApi
      .getUsers({ page, size: SIZE, keyword: keyword || undefined, status })
      .then(({ data }) => {
        setItems(data.data.items);
        setTotalCount(data.data.totalCount);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, keyword, status]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setKeyword(inputKeyword);
  };

  const handleSuspend = async (userId: number, isSuspended: boolean) => {
    setActionLoading(userId);
    try {
      if (isSuspended) await adminApi.unsuspendUser(userId);
      else await adminApi.suspendUser(userId);
      fetchUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">사용자 관리</h1>
        <p className="mt-0.5 text-sm text-slate-400">전체 {totalCount.toLocaleString()}명</p>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* 검색 / 필터 */}
      <div className="flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            value={inputKeyword}
            onChange={(e) => setInputKeyword(e.target.value)}
            placeholder="이름 또는 이메일 검색"
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30"
          />
          <button
            type="submit"
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-500"
          >
            검색
          </button>
        </form>
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { setStatus(opt.value); setPage(1); }}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                status === opt.value ? "bg-slate-600 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 테이블 */}
      <div className="overflow-hidden rounded-2xl border border-white/10">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">이름</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">이메일</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 hidden md:table-cell">가입 경로</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 hidden lg:table-cell">가입일</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">상태</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-slate-400">관리</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-white/5">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 animate-pulse rounded bg-white/5" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-500">
                    사용자가 없습니다.
                  </td>
                </tr>
              ) : (
                items.map((user) => (
                  <tr key={user.userId} className="border-b border-white/5 transition hover:bg-white/5">
                    <td className="px-4 py-3 font-medium text-slate-200">{user.name}</td>
                    <td className="px-4 py-3 text-slate-400">{user.email}</td>
                    <td className="px-4 py-3 text-slate-400 hidden md:table-cell">{user.providerName}</td>
                    <td className="px-4 py-3 text-slate-500 hidden lg:table-cell">
                      {new Date(user.createdAt).toLocaleDateString("ko-KR")}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          user.isSuspended
                            ? "bg-red-500/15 text-red-400"
                            : "bg-teal-500/15 text-teal-400"
                        }`}
                      >
                        {user.isSuspended ? "정지" : "활성"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleSuspend(user.userId, user.isSuspended)}
                        disabled={actionLoading === user.userId}
                        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                          user.isSuspended
                            ? "bg-teal-500/15 text-teal-400 hover:bg-teal-500/25"
                            : "bg-red-500/15 text-red-400 hover:bg-red-500/25"
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        {actionLoading === user.userId ? (
                          <span className="inline-block h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                        ) : user.isSuspended ? (
                          "정지 해제"
                        ) : (
                          "정지"
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
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
          <span className="text-xs text-slate-400">
            {page} / {totalPages}
          </span>
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
