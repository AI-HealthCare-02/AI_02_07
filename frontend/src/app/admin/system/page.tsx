"use client";

import { useEffect, useState } from "react";
import { adminApi, SystemSettings } from "@/lib/admin-api";

interface TestResult {
  success: boolean;
  responseTime: number | null;
  testResponse: string | null;
  errorMessage: string | null;
}

export default function AdminSystemPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // 폼 상태
  const [answerModel, setAnswerModel] = useState("gpt-4o");
  const [answerTemp, setAnswerTemp] = useState(0.7);
  const [answerMaxTokens, setAnswerMaxTokens] = useState(2000);

  useEffect(() => {
    adminApi
      .getSystemSettings()
      .then(({ data }) => {
        const s = data.data;
        setSettings(s);
        setAnswerModel(s.answerModel.apiModel);
        setAnswerTemp(s.answerModel.temperature);
        setAnswerMaxTokens(s.answerModel.maxTokens);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const { data } = await adminApi.updateSystemSettings({
        answerModel: { apiModel: answerModel, temperature: answerTemp, maxTokens: answerMaxTokens },
        filterModel: { apiModel: settings?.filterModel.apiModel ?? "gpt-4o-mini" },
      });
      setSettings(data.data);
      setSuccess("설정이 저장되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await adminApi.testLlm({
        apiModel: answerModel,
        temperature: answerTemp,
        maxTokens: answerMaxTokens,
      });
      setTestResult(data.data as TestResult);
    } catch (e) {
      setTestResult({
        success: false,
        responseTime: null,
        testResponse: null,
        errorMessage: e instanceof Error ? e.message : "테스트 실패",
      });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-white/5" />
        <div className="h-64 animate-pulse rounded-2xl bg-white/5" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">시스템 설정</h1>
        <p className="mt-0.5 text-sm text-slate-400">LLM 모델 및 파라미터를 설정합니다.</p>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-xl bg-teal-500/10 border border-teal-500/20 px-4 py-3 text-sm text-teal-400">
          {success}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-5">
        {/* 답변 모델 */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <h2 className="mb-4 text-sm font-semibold text-white">답변 생성 모델</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">모델명</label>
              <input
                value={answerModel}
                onChange={(e) => setAnswerModel(e.target.value)}
                placeholder="gpt-4o"
                required
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">
                Temperature <span className="text-teal-400">{answerTemp}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={answerTemp}
                onChange={(e) => setAnswerTemp(parseFloat(e.target.value))}
                className="w-full accent-teal-500"
              />
              <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                <span>0.0</span><span>1.0</span>
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Max Tokens</label>
              <input
                type="number"
                min={100}
                max={16384}
                value={answerMaxTokens}
                onChange={(e) => setAnswerMaxTokens(parseInt(e.target.value))}
                required
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30"
              />
            </div>
          </div>

          {/* LLM 테스트 */}
          <div className="mt-4 border-t border-white/10 pt-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleTest}
                disabled={testing}
                className="flex items-center gap-2 rounded-lg border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-400 transition hover:bg-teal-500/20 disabled:opacity-50"
              >
                {testing ? (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border border-teal-400 border-t-transparent" />
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                )}
                {testing ? "테스트 중..." : "모델 테스트"}
              </button>
              {testResult && (
                <span className={`text-xs ${testResult.success ? "text-teal-400" : "text-red-400"}`}>
                  {testResult.success
                    ? `✓ 성공 (${testResult.responseTime}ms)`
                    : `✗ ${testResult.errorMessage}`}
                </span>
              )}
            </div>
            {testResult?.testResponse && (
              <div className="mt-3 rounded-lg bg-white/5 px-4 py-3 text-xs text-slate-300">
                {testResult.testResponse}
              </div>
            )}
          </div>
        </div>

        {/* 저장 */}
        <div className="flex items-center justify-between">
          {settings && (
            <p className="text-xs text-slate-500">
              마지막 수정: {new Date(settings.updatedAt).toLocaleString("ko-KR")}
            </p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="ml-auto flex items-center gap-2 rounded-lg bg-teal-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-teal-500 disabled:opacity-50"
          >
            {saving ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : null}
            {saving ? "저장 중..." : "설정 저장"}
          </button>
        </div>
      </form>
    </div>
  );
}
