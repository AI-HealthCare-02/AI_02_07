"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";

interface SyncResult {
  inserted: number;
  updated: number;
  skipped: number;
  failed: number;
  dry_run: boolean;
  since_date: string | null;
}

interface SyncLog {
  id: number;
  sync_type: string;
  since_date: string | null;
  inserted: number;
  updated: number;
  skipped: number;
  failed: number;
  dry_run: boolean;
  synced_at: string;
}

function Badge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-center">
      <p className="text-xs text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color}`}>{value.toLocaleString()}</p>
    </div>
  );
}

export default function DrugSyncPage() {
  const [sinceDays, setSinceDays] = useState<string>("7");
  const [sinceDate, setSinceDate] = useState<string>("");
  const [itemSeq, setItemSeq] = useState<string>("");
  const [dryRun, setDryRun] = useState(true);
  const [mode, setMode] = useState<"days" | "date" | "seq">("days");

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [logs, setLogs] = useState<SyncLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);

  const loadLogs = useCallback(() => {
    setLogsLoading(true);
    adminApi
      .getDrugSyncLogs(30)
      .then((res) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setLogs((res.data as any)?.data ?? []);
      })
      .catch(() => {})
      .finally(() => setLogsLoading(false));
  }, []);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleSync = async () => {
    setRunning(true);
    setResult(null);
    setError(null);

    const body: {
      since_days?: number | null;
      since_date?: string | null;
      item_seq?: string | null;
      dry_run: boolean;
    } = { dry_run: dryRun };

    if (mode === "days" && sinceDays) body.since_days = parseInt(sinceDays);
    else if (mode === "date" && sinceDate) body.since_date = sinceDate.replace(/-/g, "");
    else if (mode === "seq" && itemSeq) body.item_seq = itemSeq;

    try {
      const res = await adminApi.triggerDrugSync(body);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setResult((res.data as any)?.data as SyncResult);
      loadLogs();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "동기화 실패");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">약품 데이터 동기화</h1>
        <p className="mt-0.5 text-sm text-slate-400">
          공공데이터 API에서 변경된 의약품 데이터를 동기화합니다.
        </p>
      </div>

      {/* 동기화 설정 */}
      <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-5">
        <p className="text-sm font-semibold text-white">동기화 설정</p>

        {/* 모드 선택 */}
        <div className="flex gap-2">
          {(["days", "date", "seq"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                mode === m
                  ? "bg-teal-500/20 text-teal-400 border border-teal-500/40"
                  : "border border-white/10 text-slate-400 hover:text-slate-200"
              }`}
            >
              {m === "days" ? "최근 N일" : m === "date" ? "날짜 지정" : "특정 약품"}
            </button>
          ))}
        </div>

        {/* 입력 */}
        <div className="flex flex-wrap items-end gap-3">
          {mode === "days" && (
            <div>
              <label className="mb-1 block text-xs text-slate-400">최근 N일</label>
              <input
                type="number"
                min={1}
                value={sinceDays}
                onChange={(e) => setSinceDays(e.target.value)}
                className="w-28 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          )}
          {mode === "date" && (
            <div>
              <label className="mb-1 block text-xs text-slate-400">이후 변경분 (YYYY-MM-DD)</label>
              <input
                type="date"
                value={sinceDate}
                onChange={(e) => setSinceDate(e.target.value)}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          )}
          {mode === "seq" && (
            <div>
              <label className="mb-1 block text-xs text-slate-400">품목기준코드 (item_seq)</label>
              <input
                type="text"
                placeholder="예: 200003092"
                value={itemSeq}
                onChange={(e) => setItemSeq(e.target.value)}
                className="w-48 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-teal-500/50 focus:outline-none"
              />
            </div>
          )}

          {/* dry-run 토글 */}
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
            <button
              onClick={() => setDryRun((v) => !v)}
              className={`relative h-5 w-9 rounded-full transition-colors ${dryRun ? "bg-yellow-500" : "bg-teal-500"}`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  dryRun ? "translate-x-0.5" : "translate-x-4"
                }`}
              />
            </button>
            {dryRun ? (
              <span className="text-yellow-400 font-medium">Dry-run (시뮬레이션)</span>
            ) : (
              <span className="text-teal-400 font-medium">실제 동기화</span>
            )}
          </label>
        </div>

        {dryRun && (
          <p className="text-xs text-yellow-500/80">
            ⚠️ Dry-run 모드: DB를 변경하지 않고 결과만 확인합니다. 실제 동기화하려면 토글을 끄세요.
          </p>
        )}

        <button
          onClick={handleSync}
          disabled={running}
          className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${
            dryRun
              ? "bg-yellow-600 hover:bg-yellow-500"
              : "bg-teal-600 hover:bg-teal-500"
          }`}
        >
          {running ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              동기화 중...
            </>
          ) : dryRun ? (
            "🔍 시뮬레이션 실행"
          ) : (
            "🔄 동기화 실행"
          )}
        </button>
      </div>

      {/* 결과 */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-white">
              {result.dry_run ? "🔍 시뮬레이션 결과" : "✅ 동기화 결과"}
            </p>
            {result.since_date && (
              <span className="text-xs text-slate-400">{result.since_date} 이후 변경분</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Badge label="신규 추가" value={result.inserted} color="text-teal-400" />
            <Badge label="업데이트" value={result.updated} color="text-blue-400" />
            <Badge label="변경 없음" value={result.skipped} color="text-slate-400" />
            <Badge label="실패" value={result.failed} color="text-red-400" />
          </div>
          {result.dry_run && (
            <p className="text-xs text-yellow-500">
              시뮬레이션 결과입니다. 실제 DB는 변경되지 않았습니다.
            </p>
          )}
        </div>
      )}

      {/* 동기화 이력 */}
      <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <p className="text-sm font-semibold text-white">동기화 이력</p>
          <button
            onClick={loadLogs}
            className="text-xs text-slate-400 hover:text-teal-400 transition"
          >
            🔄 새로고침
          </button>
        </div>

        {logsLoading ? (
          <div className="flex justify-center py-10">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
          </div>
        ) : logs.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">동기화 이력이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/10 bg-white/5 text-left text-slate-400">
                  <th className="px-4 py-3">실행 시각</th>
                  <th className="px-4 py-3">유형</th>
                  <th className="px-4 py-3">기준일</th>
                  <th className="px-4 py-3 text-right">추가</th>
                  <th className="px-4 py-3 text-right">수정</th>
                  <th className="px-4 py-3 text-right">스킵</th>
                  <th className="px-4 py-3 text-right">실패</th>
                  <th className="px-4 py-3 text-center">모드</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 text-slate-300">{log.synced_at}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          log.sync_type === "incremental"
                            ? "bg-teal-500/15 text-teal-400"
                            : "bg-blue-500/15 text-blue-400"
                        }`}
                      >
                        {log.sync_type === "incremental" ? "증분" : "전체"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{log.since_date ?? "-"}</td>
                    <td className="px-4 py-3 text-right text-teal-400">{log.inserted.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-blue-400">{log.updated.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-slate-500">{log.skipped.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-red-400">{log.failed.toLocaleString()}</td>
                    <td className="px-4 py-3 text-center">
                      {log.dry_run ? (
                        <span className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-[10px] text-yellow-400">
                          dry-run
                        </span>
                      ) : (
                        <span className="rounded-full bg-green-500/15 px-2 py-0.5 text-[10px] text-green-400">
                          실행
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
