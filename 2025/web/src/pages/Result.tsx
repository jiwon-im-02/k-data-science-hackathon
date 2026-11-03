// src/pages/Result.tsx
import { useLocation, Link, Navigate } from "react-router-dom";

export default function Result() {
  const loc = useLocation() as any;
  const data = loc.state?.result as { final: number; verdict: "genuine"|"forgery"; similarities: number[] } | undefined;
  const refName = loc.state?.refName as string | undefined;
  const probeName = loc.state?.probeName as string | undefined;

  if (!data) return <Navigate to="/photo" replace />;

  const pct = Math.round((data.final ?? 0) * 100);

  return (
    <main className="min-h-[calc(100vh-8rem)]">
      <div className="max-w-screen-md mx-auto px-6 py-16">
        <h1 className="text-4xl font-extrabold text-center">Result</h1>

        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-8 space-y-4">
          <div className="text-sm text-slate-600">유사도</div>
          <div className="text-5xl font-extrabold">{pct}%</div>

          <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${data.verdict === "genuine" ? "bg-emerald-500" : "bg-amber-500"}`}
              style={{ width: `${pct}%` }}
            />
          </div>

          <div
            className={`inline-flex px-3 py-1 rounded-full text-sm font-medium
            ${data.verdict === "genuine" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}
          >
            {data.verdict === "genuine" ? "Genuine" : "Forgery?"}
          </div>

          <div className="text-sm text-slate-500 pt-2">
            <div>본인 서명: <b>{refName ?? "-"}</b></div>
            <div>확인 서명: <b>{probeName ?? "-"}</b></div>
          </div>
        </div>

        <div className="mt-8 flex justify-center gap-3">
          <Link to="/photo" className="rounded-lg border px-4 py-2 bg-white hover:bg-slate-50">다시 검사</Link>
          <Link to="/" className="rounded-lg border px-4 py-2 bg-white hover:bg-slate-50">홈으로</Link>
        </div>
      </div>
    </main>
  );
}
