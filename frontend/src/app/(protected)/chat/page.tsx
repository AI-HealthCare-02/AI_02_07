"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import apiClient from "@/lib/axios";
import ReactMarkdown from "react-markdown";

// ── 타입 ──────────────────────────────────────────────────────────────────────

interface ChatRoom {
  roomId: number;
  title: string;
  updatedAt: string;
}

interface ChatMessage {
  messageId: number;
  senderTypeCode: "USER" | "ASSISTANT";
  content: string;
  filterResult: "PASS" | "DOMAIN" | "EMERGENCY" | null;
  isBookmarked?: boolean;
  createdAt: string;
}

// ── 로딩 스피너 ───────────────────────────────────────────────────────────────

function Spinner({ size = 20 }: { size?: number }) {
  return (
    <span
      style={{ width: size, height: size }}
      className="inline-block animate-spin rounded-full border-2 border-white/20 border-t-teal-400"
    />
  );
}

// ── AI 타이핑 로딩 버블 ───────────────────────────────────────────────────────

function TypingBubble() {
  return (
    <div className="flex items-end gap-2">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-teal-500/30 bg-teal-500/10">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-white/8 bg-white/5 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-teal-400/70"
            style={{ animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }}
          />
        ))}
      </div>
    </div>
  );
}

// ── 메시지 버블 ───────────────────────────────────────────────────────────────

const markdownComponents = {
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-white">{children}</strong>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="leading-relaxed">{children}</li>,
  code: ({ children }: { children?: React.ReactNode }) => <code className="rounded bg-black/30 px-1 py-0.5 text-xs font-mono text-teal-200">{children}</code>,
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="mb-2 text-base font-bold">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="mb-1.5 text-sm font-bold">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
};

