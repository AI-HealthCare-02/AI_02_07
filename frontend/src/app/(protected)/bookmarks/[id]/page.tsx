"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

interface BookmarkDetail {
  bookmarkId: number;
  questionContent: string;
  answerContent: string;
  createdAt: string;
}

export default function BookmarkDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [item, setItem] = useState<BookmarkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get(`/api/v1/chat/bookmarks/${id}`)
      .then(({ data }) => setItem(data.data))
      .catch(() => setError("북마크를 불러오는 데 실패했습니다."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-red-500">{error ?? "북마크를 찾을 수 없습니다."}</p>
        <button onClick={() => router.back()} className="text-sm text-teal-500 underline">
          돌아가기
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">🔖 북마크 상세</h1>
        <button
          onClick={() => router.back()}
          className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
        >
          ← 목록
        </button>
      </div>

      {/* 날짜 */}
      <p className="mb-5 text-xs text-muted-foreground">
        {new Date(item.createdAt).toLocaleDateString("ko-KR", {
          year: "numeric", month: "long", day: "numeric",
          hour: "2-digit", minute: "2-digit",
        })}
      </p>

      {/* 질문 */}
      <div className="mb-4 rounded-2xl border border-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2">
          <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground">Q</span>
          <span className="text-xs font-semibold text-muted-foreground">질문</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {item.questionContent}
        </p>
      </div>

      {/* 답변 */}
      <div className="rounded-2xl border border-teal-500/20 bg-teal-500/5 p-5">
        {/* 상단 글로우 라인 */}
        <div
          className="absolute left-0 right-0 top-0 h-px rounded-t-2xl"
          style={{ background: "linear-gradient(90deg, transparent, rgba(20,184,166,0.4), transparent)" }}
        />
        <div className="mb-3 flex items-center gap-2">
          <span className="rounded-full bg-teal-500/20 px-2.5 py-1 text-xs font-bold text-teal-400">A</span>
          <span className="text-xs font-semibold text-teal-400">AI 답변</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {item.answerContent}
        </p>
      </div>

      {/* 면책 */}
      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        ⚠️ 본 답변은 참고용이며, 정확한 진단은 의사 또는 약사와 상담하세요.
      </p>
    </div>
  );
}
