"use client";

import { useCallback, useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";
import { useAuthStore } from "@/store/auth-store";

// ── 타입 ──────────────────────────────────────────────────
type Tab = "analyze" | "list";
type Step = "upload" | "analyzing" | "done" | "unidentified" | "failed";

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
        알약 {label}
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
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
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
  const { isAuthenticated, _hasHydrated } = useAuthStore();
  const frontRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<Tab>("analyze");
  const [step, setStep] = useState<Step>("upload");
  const [front, setFront] = useState<ImageSlot | null>(null);
  const [back, setBack] = useState<ImageSlot | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [unidentifiedReason, setUnidentifiedReason] = useState<string | null>(null);
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

  useEffect(() => {
    if (_hasHydrated && !isAuthenticated) router.replace("/login");
  }, [_hasHydrated, isAuthenticated, router]);

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
    if (!front) return;
    setStep("analyzing");
    setElapsedSec(0);
    timerRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);

    const formData = new FormData();
    formData.append("front_image", front.file);
    if (back) formData.append("back_image", back.file);

    try {
      const { data } = await apiClient.post(
        "/api/v1/pill-analysis/analyze",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      if (timerRef.current) clearInterval(timerRef.current);

      const id = data.data?.analysis_id ?? null;
      const name: string = data.data?.product_name ?? "";
      const unidentifiedKeywords = ["식별 불가", "미매칭", "알약 이미지가 아닙니다", "여러 알약", "분석 실패"];
      const isUnidentified = unidentifiedKeywords.some((kw) => name.includes(kw));

      // 진행 바를 100%까지 채운 뒤 이동
      setElapsedSec(999);
      await new Promise((r) => setTimeout(r, 800));

      if (isUnidentified) {
        setUnidentifiedReason(name);
        setStep("unidentified");
      } else if (id) {
        router.push(`/pill/${id}`);
      } else {
        setAnalysisId(id);
        setStep("done");
      }
    } catch (e: unknown) {
      if (timerRef.current) clearInterval(timerRef.current);
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      setFailReason(msg);
      setStep("failed");
    }
  };

  const resetAnalyze = () => {
    setStep("upload");
    setFront(null);
    setBack(null);
    setAnalysisId(null);
    setFailReason(null);
    setUnidentifiedReason(null);
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
  const TOTAL_SEC = 55;
  const STEPS_LABEL = [
    { label: "이미지 전처리", doneAt: 3 },
    { label: "이미지 업로드", doneAt: 8 },
    { label: "AI 멀티모달 분석", doneAt: 45 },
    { label: "결과 저장", doneAt: 55 },
  ];
  const isApiDone = elapsedSec >= 999;
  const progressPct = isApiDone ? 100 : Math.min(Math.round((elapsedSec / TOTAL_SEC) * 100), 95);

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
            {t === "analyze" ? "알약 분석" : "분석 기록"}
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
                <h1 className="text-2xl font-bold text-foreground">알약 이미지 분석</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  알약 이미지를 업로드하면 AI가 약품 정보를 분석합니다.<br />
                  앞뒤가 한 장에 있거나 앞면만 있어도 분석 가능합니다.
                </p>
              </div>

              {/* 이미지 슬롯 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold text-muted-foreground">💊 앞면 <span className="text-red-400">*필수</span></p>
                  <ImageSlotCard slot={front} label="앞면" onSelect={() => frontRef.current?.click()} onRemove={() => setFront(null)} />
                </div>
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold text-muted-foreground">💊 뒷면 <span className="text-muted-foreground/60">(선택)</span></p>
                  <ImageSlotCard slot={back} label="뒷면" onSelect={() => backRef.current?.click()} onRemove={() => setBack(null)} />
                </div>
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
                알약의 각인 문자, 색상, 모양이 잘 보이도록 촬영해주세요.
              </p>

              {/* 촬영 가이드 */}
              <div className="rounded-xl border border-teal-500/20 bg-teal-500/5 p-4">
                <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-teal-400">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" />
                  </svg>
                  정확한 분석을 위한 촬영 가이드
                </div>
                <div className="space-y-3">
                  {[
                    { ok: true,  title: "각인이 선명하게 보이도록",   desc: "알약 표면의 글자·숫자가 또렷하게 찍히도록 가까이서 촬영하세요." },
                    { ok: true,  title: "밝은 곳에서 촬영",           desc: "자연광이나 밝은 조명 아래에서 그림자 없이 촬영하면 인식률이 높아집니다." },
                    { ok: true,  title: "한 장에 알약 하나만",         desc: "여러 알약이 함께 찍히면 분석이 실패합니다. 분석할 알약 하나만 촬영하세요." },
                    { ok: true,  title: "업로드 방법 3가지",           desc: "① 앞면만 업로드  ② 앞면 + 뒷면 각각 업로드 (권장)  ③ 앞뒤가 모두 보이는 사진 1장 업로드" },
                    { ok: false, title: "이런 이미지는 인식이 어려워요", desc: "흔들린 사진 · 각인이 가려진 사진 · 너무 어두운 사진 · 알약이 아닌 이미지" },
                  ].map(({ ok, title, desc }) => (
                    <div key={title} className="flex gap-3">
                      <span className="mt-0.5 shrink-0">
                        {ok ? (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                        ) : (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                        )}
                      </span>
                      <div>
                        <p className="text-xs font-medium text-foreground">{title}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 데이터 출처 */}
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="mb-2 flex items-center gap-2">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <p className="text-xs font-semibold text-muted-foreground">데이터 출처 및 분석 방식</p>
                </div>
                <div className="space-y-1.5 text-xs text-muted-foreground">
                  <p>· 식품의약품안전처 의약품 낱알 식별 정보 DB (~32,000개 약품)</p>
                  <p>· GPT Vision으로 각인·색상·모양을 분석 후 pgvector 유사도 검색으로 매칭</p>
                  <p>· AI 분석 결과는 참고용이며, 정확한 약품 확인은 약사에게 문의하세요.</p>
                </div>
              </div>

              <button
                onClick={startAnalysis}
                disabled={!front}
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
                <div className="mb-4 flex justify-center animate-spin text-teal-400">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                </div>
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
                  <span>{isApiDone ? "분석 완료" : "진행 중"}</span>
                  <span>{progressPct}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-teal-500 transition-all duration-700"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* 단계 */}
              <div className="w-full max-w-sm space-y-3 text-left">
                {STEPS_LABEL.map((s) => {
                  const done = isApiDone || elapsedSec >= s.doneAt;
                  const active = !done && elapsedSec >= s.doneAt - 5;
                  return (
                    <div key={s.label} className="flex items-center gap-3 text-sm">
                      <span className="shrink-0">
                        {done ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                        ) : active ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground"><circle cx="12" cy="12" r="10" /></svg>
                        )}
                      </span>
                      <span className={done ? "text-foreground" : "text-muted-foreground"}>
                        {s.label}
                        {active ? " 중..." : done ? " 완료" : " 대기"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── 분석 불가 ── */}
          {step === "unidentified" && (
            <div className="space-y-5">
              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-6 text-center">
                <div className="mb-3 flex justify-center text-yellow-500">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-foreground">알약을 식별할 수 없습니다</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {unidentifiedReason ?? "DB에서 일치하는 약품을 찾지 못했습니다."}
                </p>
              </div>
              <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                <p className="mb-2 font-medium text-foreground">식별 실패 시 확인사항</p>
                <ul className="list-inside list-disc space-y-1 text-xs">
                  <li>각인 문자가 선명하게 보이도록 촬영해주세요.</li>
                  <li>한 이미지에 하나의 알약만 촬영해주세요.</li>
                  <li>앞면과 뒷면을 각각 업로드하면 정확도가 높아집니다.</li>
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

          {/* ── 분석 완료 ── */}
          {step === "done" && (
            <div className="space-y-5">
              <div className="rounded-xl border border-teal-500/30 bg-teal-500/5 p-6 text-center">
                <div className="mb-3 flex justify-center text-teal-400">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-foreground">
                  분석이 완료되었습니다!
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  분석된 약품 정보를 확인하세요.
                </p>
              </div>

              {/* 업로드한 이미지 미리보기 */}
              <div className="rounded-xl border border-border bg-card p-5">
                <p className="mb-3 text-sm font-semibold text-teal-500">업로드한 이미지</p>
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
                <div className="mb-3 flex justify-center text-red-400">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                </div>
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
                <p className="mb-3 text-sm font-semibold text-muted-foreground">업로드한 이미지</p>
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
                <p className="mb-2 font-medium text-foreground">분석 실패 시 확인사항</p>
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
