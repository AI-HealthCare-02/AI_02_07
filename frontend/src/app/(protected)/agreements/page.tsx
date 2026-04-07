"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/axios";

// ── 동의 항목 정의 ─────────────────────────────
const AGREEMENTS = [
  {
    key: "agreed_personal_info" as const,
    title: "개인정보 수집 및 이용 동의",
    required: true,
    content: `■ 수집 항목
이름, 이메일, 닉네임, 성별, 생년월일, 가입 경로

■ 수집 목적
회원 식별 및 서비스 제공, 맞춤형 건강 정보 안내

■ 보유 기간
회원 탈퇴 시까지 (탈퇴 후 30일 이내 파기)

■ 동의 거부 권리
개인정보 수집에 동의하지 않을 권리가 있으나,
동의 거부 시 서비스 이용이 제한됩니다.`,
  },
  {
    key: "agreed_sensitive_info" as const,
    title: "민감정보 수집 및 이용 동의",
    required: true,
    content: `■ 수집 항목
건강 상태, 기저질환, 알레르기, 생활습관 정보
(흡연·음주·운동·수면·임신/수유 여부)

■ 수집 목적
AI 기반 맞춤형 건강 상담 및 가이드 제공

■ 보유 기간
회원 탈퇴 시까지 (탈퇴 후 30일 이내 파기)

■ 동의 거부 권리
민감정보 수집에 동의하지 않을 권리가 있으나,
동의 거부 시 건강 상담 서비스 이용이 제한됩니다.`,
  },
  {
    key: "agreed_medical_data" as const,
    title: "의료 데이터 활용 동의",
    required: true,
    content: `■ 활용 항목
업로드한 처방전, 진단서 등 의료 문서 및 분석 결과

■ 활용 목적
AI 의료 문서 분석, 복약 가이드 생성,
개인 맞춤형 건강 정보 제공

■ 보유 기간
회원 탈퇴 시까지 (탈퇴 후 30일 이내 파기)

■ 주의사항
본 서비스는 전문 의료 행위를 대체하지 않으며,
참고용 정보 제공을 목적으로 합니다.

■ 동의 거부 권리
의료 데이터 활용에 동의하지 않을 권리가 있으나,
동의 거부 시 의료 문서 분석 서비스 이용이 제한됩니다.`,
  },
];

type AgreementKey = (typeof AGREEMENTS)[number]["key"];

export default function AgreementsPage() {
  const router = useRouter();

  const [checked, setChecked] = useState<Record<AgreementKey, boolean>>({
    agreed_personal_info: false,
    agreed_sensitive_info: false,
    agreed_medical_data: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [checking, setChecking] = useState(true);

  // 토큰 없으면 로그인, 이미 동의했으면 메인으로
  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
      return;
    }
    apiClient.get("/api/v1/users/me").then(({ data }) => {
      const p = data.data;
      if (p.agreed_personal_info && p.agreed_sensitive_info && p.agreed_medical_data) {
        router.replace("/");
      } else {
        setChecking(false);
      }
    }).catch(() => setChecking(false));
  }, [router]);

  const allChecked = Object.values(checked).every(Boolean);

  const toggleAll = (value: boolean) => {
    setChecked({
      agreed_personal_info: value,
      agreed_sensitive_info: value,
      agreed_medical_data: value,
    });
  };

  const handleSubmit = async () => {
    if (!allChecked) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.patch("/api/v1/users/me/agreements", {
        agreed_personal_info: true,
        agreed_sensitive_info: true,
        agreed_medical_data: true,
      });

      // 동의 완료 후 lifestyle 확인 → 없으면 헬스정보, 있으면 메인
      try {
        const { data } = await apiClient.get("/api/v1/users/me/lifestyle");
        router.replace(data.data ? "/" : "/health-profile");
      } catch {
        router.replace("/health-profile");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "동의 처리에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setSaving(false);
    }
  };

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      {/* 헤더 */}
      <div className="mb-8 text-center">
        <span className="text-4xl">🏥</span>
        <h1 className="mt-3 text-2xl font-bold text-white">서비스 이용 동의</h1>
        <p className="mt-2 text-sm text-white/40">
          HealthGuide 서비스 이용을 위해 아래 항목에 동의해주세요.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {/* 동의 항목 목록 */}
      <div className="space-y-4">
        {AGREEMENTS.map((item) => (
          <AgreementItem
            key={item.key}
            title={item.title}
            content={item.content}
            checked={checked[item.key]}
            onChange={(v) => setChecked((prev) => ({ ...prev, [item.key]: v }))}
          />
        ))}
      </div>

      {/* 전체 동의 */}
      <div className="mt-6 rounded-xl border border-teal-500/20 bg-teal-500/5 px-5 py-4">
        <label className="flex cursor-pointer items-center gap-3">
          <Checkbox
            checked={allChecked}
            onChange={toggleAll}
            accent
          />
          <span className="text-sm font-semibold text-teal-300">
            위 약관에 모두 동의합니다 (필수)
          </span>
        </label>
      </div>

      {/* 다음 버튼 */}
      <button
        onClick={handleSubmit}
        disabled={!allChecked || saving}
        className="mt-6 w-full rounded-xl bg-teal-600 py-3.5 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {saving ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            처리 중...
          </span>
        ) : (
          "동의하고 시작하기"
        )}
      </button>
    </div>
  );
}

// ── 개별 동의 항목 컴포넌트 ───────────────────
function AgreementItem({
  title,
  content,
  checked,
  onChange,
}: {
  title: string;
  content: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`rounded-xl border transition ${
      checked ? "border-teal-500/30 bg-teal-500/5" : "border-white/8 bg-white/3"
    }`}>
      {/* 항목 헤더 */}
      <div className="flex items-center gap-3 px-5 py-4">
        <Checkbox checked={checked} onChange={onChange} />
        <span className="flex-1 text-sm font-medium text-white/80">{title}</span>
        <span className="text-xs text-red-400/70">필수</span>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-2 text-xs text-white/30 transition hover:text-white/60"
        >
          {expanded ? "접기 ▲" : "보기 ▼"}
        </button>
      </div>

      {/* 내용 펼치기 */}
      {expanded && (
        <div className="border-t border-white/8 px-5 py-4">
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-white/40">
            {content}
          </pre>
          {/* 동의 버튼 */}
          <button
            onClick={() => { onChange(true); setExpanded(false); }}
            className="mt-4 w-full rounded-lg border border-teal-500/30 py-2 text-xs font-medium text-teal-400 transition hover:bg-teal-500/10"
          >
            동의합니다
          </button>
        </div>
      )}
    </div>
  );
}

// ── 체크박스 컴포넌트 ─────────────────────────
function Checkbox({
  checked,
  onChange,
  accent = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  accent?: boolean;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border transition ${
        checked
          ? accent
            ? "border-teal-400 bg-teal-500"
            : "border-teal-500 bg-teal-600"
          : "border-white/20 bg-white/5 hover:border-white/40"
      }`}
    >
      {checked && (
        <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
          <path d="M1 4L4 7.5L10 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}
