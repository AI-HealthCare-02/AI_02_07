"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────────────────
type Tab = "analyze" | "list";
type Step = "upload" | "analyzing" | "done" | "failed";

interface PillSummary {
  analysis_id: number;
  product_name: string | null;
  efficacy: string | null;
  created_at: string;
}

interface ImageSlot {
  file: File;
  preview: string;
  label: "앞면" | "뒷면";
}

// ── 토스트 ─────────────────────────────────────────────────
function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-3 text-sm text-red-500 shadow-lg lg:bottom-6">
      {message}
      <button onClick={onClose} className="ml-3 opacity-60 hover:opacity-100">
        ✕
      </button>
    </div>
  );
}

// ── 이미지 업로드 슬롯 ─────────────────────────────────────
function ImageSlotCard({
  slot,
  label,
  onSelect,
  onRemove,
}: {
  slot: ImageSlot | null;
  label: "앞면" | "뒷면";
  onSelect: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-semibold text-muted-foreground">
        💊 알약 {label}
      </p>
      {slot ? (
        <div className="relative overflow-hidden rounded-xl border border-teal-500/40 bg-card">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={slot.preview}
            alt={`알약 ${label}`}
            className="h-44 w-full object-cover"
          />
          <button
            onClick={onRemove}
            className="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white hover:bg-red-600"
          >
            ✕
          </button>
          <p className="truncate px-3 py-2 text-xs text-muted-foreground">
            {slot.file.name}
          </p>
        </div>
      ) : (
        <button
          onClick={onSelect}
          className="flex h-44 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-card text-muted-foreground transition hover:border-teal-500/50 hover:bg-teal-500/5"
        >
          <span className="text-3xl">📷</span>
          <span className="text-xs">클릭하여 선택</span>
          <span className="text-xs opacity-60">JPG · PNG · WEBP</span>
        </button>
      )}
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────
export default function PillPage() {
  const router = useRouter();
  const frontRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<Tab>("analyze");
  const [step, setStep] = useState<Step>("upload");
  const [front, setFront] = useState<ImageSlot | null>(null);
  const [back, setBack] = useState<ImageSlot | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [failReason, setFailReason] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 목록
  const [list, setList] = useState<PillSummary[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [listLoading, setListLoading] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const makeSlot = (file: File, label: "앞면" | "뒷면"): ImageSlot => ({
    file,
    label,
    preview: URL.createObjectURL(file),
  });

  const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/heic"];

  const handleFileSelect = (
    e: React.ChangeEvent<HTMLInputElement>,
    label: "앞면" | "뒷면"
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED.includes(file.type)) {
      showToast("JPG, PNG, WEBP, HEIC 파일만 업로드 가능합니다.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast("이미지 크기가 5MB를 초과합니다.");
      return;
    }
    if (label === "앞면") setFront(makeSlot(file, "앞면"));
    else setBack(makeSlot(file, "뒷면"));
    e.target.value = "";
  };

  // ── 분석 시작 ──
  const startAnalysis = async () => {
    if (!front || !back) return;
    setStep("analyzing");
    setElapsedSec(0);
    timerRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);

    const formData = new FormData();
    formData.append("front_image", front.file);
    formData.append("back_image", back.file);

    try {
      const { data } = await apiClient.post(
        "/api/v1/pill-analysis/analyze",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setAnalysisId(data.data?.analysis_id ?? null);
      setStep("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      setFailReason(msg);
      setStep("failed");
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const resetAnalyze = () => {
    setStep("upload");
    setFront(null);
    setBack(null);
    setAnalysisId(null);
    setFailReason(null);
    setElapsedSec(0);
  };

  // ── 목록 조회 ──
  const fetchList = useCallback(
    async (p: number, q: string) => {
      setListLoading(true);
      try {
        const params = new URLSearchParams({
          page: String(p),
          size: "10",
          ...(q ? { search: q } : {}),
        });
        const { data } = await apiClient.get(
          `/api/v1/pill-analysis?${params}`
        );
        setList(data.data ?? []);
        setTotalPages(data.pagination?.total_pages ?? 1);
      } catch {
        showToast("목록을 불러오지 못했습니다.");
      } finally {
        setListLoading(false);
      }
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const handleTabList = () => {
    setTab("list");
    fetchList(1, "");
    setPage(1);
    setSearch("");
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchList(1, search);
  };

  const handlePage = (p: number) => {
    setPage(p);
    fetchList(p, search);
  };

  // ── 분석 진행 단계 ──
  const STEPS_LABEL = [
    { label: "이미지 전처리", doneAt: 3 },
    { label: "이미지 업로드", doneAt: 8 },
    { label: "AI 멀티모달 분석", doneAt: 45 },
    { label: "결과 저장", doneAt: 55 },
  ];

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 lg:pb-8">
      {/* 면책 고지 */}
      <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/5 px-4 py-2.5 text-xs text-orange-500">
        ⚠️ 본 서비스는 참고용이며, 정확한 복약은 의사/약사와 상담하세요.
      </div>

      {/* 탭 */}
      <div className="mb-6 flex gap-1 rounded-xl border border-border bg-card p-1">
        {(["analyze", "list"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => (t === "list" ? handleTabList() : setTab("analyze"))}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition ${
              tab === t
                ? "bg-teal-600 text-white"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "analyze" ? "💊 알약 분석" : "📋 분석 기록"}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════
          탭 1: 알약 분석
      ══════════════════════════════════════ */}
      {tab === "analyze" && (
        <>
          {/* ── 업로드 ── */}
          {step === "upload" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-foreground">
                  알약 이미지 분석
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  알약 앞면과 뒷면 이미지를 각각 업로드하면 AI가 약품 정보를
                  분석합니다.
                </p>
              </div>

              {/* 이미지 슬롯 2개 */}
              <div className="grid grid-cols-2 gap-4">
                <ImageSlotCard
                  slot={front}
                  label="앞면"
                  onSelect={() => frontRef.current?.click()}
                  onRemove={() => setFront(null)}
                />
                <ImageSlotCard
                  slot={back}
                  label="뒷면"
                  onSelect={() => backRef.current?.click()}
                  onRemove={() => setBack(null)}
                />
              </div>

              <input
                ref={frontRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.heic"
                className="hidden"
                onChange={(e) => handleFileSelect(e, "앞면")}
              />
              <input
                ref={backRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.heic"
                className="hidden"
                onChange={(e) => handleFileSelect(e, "뒷면")}
              />

              <p className="text-xs text-muted-foreground">
                💡 알약의 각인 문자, 색상, 모양이 잘 보이도록 촬영해주세요.
              </p>

              <button
                onClick={startAnalysis}
                disabled={!front || !back}
                className="w-full rounded-xl bg-teal-600 py-3.5 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                분석 시작하기 →
              </button>
            </div>
          )}

          {/* ── 분석 중 ── */}
          {step === "analyzing" && (
            <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 text-center">
              <div>
                <div className="mb-4 animate-pulse text-5xl">🔄</div>
                <h2 className="text-xl font-bold text-foreground">
                  AI 분석 중...
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  평균 소요 시간: 30~60초
                </p>
                {elapsedSec >= 50 && (
                  <p className="mt-2 text-xs text-yellow-500">
                    시간이 걸리고 있어요, 잠시만 기다려주세요.
                  </p>
                )}
              </div>

              {/* 진행 바 */}
              <div className="w-full max-w-sm">
                <div className="mb-2 flex justify-between text-xs text-muted-foreground">
                  <span>진행 중</span>
                  <span>
                    {Math.min(Math.round((elapsedSec / 55) * 100), 95)}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-teal-500 transition-all duration-1000"
                    style={{
                      width: `${Math.min(Math.round((elapsedSec / 55) * 100), 95)}%`,
                    }}
                  />
                </div>
              </div>

              {/* 단계 */}
              <div className="w-full max-w-sm space-y-3 text-left">
                {STEPS_LABEL.map((s) => {
                  const done = elapsedSec >= s.doneAt;
                  const active = !done && elapsedSec >= s.doneAt - 5;
                  return (
                    <div key={s.label} className="flex items-center gap-3 text-sm">
                      <span className="text-base">
                        {done ? "✅" : active ? "🔄" : "⏳"}
                      </span>
                      <span
                        className={
                          done ? "text-foreground" : "text-muted-foreground"
                        }
                      >
                        {s.label}
                        {active ? " 중..." : done ? " 완료" : " 대기"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── 분석 완료 ── */}
          {step === "done" && (
            <div className="space-y-5">
              <div className="rounded-xl border border-teal-500/30 bg-teal-500/5 p-6 text-center">
                <div className="mb-3 text-5xl">✅</div>
                <h2 className="text-xl font-bold text-foreground">
                  분석이 완료되었습니다!
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  분석된 약품 정보를 확인하세요.
                </p>
              </div>

              {/* 업로드한 이미지 미리보기 */}
              <div className="rounded-xl border border-border bg-card p-5">
                <p className="mb-3 text-sm font-semibold text-teal-500">
                  📷 업로드한 이미지
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {[front, back].map((slot) =>
                    slot ? (
                      <div key={slot.label} className="space-y-1">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={slot.preview}
                          alt={`알약 ${slot.label}`}
                          className="h-36 w-full rounded-lg object-cover"
                        />
                        <p className="text-center text-xs text-muted-foreground">
                          {slot.label}
                        </p>
                      </div>
                    ) : null
                  )}
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={resetAnalyze}
                  className="flex-1 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground"
                >
                  다시 분석
                </button>
                {analysisId && (
                  <button
                    onClick={() => router.push(`/pill/${analysisId}`)}
                    className="flex-1 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition hover:bg-teal-500"
                  >
                    상세 결과 보기 →
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ── 분석 실패 ── */}
          {step === "failed" && (
            <div className="space-y-5">
              <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 text-center">
                <div className="mb-3 text-5xl">❌</div>
                <h2 className="text-xl font-bold text-foreground">
                  분석에 실패했습니다
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  이미지가 불명확하거나 서버 오류가 발생했습니다.
                  <br />
                  선명한 이미지로 다시 시도해주세요.
                </p>
                {failReason && (
                  <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs font-mono text-red-400">
                    {failReason}
                  </p>
                )}
              </div>

              {/* 업로드한 이미지 미리보기 */}
              <div className="rounded-xl border border-border bg-card p-5">
                <p className="mb-3 text-sm font-semibold text-muted-foreground">
                  📷 업로드한 이미지
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {[front, back].map((slot) =>
                    slot ? (
                      <div key={slot.label} className="space-y-1">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={slot.preview}
                          alt={`알약 ${slot.label}`}
                          className="h-36 w-full rounded-lg object-cover opacity-60"
                        />
                        <p className="text-center text-xs text-muted-foreground">
                          {slot.label}
                        </p>
                      </div>
                    ) : null
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                <p className="mb-2 font-medium text-foreground">
                  💡 분석 실패 시 확인사항
                </p>
                <ul className="list-inside list-disc space-y-1 text-xs">
                  <li>알약이 화면 중앙에 선명하게 찍혔는지 확인하세요.</li>
                  <li>각인 문자가 보이도록 밝은 곳에서 촬영하세요.</li>
                  <li>JPG, PNG, WEBP 형식의 이미지를 사용하세요.</li>
                </ul>
              </div>

              <button
                onClick={resetAnalyze}
                className="w-full rounded-xl bg-teal-600 py-3.5 text-sm font-semibold text-white transition hover:bg-teal-500"
              >
                다시 시도하기
              </button>
            </div>
          )}
        </>
      )}

      {/* ══════════════════════════════════════
          탭 2: 분석 기록
      ══════════════════════════════════════ */}
      {tab === "list" && (
        <div className="space-y-5">
          <h1 className="text-2xl font-bold text-foreground">내 분석 기록</h1>

          {/* 검색 */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="제품명으로 검색"
              className="flex-1 rounded-xl border border-input bg-card px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-teal-500/50 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-500"
            >
              검색
            </button>
          </form>

          {/* 목록 */}
          {listLoading ? (
            <div className="flex justify-center py-16">
              <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
            </div>
          ) : list.length === 0 ? (
            <div className="rounded-xl border border-border bg-card py-16 text-center text-sm text-muted-foreground">
              분석 기록이 없습니다.
            </div>
          ) : (
            <div className="divide-y divide-border rounded-xl border border-border bg-card">
              {list.map((item) => (
                <button
                  key={item.analysis_id}
                  onClick={() => router.push(`/pill/${item.analysis_id}`)}
                  className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-teal-500/5"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">
                      {item.product_name ?? "분석 결과 없음"}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {item.efficacy ?? "-"}
                    </p>
                  </div>
                  <div className="ml-4 shrink-0 text-right">
                    <p className="text-xs text-muted-foreground">
                      {item.created_at.slice(0, 10)}
                    </p>
                    <p className="mt-0.5 text-xs text-teal-500">상세 보기 →</p>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* 페이징 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() => handlePage(page - 1)}
                disabled={page === 1}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-30"
              >
                ‹
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => handlePage(p)}
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
                onClick={() => handlePage(page + 1)}
                disabled={page === totalPages}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground transition hover:border-teal-500/40 hover:text-foreground disabled:opacity-30"
              >
                ›
              </button>
            </div>
          )}
        </div>
      )}

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
