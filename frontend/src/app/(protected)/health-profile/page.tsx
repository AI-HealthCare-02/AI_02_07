"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { useCodesByGroup } from "@/hooks/use-common-codes";
import apiClient from "@/lib/axios";

// ── 타입 ──────────────────────────────────────
interface CommonCode { code: string; code_name: string; sort_order: number; }
interface Allergy { allergy_id: number; allergy_name: string; }
interface Disease { disease_id: number; disease_name: string; }

interface LifestyleForm {
  height: string;
  weight: string;
  pregnancy_code: string;
  smoking_code: string;
  drinking_code: string;
  exercise_code: string;
  sleep_time_code: string;
}

// ── 공통코드 셀렉트 컴포넌트 ──────────────────
function CodeSelect({
  codes,
  value,
  onChange,
  loading,
}: {
  codes: CommonCode[] | undefined;
  value: string;
  onChange: (v: string) => void;
  loading: boolean;
}) {
  if (loading) return <div className="h-10 animate-pulse rounded-lg bg-white/5" />;
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white/80 focus:border-teal-500/50 focus:outline-none"
    >
      {(codes ?? []).map((c) => (
        <option key={c.code} value={c.code}>{c.code_name}</option>
      ))}
    </select>
  );
}

// ── 태그 입력 컴포넌트 (알레르기/기저질환 공용) ──
function TagInput({
  items,
  onAdd,
  onDelete,
  placeholder,
  adding,
}: {
  items: { id: number; name: string }[];
  onAdd: (name: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  placeholder: string;
  adding: boolean;
}) {
  const [input, setInput] = useState("");

  const handleAdd = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    await onAdd(trimmed);
    setInput("");
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder={placeholder}
          className="flex-1 rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white/80 placeholder:text-white/30 focus:border-teal-500/50 focus:outline-none"
        />
        <button
          onClick={handleAdd}
          disabled={adding || !input.trim()}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-500 disabled:opacity-40"
        >
          {adding ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white inline-block" /> : "추가"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={item.id}
            className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70"
          >
            {item.name}
            <button
              onClick={() => onDelete(item.id)}
              className="text-white/30 transition hover:text-red-400"
            >
              ✕
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── 메인 페이지 ──────────────────────────────
export default function HealthProfilePage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  // 공통코드
  const { data: pregnancyCodes, isLoading: loadingPregnancy } = useCodesByGroup("PREGNANCY");
  const { data: smokingCodes,   isLoading: loadingSmoking }   = useCodesByGroup("SMOKING");
  const { data: drinkingCodes,  isLoading: loadingDrinking }  = useCodesByGroup("DRINKING");
  const { data: exerciseCodes,  isLoading: loadingExercise }  = useCodesByGroup("EXERCISE");
  const { data: sleepCodes,     isLoading: loadingSleep }     = useCodesByGroup("SLEEP_TIME");

  // 상태
  const [pageLoading, setPageLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [addingAllergy, setAddingAllergy] = useState(false);
  const [addingDisease, setAddingDisease] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [gender, setGender] = useState("OTHER");
  const [birthDate, setBirthDate] = useState("");
  const [lifestyle, setLifestyle] = useState<LifestyleForm>({
    height: "", weight: "",
    pregnancy_code: "", smoking_code: "",
    drinking_code: "", exercise_code: "", sleep_time_code: "",
  });
  const [allergies, setAllergies] = useState<Allergy[]>([]);
  const [diseases, setDiseases] = useState<Disease[]>([]);

  const codesReady =
    !loadingPregnancy && !loadingSmoking && !loadingDrinking && !loadingExercise && !loadingSleep;

  const sortedFirst = (codes?: CommonCode[]) =>
    codes?.slice().sort((a, b) => a.sort_order - b.sort_order)[0]?.code ?? "";

  // 초기 데이터 로드 — 공통코드 준비 후 실행하여 기본값 순서 보장
  useEffect(() => {
    if (!codesReady) return;

    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    const load = async () => {
      try {
        const [profileRes, lifestyleRes, allergyRes, diseaseRes] = await Promise.all([
          apiClient.get("/api/v1/users/me"),
          apiClient.get("/api/v1/users/me/lifestyle"),
          apiClient.get("/api/v1/users/me/allergies"),
          apiClient.get("/api/v1/users/me/diseases"),
        ]);

        // 성별: API 값 우선, 없으면 OTHER
        const profile = profileRes.data.data;
        setGender(profile.gender_code ?? "OTHER");
        setBirthDate(profile.birth_date ?? "");

        // 생활습관: API 값 우선, 없으면 sort_order 가장 낮은 공통코드로 기본값
        const ls = lifestyleRes.data.data;
        setLifestyle({
          height:          ls?.height?.toString() ?? "",
          weight:          ls?.weight?.toString() ?? "",
          pregnancy_code:  ls?.pregnancy_code  ?? sortedFirst(pregnancyCodes),
          smoking_code:    ls?.smoking_code    ?? sortedFirst(smokingCodes),
          drinking_code:   ls?.drinking_code   ?? sortedFirst(drinkingCodes),
          exercise_code:   ls?.exercise_code   ?? sortedFirst(exerciseCodes),
          sleep_time_code: ls?.sleep_time_code ?? sortedFirst(sleepCodes),
        });

        setAllergies(allergyRes.data.data ?? []);
        setDiseases(diseaseRes.data.data ?? []);
      } catch {
        setError("데이터를 불러오는 데 실패했습니다.");
      } finally {
        setPageLoading(false);
      }
    };

    load();
  }, [codesReady]); // eslint-disable-line react-hooks/exhaustive-deps

  // 저장
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      // 프로필 (성별, 생년월일)
      await apiClient.patch("/api/v1/users/me", {
        gender_code: gender === "OTHER" ? null : gender,
        ...(birthDate ? { birth_date: birthDate } : {}),
      });

      // 생활습관
      const lsPayload: Record<string, string | number | null> = {};
      if (lifestyle.height)         lsPayload.height         = Number(lifestyle.height);
      if (lifestyle.weight)         lsPayload.weight         = Number(lifestyle.weight);
      if (lifestyle.pregnancy_code) lsPayload.pregnancy_code = lifestyle.pregnancy_code;
      if (lifestyle.smoking_code)   lsPayload.smoking_code   = lifestyle.smoking_code;
      if (lifestyle.drinking_code)  lsPayload.drinking_code  = lifestyle.drinking_code;
      if (lifestyle.exercise_code)  lsPayload.exercise_code  = lifestyle.exercise_code;
      if (lifestyle.sleep_time_code) lsPayload.sleep_time_code = lifestyle.sleep_time_code;

      await apiClient.put("/api/v1/users/me/lifestyle", lsPayload);

      router.push("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  // 알레르기 추가/삭제
  const addAllergy = async (name: string) => {
    setAddingAllergy(true);
    try {
      const { data } = await apiClient.post("/api/v1/users/me/allergies", { allergy_name: name });
      setAllergies((prev) => [...prev, data.data]);
    } finally {
      setAddingAllergy(false);
    }
  };
  const deleteAllergy = async (id: number) => {
    await apiClient.delete(`/api/v1/users/me/allergies/${id}`);
    setAllergies((prev) => prev.filter((a) => a.allergy_id !== id));
  };

  // 기저질환 추가/삭제
  const addDisease = async (name: string) => {
    setAddingDisease(true);
    try {
      const { data } = await apiClient.post("/api/v1/users/me/diseases", { disease_name: name });
      setDiseases((prev) => [...prev, data.data]);
    } finally {
      setAddingDisease(false);
    }
  };
  const deleteDisease = async (id: number) => {
    await apiClient.delete(`/api/v1/users/me/diseases/${id}`);
    setDiseases((prev) => prev.filter((d) => d.disease_id !== id));
  };

  // ── 로딩 ──
  if (pageLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  // ── 렌더 ──
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-white">헬스정보 수정</h1>

      {error && (
        <div className="mb-6 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      <div className="space-y-8">
        {/* ── 기본 정보 ── */}
        <Section title="기본 정보">
          {/* 성별 */}
          <Field label="성별">
            <div className="flex gap-3">
              {[
                { value: "M", label: "남성" },
                { value: "F", label: "여성" },
                { value: "OTHER", label: "기타" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setGender(opt.value)}
                  className={`flex-1 rounded-lg border py-2 text-sm font-medium transition ${
                    gender === opt.value
                      ? "border-teal-500 bg-teal-500/15 text-teal-300"
                      : "border-white/10 bg-white/5 text-white/50 hover:border-white/20"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </Field>

          {/* 생년월일 */}
          <Field label="생년월일">
            <input
              type="date"
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
              max={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white/80 focus:border-teal-500/50 focus:outline-none [color-scheme:dark]"
            />
          </Field>
        </Section>

        {/* ── 신체 정보 ── */}
        <Section title="신체 정보">
          <div className="grid grid-cols-2 gap-4">
            <Field label="키 (cm)">
              <input
                type="number"
                value={lifestyle.height}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "" || (Number(v) > 0 && Number(v) <= 250))
                    setLifestyle((p) => ({ ...p, height: v }));
                }}
                placeholder="예: 170"
                min={1} max={250}
                className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white/80 placeholder:text-white/30 focus:border-teal-500/50 focus:outline-none"
              />
            </Field>
            <Field label="몸무게 (kg)">
              <input
                type="number"
                value={lifestyle.weight}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "" || (Number(v) > 0 && Number(v) <= 200))
                    setLifestyle((p) => ({ ...p, weight: v }));
                }}
                placeholder="예: 65"
                min={1} max={200}
                className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white/80 placeholder:text-white/30 focus:border-teal-500/50 focus:outline-none"
              />
            </Field>
          </div>
        </Section>

        {/* ── 생활 습관 ── */}
        <Section title="생활 습관">
          <Field label="임신/수유 여부">
            <CodeSelect codes={pregnancyCodes} value={lifestyle.pregnancy_code}
              onChange={(v) => setLifestyle((p) => ({ ...p, pregnancy_code: v }))}
              loading={loadingPregnancy} />
          </Field>
          <Field label="흡연 여부">
            <CodeSelect codes={smokingCodes} value={lifestyle.smoking_code}
              onChange={(v) => setLifestyle((p) => ({ ...p, smoking_code: v }))}
              loading={loadingSmoking} />
          </Field>
          <Field label="음주 빈도">
            <CodeSelect codes={drinkingCodes} value={lifestyle.drinking_code}
              onChange={(v) => setLifestyle((p) => ({ ...p, drinking_code: v }))}
              loading={loadingDrinking} />
          </Field>
          <Field label="운동 빈도">
            <CodeSelect codes={exerciseCodes} value={lifestyle.exercise_code}
              onChange={(v) => setLifestyle((p) => ({ ...p, exercise_code: v }))}
              loading={loadingExercise} />
          </Field>
          <Field label="수면 시간">
            <CodeSelect codes={sleepCodes} value={lifestyle.sleep_time_code}
              onChange={(v) => setLifestyle((p) => ({ ...p, sleep_time_code: v }))}
              loading={loadingSleep} />
          </Field>
        </Section>

        {/* ── 알레르기 ── */}
        <Section title="알레르기">
          <TagInput
            items={allergies.map((a) => ({ id: a.allergy_id, name: a.allergy_name }))}
            onAdd={addAllergy}
            onDelete={deleteAllergy}
            placeholder="알레르기 입력 후 추가 또는 Enter"
            adding={addingAllergy}
          />
        </Section>

        {/* ── 기저질환 ── */}
        <Section title="기저질환">
          <TagInput
            items={diseases.map((d) => ({ id: d.disease_id, name: d.disease_name }))}
            onAdd={addDisease}
            onDelete={deleteDisease}
            placeholder="기저질환 입력 후 추가 또는 Enter"
            adding={addingDisease}
          />
        </Section>
      </div>

      {/* ── 저장 버튼 ── */}
      <div className="mt-10 flex gap-3">
        <button
          onClick={() => router.back()}
          className="flex-1 rounded-lg border border-white/10 py-3 text-sm font-medium text-white/50 transition hover:border-white/20 hover:text-white/70"
        >
          취소
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 rounded-lg bg-teal-600 py-3 text-sm font-medium text-white transition hover:bg-teal-500 disabled:opacity-50"
        >
          {saving ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              저장 중...
            </span>
          ) : "저장"}
        </button>
      </div>
    </div>
  );
}

// ── 레이아웃 헬퍼 ──
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-6">
      <h2 className="mb-4 text-sm font-semibold text-teal-400">{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-white/40">{label}</label>
      {children}
    </div>
  );
}