function BookmarkButton({ messageId, initialBookmarked = false }: { messageId: number; initialBookmarked?: boolean }) {
  const [bookmarked, setBookmarked] = useState(initialBookmarked);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (loading) return;
    setLoading(true);
    try {
      if (bookmarked) {
        await apiClient.delete(`/api/v1/chat/messages/${messageId}/bookmark`);
      } else {
        await apiClient.post(`/api/v1/chat/messages/${messageId}/bookmark`);
      }
      setBookmarked((prev) => !prev);
    } catch {
      // 무시
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={toggle}
      disabled={loading}
      className="mt-1.5 flex items-center gap-1 text-[11px] transition disabled:opacity-40"
      style={{ color: bookmarked ? "#14b8a6" : "rgba(255,255,255,0.25)" }}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill={bookmarked ? "#14b8a6" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
      {bookmarked ? "북마크됨" : "북마크"}
    </button>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.senderTypeCode === "USER";
  const isEmergency = msg.filterResult === "EMERGENCY";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-white/10 px-4 py-3 text-sm text-white/85">
          {msg.content}
        </div>
      </div>
    );
  }

  if (isEmergency) {
    return (
      <div className="flex items-end gap-2">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-red-500/40 bg-red-500/10">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <div className="max-w-[75%] rounded-2xl rounded-bl-sm border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-teal-500/30 bg-teal-500/10">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      </div>
      <div className="flex max-w-[75%] flex-col">
        <div
          className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-white"
          style={{ background: "linear-gradient(135deg, rgb(20,184,166), rgb(6,182,212))" }}
        >
          <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
        </div>
        <BookmarkButton messageId={msg.messageId} initialBookmarked={msg.isBookmarked ?? false} />
      </div>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────

export default function ChatPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [activeRoomId, setActiveRoomId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");

  const [loadingRooms, setLoadingRooms] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [aiTyping, setAiTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const activeRoomIdRef = useRef<number | null>(null);

  // ── 인증 확인 (layout에서 공통 처리) ──
  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  // ── body 스크롤 잠금 ──
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // ── 세션 목록 로드 ──
  const loadRooms = useCallback(async () => {
    try {
      const { data } = await apiClient.get("/api/v1/chat/sessions?size=50");
      const sorted: ChatRoom[] = (data.data.items ?? []).sort(
        (a: ChatRoom, b: ChatRoom) =>
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
      setRooms(sorted);
    } catch {
      // 무시
    } finally {
      setLoadingRooms(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) loadRooms();
  }, [isAuthenticated, loadRooms]);

  // ── 메시지 목록 로드 ──
  const loadMessages = useCallback(async (roomId: number) => {
    setLoadingMessages(true);
    try {
      const { data } = await apiClient.get(
        `/api/v1/chat/sessions/${roomId}/messages?size=200`
      );
      setMessages(data.data.messages ?? []);
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // ── 세션 선택 ──
  const selectRoom = useCallback(
    (roomId: number) => {
      if (activeRoomId === roomId) return;
      eventSourceRef.current?.close();
      activeRoomIdRef.current = roomId;
      setActiveRoomId(roomId);
      setAiTyping(false);
      setSidebarOpen(false);
      loadMessages(roomId);
    },
    [activeRoomId, loadMessages]
  );

  // ── 새 대화 ──
  const createRoom = async () => {
    try {
      const { data } = await apiClient.post("/api/v1/chat/sessions");
      const newRoom: ChatRoom = {
        roomId: data.data.roomId,
        title: data.data.title,
        updatedAt: data.data.createdAt,
      };
      setRooms((prev) => [newRoom, ...prev]);
      setActiveRoomId(newRoom.roomId);
      setMessages([]);
      setSidebarOpen(false);
    } catch {
      // 무시
    }
  };

  // ── 스크롤 하단 ──
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [messages, aiTyping]);

  // ── 메시지 전송 (SSE) ──
  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending || aiTyping) return;

    let roomId = activeRoomId;

    // 세션 없으면 자동 생성
    if (!roomId) {
      try {
        const { data } = await apiClient.post("/api/v1/chat/sessions");
        roomId = data.data.roomId;
        const newRoom: ChatRoom = {
          roomId: data.data.roomId,
          title: data.data.title,
          updatedAt: data.data.createdAt,
        };
        setRooms((prev) => [newRoom, ...prev]);
        setActiveRoomId(roomId);
        activeRoomIdRef.current = roomId;
      } catch {
        return;
      }
    }

    // 사용자 메시지 즉시 표시
    const tempUserMsg: ChatMessage = {
      messageId: Date.now(),
      senderTypeCode: "USER",
      content: text,
      filterResult: "PASS",
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setInput("");
    setSending(true);
    setAiTyping(true);

    const token = localStorage.getItem("access_token");
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    // SSE fetch 스트리밍
    try {
      const res = await fetch(`${BASE_URL}/api/v1/chat/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ sessionId: roomId, message: text }),
      });

      if (!res.ok || !res.body) throw new Error("SSE 연결 실패");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiContent = "";
      let aiMsgAdded = false;
      const streamRoomId = roomId; // 스트림 시작 시점의 방 ID 캡처

      const processLine = (line: string) => {
        // 방이 바뀌었으면 무시
        if (activeRoomIdRef.current !== streamRoomId) return;
        if (!line.startsWith("data:")) return;
        const raw = line.slice(5).trim();
        if (raw === "[DONE]") return;

        try {
          const parsed = JSON.parse(raw);

          // 토큰 스트리밍
          if (parsed.token !== undefined) {
            aiContent += parsed.token;
            setAiTyping(false);
            if (!aiMsgAdded) {
              aiMsgAdded = true;
              setMessages((prev) => [
                ...prev,
                {
                  messageId: Date.now() + 1,
                  senderTypeCode: "ASSISTANT",
                  content: aiContent,
                  filterResult: "PASS",
                  createdAt: new Date().toISOString(),
                },
              ]);
            } else {
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { ...next[next.length - 1], content: aiContent };
                return next;
              });
            }
          }

          // 필터 차단
          if (parsed.type === "DOMAIN" || parsed.type === "EMERGENCY") {
            setAiTyping(false);
            setMessages((prev) => [
              ...prev,
              {
                messageId: Date.now() + 1,
                senderTypeCode: "ASSISTANT",
                content: parsed.message,
                filterResult: parsed.type,
                createdAt: new Date().toISOString(),
              },
            ]);
          }
        } catch {
          // JSON 파싱 실패 무시
        }
      };

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) processLine(line.trim());
      }

      // 전송 완료 후 세션 목록 갱신 (제목 업데이트 반영)
      loadRooms();
    } catch {
      setAiTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          messageId: Date.now() + 1,
          senderTypeCode: "ASSISTANT",
          content: "⏳ 응답을 받지 못했습니다. 잠시 후 다시 시도해주세요.",
          filterResult: null,
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
      setAiTyping(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── 렌더 ──────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>

      <div className="flex h-[calc(100vh-64px)] bg-[#090a0f]">

        {/* ── 모바일 사이드바 오버레이 ── */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-20 bg-black/60 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* ── 사이드바 ── */}
        <aside
          className={`fixed left-0 top-16 z-30 flex h-[calc(100vh-64px)] w-72 flex-col border-r border-white/8 bg-[#0d1117] transition-transform duration-300 lg:static lg:translate-x-0 lg:z-auto ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {/* 새 대화 버튼 */}
          <div className="p-4">
            <button
              onClick={createRoom}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-teal-500/30 bg-teal-500/10 py-2.5 text-sm font-medium text-teal-300 transition hover:bg-teal-500/20"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              새 대화
            </button>
          </div>

          {/* 대화 목록 */}
          <div className="flex-1 overflow-y-auto px-2 pb-4">
            {loadingRooms ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : rooms.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-white/30">
                대화 내역이 없습니다
              </p>
            ) : (
              rooms.map((room) => (
                <button
                  key={room.roomId}
                  onClick={() => selectRoom(room.roomId)}
                  className={`mb-1 w-full rounded-lg px-3 py-2.5 text-left transition ${
                    activeRoomId === room.roomId
                      ? "bg-teal-500/15 text-teal-300"
                      : "text-white/50 hover:bg-white/5 hover:text-white/80"
                  }`}
                >
                  <p className="truncate text-sm font-medium">{room.title}</p>
                  <p className="mt-0.5 text-[10px] text-white/25">
                    {new Date(room.updatedAt).toLocaleDateString("ko-KR", {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* ── 메인 채팅 영역 ── */}
        <div className="flex flex-1 flex-col overflow-hidden">

          {/* 모바일 상단 바 */}
          <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3 lg:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white/70"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <span className="text-sm font-medium text-white/60">
              {activeRoomId
                ? rooms.find((r) => r.roomId === activeRoomId)?.title ?? "AI 상담"
                : "AI 상담"}
            </span>
          </div>

          {/* 메시지 영역 */}
          <div ref={messagesContainerRef} className="flex-1 overflow-y-auto px-4 py-6 pb-2">
            {!activeRoomId ? (
              /* 빈 상태 */
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-teal-500/20 bg-teal-500/5">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    <path d="M8 10h8M8 14h5" />
                  </svg>
                </div>
                <div>
                  <p className="text-base font-semibold text-white/70">AI 건강 상담을 시작하세요</p>
                  <p className="mt-1 text-sm text-white/30">왼쪽에서 새 대화를 시작하거나 기존 대화를 선택하세요</p>
                </div>
              </div>
            ) : loadingMessages ? (
              <div className="flex h-full items-center justify-center">
                <Spinner size={28} />
              </div>
            ) : (
              <div className="mx-auto max-w-2xl space-y-4">
                {messages.map((msg) => (
                  <MessageBubble key={msg.messageId} msg={msg} />
                ))}
                {aiTyping && <TypingBubble />}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* 면책 고지 */}
          <div className="border-t border-orange-500/20 bg-orange-500/5 px-4 py-2 text-center">
            <p className="text-xs font-medium text-orange-400/80">
              ⚠️ 의료 진단을 대신하지 않습니다. 응급상황 시 119에 연락하세요.
            </p>
          </div>

          {/* 입력창 */}
          <div className="border-t border-white/8 bg-[#0d1117] px-4 py-3 pb-safe">
            <div className="mx-auto flex max-w-2xl items-end gap-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="메시지를 입력하세요"
                rows={1}
                disabled={sending || aiTyping}
                className="flex-1 resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/85 placeholder:text-white/25 focus:border-teal-500/40 focus:outline-none disabled:opacity-50"
                style={{ maxHeight: 120, overflowY: "auto" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 120) + "px";
                }}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || sending || aiTyping}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition hover:bg-teal-500 disabled:opacity-40"
              >
                {sending || aiTyping ? (
                  <Spinner size={16} />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
