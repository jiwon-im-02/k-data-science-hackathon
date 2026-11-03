// src/pages/PhotoVerify.tsx
import React from "react";
import { useNavigate } from "react-router-dom";
import { verifyByPhoto, verifyByPhotoUsingEnrolled } from "@/lib/api"; // 별칭 없으면 "../lib/api"

export default function PhotoVerify() {
  const nav = useNavigate();

  // 업로드 상태
  const [refFile, setRefFile] = React.useState<File | null>(null);
  const [probeFile, setProbeFile] = React.useState<File | null>(null);

  // 모드/설정
  const [useEnrolled, setUseEnrolled] = React.useState(true); // 기본: 등록 샘플 사용
  const [userId, setUserId] = React.useState("");
  const [thr, setThr] = React.useState(0.72);

  // UI 상태
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string>("");

  // 미리보기 URL
  const refUrl = React.useMemo(() => (refFile ? URL.createObjectURL(refFile) : ""), [refFile]);
  const probeUrl = React.useMemo(() => (probeFile ? URL.createObjectURL(probeFile) : ""), [probeFile]);

  const onSubmit = async () => {
    setLoading(true);
    setErr("");

    try {
      let result;
      if (useEnrolled) {
        if (!userId.trim()) {
          alert("사용자 ID를 입력하세요.");
          setLoading(false);
          return;
        }
        if (!probeFile) {
          alert("확인할 서명을 첨부하세요.");
          setLoading(false);
          return;
        }
        // 등록된 기준 샘플로 검증 (probe만 전송)
        result = await verifyByPhotoUsingEnrolled(userId.trim(), probeFile, thr);
      } else {
        if (!refFile || !probeFile) {
          alert("본인 서명과 확인할 서명을 모두 첨부해주세요.");
          setLoading(false);
          return;
        }
        // 직접 기준(ref) + probe 전송
        result = await verifyByPhoto(refFile, probeFile, thr);
      }

      // 결과 페이지로 이동 (썸네일/파일명도 같이 전달)
      nav("/result", {
        state: {
          result,
          refName: refFile?.name,
          probeName: probeFile?.name,
          refUrl: refUrl || null,
          probeUrl,
        },
      });
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-[calc(100vh-8rem)] bg-gradient-to-b from-white to-slate-50">
      <div className="max-w-screen-xl mx-auto px-6 py-14">
        <div className="text-center">
          <h1 className="text-4xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-indigo-600 to-emerald-600 bg-clip-text text-transparent">
              Verify by Photo
            </span>
          </h1>
          <p className="mt-3 text-slate-600">
            등록 샘플을 사용하거나(권장), 기준/검증 이미지를 직접 업로드해 유사도를 계산합니다.
          </p>
        </div>

        {/* 모드 스위치 / 사용자 ID */}
        <div className="mt-8 rounded-xl border bg-white p-4 flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={useEnrolled}
              onChange={(e) => setUseEnrolled(e.target.checked)}
            />
            <span className="text-sm">내 등록 샘플 사용 (권장)</span>
          </label>

          {useEnrolled ? (
            <input
              className="border rounded px-3 py-2"
              placeholder="사용자 ID (예: jiwon_kds)"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          ) : (
            <span className="text-xs text-slate-500">
              ※ 등록 샘플을 쓰지 않고, 기준이미지 + 검증이미지를 직접 업로드합니다.
            </span>
          )}
        </div>

        {/* 업로드 카드 */}
        <div className="mt-8 grid lg:grid-cols-2 gap-8">
          {/* 기준 서명(등록 샘플 모드에서는 숨김) */}
          {!useEnrolled && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="text-sm font-medium">본인의 서명을 입력해주세요</div>
              <label className="mt-3 flex h-44 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 hover:border-indigo-400 transition cursor-pointer bg-slate-50">
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setRefFile(e.target.files?.[0] || null)}
                />
                <span className="text-slate-500">클릭하여 파일 선택</span>
              </label>
              {refUrl && (
                <div className="mt-4">
                  <div className="text-xs text-slate-500 mb-2">{refFile?.name}</div>
                  <img
                    src={refUrl}
                    alt="reference"
                    className="w-full max-h-80 object-contain rounded-lg border"
                  />
                </div>
              )}
            </div>
          )}

          {/* 검증 서명(항상 표시) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="text-sm font-medium">확인할 서명을 입력해주세요</div>
            <label className="mt-3 flex h-44 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 hover:border-indigo-400 transition cursor-pointer bg-slate-50">
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => setProbeFile(e.target.files?.[0] || null)}
              />
              <span className="text-slate-500">클릭하여 파일 선택</span>
            </label>
            {probeUrl && (
              <div className="mt-4">
                <div className="text-xs text-slate-500 mb-2">{probeFile?.name}</div>
                <img
                  src={probeUrl}
                  alt="probe"
                  className="w-full max-h-80 object-contain rounded-lg border"
                />
              </div>
            )}
          </div>
        </div>

        {/* 액션 바 */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <label className="text-sm text-slate-600">임계치</label>
          <input
            type="number"
            step={0.01}
            min={0}
            max={1}
            value={thr}
            onChange={(e) => setThr(Number(e.target.value))}
            className="w-24 border rounded px-3 py-2"
          />
          <button
            onClick={onSubmit}
            disabled={loading}
            className="rounded-xl bg-slate-900 text-white px-6 py-3 hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? "분석 중..." : "확인"}
          </button>
          {err && <span className="text-sm text-red-600">{err}</span>}
        </div>
      </div>
    </main>
  );
}
