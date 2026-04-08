"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import apiClient from "@/lib/axios";

const PROVIDER_LABEL: Record<string, string> = {
  KAKAO: "카카오",
  GOOGLE: "구글",
  LOCAL: "일반 가입",
};

interface Profile {
  name: string;
  email: string;
  provider_code: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const { clearAuth } = useAuthStore();

  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get("/api/v1/users/me")
      .then(({ data }) => setProfile(data.data))
      .catch(() => setError("프로필을 불러오는 데 실패했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await apiClient.delete("/api/v1/users/me", {
        data: { confirm_text: "탈퇴합니다" },
      });
      clearAuth();
      router.replace("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "계정 삭제에 실패했습니다.");
      setShowConfirm(false);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/30 border-t-teal-400" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-foreground">개인정보</h1>

      {error && (
        <div className="mb-6 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-500">{error}</div>
      )}

      {/* 정보 카드 */}
      <div className="rounded-xl border border-border bg-card divide-y divide-border">
        <InfoRow label="이름" value={profile?.name ?? "-"} />
        <InfoRow label="이메일" value={profile?.email ?? "-"} />
        <InfoRow
          label="가입 경로"
          value={PROVIDER_LABEL[profile?.provider_code ?? ""] ?? profile?.provider_code ?? "-"}
        />
      </div>

      {/* 계정 삭제 */}
      <div className="mt-10">
        <button
          onClick={() => setShowConfirm(true)}
          className="w-full rounded-lg border border-red-500/30 py-3 text-sm font-medium text-red-500 transition hover:border-red-500/60 hover:bg-red-500/10"
        >
          계정 삭제 요청
        </button>
      </div>

      {/* 삭제 확인 모달 */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
            <h2 className="mb-4 text-base font-semibold text-foreground">계정 삭제</h2>
            <p className="mb-6 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {`정말로 계정을 삭제하시겠습니까?\n삭제 시 모든 건강기록, 가이드, 대화 내역이\n영구 삭제되며 복구할 수 없습니다.`}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                disabled={deleting}
                className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground transition hover:text-foreground disabled:opacity-40"
              >
                취소
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 rounded-lg bg-red-600 py-2.5 text-sm font-medium text-white transition hover:bg-red-500 disabled:opacity-50"
              >
                {deleting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    삭제 중...
                  </span>
                ) : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-5 py-4">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}
