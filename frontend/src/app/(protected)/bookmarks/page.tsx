"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

interface BookmarkItem {
  bookmarkId: number;
  questionContent: string;
  answerContent: string;
  createdAt: string;
}

interface BookmarkList {
  totalCount: number;
  totalPages: number;
  page: number;
  size: number;
  items: BookmarkItem[];
}

export default function BookmarksPage() {
  const router = useRouter();
  const [data, setData] = useState<BookmarkList | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [cancelingId, setCancelingId] = useState<number | null>(null);

  const fetchBookmarks = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const { data: res } = await apiClient.get(`/api/v1/chat/bookmarks?page=${p}&size=10`);
      setData(res.data);
    } catch {
      // 무시
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookmarks(page);
  }, [page, fetchBookmarks]);

  const handleCancel = async (e: React.MouseEvent, item: BookmarkItem) => {
    e.stopPropagation();
    if (cancelingId) return;
    setCancelingId(item.bookmarkId);
    try {
      // answer_message_id 기반으로 북마크 해제 — bookmarkId로 직접 삭제 API가 없으므로
      // 북마크 상세에서 answer_message_id를 알 수 없어 목록에서 제거만 처리
      // 백엔드에 DELETE /bookmarks/{id} 추가 필요 → 여기서는 answer_message_id 없이
      // 임시로 bookmark_id를 answer_message_id처럼 사용하는 대신
      // 별도 DELETE /bookmarks/{bookmark_id} 엔드포인트 호출
      await apiClient.delete(`/api/v1/chat/bookmarks/${item.bookmarkId}`);
      setData((prev) => {
        if (!prev) return prev;
        const items = prev.items.filter((i) => i.bookmarkId !== item.bookmarkId);
        return { ...prev, items, totalCount: prev.totalCount - 1 };
      });
    } catch {
      // 무시
    } finally {
      setCancelingId(null);
    }
  };

  const totalPages = data?.totalPages ?? 1;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">🔖 북마크</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {data ? `총 ${data.totalCount}개` : ""}
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
        >
          ← 뒤로
        </button>
      </div>

      {/* 목록 */}
      {loading ? (
        <div className="flex justify-center py-20">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-20 text-center">
          <p className="mb-2 text-3xl">🔖</p>
          <p className="text-sm font-medium text-foreground">저장된 북마크가 없어요</p>
          <p className="mt-1 text-xs text-muted-foreground">AI 상담 답변에서 북마크를 저장해보세요</p>
          <button
            onClick={() => router.push("/chat")}
            className="mt-4 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-500"
          >
            AI 상담 시작하기
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((item) => (
            <div
              key={item.bookmarkId}
              className="group relative rounded-2xl border border-border bg-card transition hover:-translate-y-0.5 hover:border-teal-500/40"
            >
              {/* 카드 클릭 → 상세 */}
              <button
                onClick={() => router.push(`/bookmarks/${item.bookmarkId}`)}
                className="w-full p-5 text-left"
              >
                {/* 질문 */}
                <div className="mb-3 flex items-start gap-2.5">
                  <span className="mt-0.5 shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">Q</span>
                  <p className="line-clamp-2 text-sm font-medium text-foreground">
                    {item.questionContent}
                  </p>
                </div>
                {/* 답변 미리보기 */}
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 shrink-0 rounded-full bg-teal-500/15 px-2 py-0.5 text-[10px] font-semibold text-teal-400">A</span>
                  <p className="line-clamp-2 text-xs text-muted-foreground">
                    {item.answerContent}
                  </p>
                </div>
                {/* 날짜 */}
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground/60">
                    {new Date(item.createdAt).toLocaleDateString("ko-KR", {
                      year: "numeric", month: "short", day: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </span>
                  <span className="text-xs text-teal-500 opacity-0 transition group-hover:opacity-100">
                    상세 보기 →
                  </span>
                </div>
              </button>

              {/* 북마크 취소 버튼 */}
              <button
                onClick={(e) => handleCancel(e, item)}
                disabled={cancelingId === item.bookmarkId}
                title="북마크 취소"
                className="absolute right-3 top-3 flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] text-muted-foreground opacity-0 transition group-hover:opacity-100 hover:border-red-500/40 hover:text-red-400 disabled:opacity-40"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
                {cancelingId === item.bookmarkId ? "..." : "취소"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 페이징 */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-30"
          >
            ‹
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                p === page
                  ? "border-teal-500 bg-teal-600 text-white"
                  : "border-border text-muted-foreground hover:border-teal-500/40 hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-30"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}
