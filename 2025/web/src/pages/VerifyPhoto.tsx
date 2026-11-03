import React from "react";

type VerifyResult = {
  score: number;             // 0~1
  passed: boolean;           // 적용 임계치로 판정
  threshold: number;         // 적용 임계치(개인 또는 모델)
  modelThreshold?: number;   // 모델 전역 임계치(표시용)
  message?: string;
  checkId?: string;          // 보고서 링크용
  camPath?: string;          // (미사용) 서버 히트맵 경로
};

export default function VerifyPhoto() {
  const VERIFY_API = (import.meta.env as any).VITE_VERIFY_API as string | undefined;
  const REPORT_BASE = (import.meta.env as any).VITE_REPORT_BASE as string | undefined;

  // public/ 에 둔 고정 히트맵 이미지 경로
  const HEATMAP_URL = `${import.meta.env.BASE_URL}heatmap.png`;

  const [userId, setUserId] = React.useState("jiwon");
  const [file, setFile] = React.useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<VerifyResult | null>(null);

  React.useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const onPickFile = (files: FileList | null) => {
    if (!files || !files[0]) return;
    const f = files[0];
    setFile(f);
    setResult(null);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
  };

  const onDrop: React.DragEventHandler<HTMLLabelElement> = (e) => {
    e.preventDefault();
    onPickFile(e.dataTransfer.files);
  };
  const onDragOver: React.DragEventHandler<HTMLLabelElement> = (e) => e.preventDefault();

  const clearFile = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  };

  const handleVerify = async () => {
    if (!VERIFY_API) {
      setError("VERIFY_API가 설정되어 있지 않습니다 (.env 확인).");
      return;
    }
    if (!userId.trim()) {
      setError("사용자 ID를 입력해 주세요.");
      return;
    }
    if (!file) {
      setError("확인할 서명 이미지를 선택해 주세요.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const fd = new FormData();
      fd.append("userId", userId.trim());
      fd.append("file", file);

      const res = await fetch(VERIFY_API, { method: "POST", body: fd });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as VerifyResult;
      setResult(data);
    } catch (e: any) {
      setError(e?.message || "확인 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const hasReport = Boolean(REPORT_BASE && result?.checkId);

  return (
    <main className="min-h-screen bg-white text-slate-800">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl md:text-3xl font-bold">Verify by Photo</h1>
        <p className="mt-2 text-slate-600 text-sm">
          등록 샘플을 사용하거나(서버 기반), 기준/검증 이미지를 직접 업로드해 유사도를 계산합니다.
          임계치는 모델이 계산한 최적값(또는 개인 보정값)을 자동 적용합니다.
        </p>

        {/* 사용자 입력 */}
        <div className="mt-6 flex flex-col md:flex-row items-start md:items-center gap-3">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="w-full md:w-60 rounded-lg border px-3 py-2 text-sm"
            placeholder="사용자 ID"
          />
        </div>

        {/* 업로드/프리뷰 */}
        <div className="mt-6">
          <div className="max-w-2xl">
            {!previewUrl ? (
              <label
                htmlFor="verify-file"
                onDrop={onDrop}
                onDragOver={onDragOver}
                className="block h-48 rounded-xl border-2 border-dashed border-slate-300 bg-white hover:bg-slate-50 transition grid place-items-center cursor-pointer"
              >
                <div className="text-center">
                  <div className="mx-auto mb-2 h-8 w-8 rounded-full bg-slate-900/90 text-white grid place-items-center">
                    ↑
                  </div>
                  <div className="text-slate-900 font-medium">클릭하여 파일 선택</div>
                  <div className="mt-1 text-xs text-slate-500">또는 여기로 드래그 앤 드롭</div>
                </div>
                <input
                  id="verify-file"
                  type="file"
                  accept="image/png,image/jpeg,application/pdf"
                  onChange={(e) => onPickFile(e.target.files)}
                  className="hidden"
                />
              </label>
            ) : (
              <div className="relative rounded-xl border bg-white p-3">
                <img
                  src={previewUrl}
                  className="block max-h-80 w-auto object-contain mx-auto"
                  alt="업로드한 서명"
                />
                <div className="mt-3 flex items-center justify-end gap-2">
                  <label
                    htmlFor="verify-file-repick"
                    className="inline-flex items-center rounded-lg border px-3 py-1.5 text-sm hover:bg-slate-50 cursor-pointer"
                  >
                    다른 파일 선택
                    <input
                      id="verify-file-repick"
                      type="file"
                      accept="image/png,image/jpeg,application/pdf"
                      onChange={(e) => onPickFile(e.target.files)}
                      className="hidden"
                    />
                  </label>
                  <button
                    onClick={clearFile}
                    className="inline-flex items-center rounded-lg border px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    제거
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 액션 */}
          <div className="mt-6 flex items-center gap-4">
            <button
              onClick={handleVerify}
              className="rounded-xl bg-slate-900 text-white px-5 py-2.5 hover:bg-slate-800 disabled:opacity-40"
              disabled={!file || loading}
            >
              {loading ? "확인 중…" : "확인"}
            </button>
          </div>

          {/* 에러 */}
          {error && (
            <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          {/* 결과 카드 */}
          {result && (
            <div className="mt-6 rounded-xl border bg-white p-5">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold text-slate-900">결과</div>
                <div
                  className={
                    "px-3 py-1 rounded-full text-sm font-medium " +
                    (result.passed
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-rose-100 text-rose-700")
                  }
                >
                  {result.passed ? "통과" : "불일치"}
                </div>
              </div>

              <div className="mt-3 grid gap-2 md:grid-cols-4 text-sm">
                <div className="rounded-lg bg-slate-50 p-3">
                  <div className="text-slate-500">임계치(적용)</div>
                  <div className="mt-1 font-semibold">{result.threshold.toFixed(2)}</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <div className="text-slate-500">임계치(모델)</div>
                  <div className="mt-1 font-semibold">
                    {result.modelThreshold != null ? result.modelThreshold.toFixed(2) : "-"}
                  </div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <div className="text-slate-500">점수(유사도)</div>
                  <div className="mt-1 font-semibold">{result.score.toFixed(3)}</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <div className="text-slate-500">사용자</div>
                  <div className="mt-1 font-semibold">{userId || "-"}</div>
                </div>
              </div>

              {result.message && (
                <div className="mt-3 text-xs text-slate-500">{result.message}</div>
              )}

              {hasReport && (
                <div className="mt-4">
                  <a
                    href={`${REPORT_BASE}/report/${encodeURIComponent(userId)}/${result!.checkId}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
                  >
                    PDF 보고서 보기
                  </a>
                </div>
              )}
            </div>
          )}

          {/* 보고서 미리보기 — 고정 히트맵 이미지 */}
          {result && (
            <div className="mt-6 rounded-xl border bg-white p-5">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold">보고서 미리보기</div>
                {hasReport && (
                  <a
                    href={`${REPORT_BASE}/report/${encodeURIComponent(userId)}/${result!.checkId}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
                  >
                    PDF 보고서 보기
                  </a>
                )}
              </div>

              <div className="mt-3 grid gap-4 md:grid-cols-2 text-sm">
                <div className="rounded-lg border p-3">
                  <div className="font-semibold text-slate-700 mb-2">요약</div>
                  <div className="text-slate-500">
                    검증 일시 <span className="font-medium">{new Date().toLocaleString()}</span>
                  </div>
                  <div className="text-slate-500">
                    사용자 <span className="font-medium">{userId}</span>
                  </div>
                  <div className="text-slate-500">
                    모듈/엔진 <span className="font-medium">AegisSign — Verify by Photo</span>
                  </div>
                  <div className="text-slate-500">
                    판정{" "}
                    <span
                      className={
                        "font-medium " + (result.passed ? "text-emerald-600" : "text-rose-600")
                      }
                    >
                      {result.passed ? "통과" : "불일치"}
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border p-3">
                  <div className="font-semibold text-slate-700 mb-2">메타 정보</div>
                  <div className="text-slate-500">
                    임계치(적용) <span className="font-medium">{result.threshold.toFixed(2)}</span>
                  </div>
                  <div className="text-slate-500">
                    임계치(모델){" "}
                    <span className="font-medium">
                      {result.modelThreshold != null ? result.modelThreshold.toFixed(2) : "-"}
                    </span>
                  </div>
                  <div className="text-slate-500">
                    점수(유사도) <span className="font-medium">{result.score.toFixed(3)}</span>
                  </div>
                </div>
              </div>

              {/* 고정 히트맵 이미지 */}
              <div className="mt-4 rounded-lg border p-3">
                <div className="font-semibold text-slate-700 mb-2">유사도 히트맵</div>
                <img
                  src={HEATMAP_URL}
                  alt="유사도 히트맵"
                  className="block w-full max-h-72 object-contain mx-auto rounded-lg border"
                />
              </div>

              <ul className="mt-4 text-xs text-slate-500 list-disc pl-5">
                <li>본 결과는 임의/조작된 조건에 따라 오차가 발생할 수 있습니다.</li>
                <li>학습/개인화는 서버 측 임베딩에서 보정될 수 있습니다.</li>
                <li>등록된 기준 서명이 없을 경우 일부 추정 항목이 ‘확정값’을 표시하지 않습니다.</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
