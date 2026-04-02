export default function Footer() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">🏥</span>
              <span className="font-bold text-primary">HealthGuide</span>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              AI 기반 헬스케어 상담 서비스. 전문 의료 행위를 대체하지 않으며, 보조적 건강 관리 도구로 활용됩니다.
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold">서비스</h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>AI 챗봇 상담</li>
              <li>의료 문서 분석</li>
              <li>건강 가이드</li>
              <li>알약 분석</li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold">지원</h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>이용약관</li>
              <li>개인정보처리방침</li>
              <li>고객센터</li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold">안내</h3>
            <p className="mt-3 text-sm text-muted-foreground">
              본 서비스는 의료 전문가의 진단을 대체할 수 없습니다. 응급 상황 시 119에 연락하세요.
            </p>
          </div>
        </div>

        <div className="mt-8 border-t pt-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} HealthGuide. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
