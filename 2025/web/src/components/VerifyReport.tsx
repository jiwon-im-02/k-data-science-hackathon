// src/components/VerifyReport.tsx
import React, { forwardRef } from "react";

export type ReportData = {
  userId: string;
  requestedAt: string; // ISO string
  operator?: string;   // 검증자(선택)
  org?: string;        // 의뢰기관/부서(선택)
  fileName?: string;
  threshold: number;
  score: number;
  passed: boolean;
  previewUrl: string | null;
  mode: "MY_SAMPLES" | "CUSTOM";
  modelVersion: string; // 예: "v1.0"
  engine: string;       // 예: "Siamese + RNN/TCN (hybrid)"
};

const Badge: React.FC<{ passed: boolean }> = ({ passed }) => (
  <span
    className={
      "px-3 py-1 rounded-full text-sm font-medium " +
      (passed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700")
    }
  >
    {passed ? "통과" : "불일치"}
  </span>
);

const Title: React.FC<{ text: string }> = ({ text }) => (
  <h3 className="text-[15px] font-semibold text-slate-900 mt-4 mb-2">{text}</h3>
);

/** A4 폭(96dpi 기준) 맞춰서 캡쳐하기 쉽도록 width 고정 */
const VerifyReport = forwardRef<HTMLDivElement, { data: ReportData }>(
  ({ data }, ref) => {
    const dt = new Date(data.requestedAt);
    const when = `${dt.getFullYear()}.${String(dt.getMonth() + 1).padStart(2, "0")}.${String(
      dt.getDate()
    ).padStart(2, "0")} ${String(dt.getHours()).padStart(2, "0")}:${String(
      dt.getMinutes()
    ).padStart(2, "0")}`;

    return (
      <div
        ref={ref}
        className="bg-white text-slate-800 w-[794px] min-h-[1123px] px-8 py-8"
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xl font-extrabold tracking-tight">
              <span className="bg-gradient-to-r from-indigo-600 to-emerald-600 bg-clip-text text-transparent">
                AegisSign
              </span>
            </div>
            <div className="text-[13px] text-slate-500">
              Verify by Photo — Verification Report
            </div>
          </div>
          <Badge passed={data.passed} />
        </div>

        {/* 요약 */}
        <div className="mt-4 grid grid-cols-2 gap-6 text-[13px]">
          <div className="rounded-lg border bg-white p-4">
            <Title text="요약" />
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <div className="text-slate-500">검증 일시</div>
              <div className="font-medium">{when}</div>

              <div className="text-slate-500">사용자</div>
              <div className="font-medium">{data.userId || "-"}</div>

              <div className="text-slate-500">모드</div>
              <div className="font-medium">
                {data.mode === "MY_SAMPLES" ? "내 등록 샘플" : "직접 업로드"}
              </div>

              <div className="text-slate-500">모델/엔진</div>
              <div className="font-medium">
                {data.engine} · {data.modelVersion}
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-white p-4">
            <Title text="메타 정보" />
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <div className="text-slate-500">임계치</div>
              <div className="font-semibold">{data.threshold.toFixed(2)}</div>

              <div className="text-slate-500">점수(유사도)</div>
              <div className="font-semibold">{data.score.toFixed(3)}</div>

              <div className="text-slate-500">판정</div>
              <div className="font-semibold">{data.passed ? "통과" : "불일치"}</div>

              <div className="text-slate-500">파일</div>
              <div className="font-medium">{data.fileName || "-"}</div>
            </div>
          </div>
        </div>

        {/* 입력 이미지 */}
        <div className="mt-4 rounded-lg border bg-white p-4">
          <Title text="입력 이미지" />
          <div className="rounded-lg border bg-slate-50 p-3">
            {data.previewUrl ? (
              <img
                src={data.previewUrl}
                alt="uploaded"
                className="max-h-[420px] w-auto object-contain mx-auto"
              />
            ) : (
              <div className="text-center text-slate-500 text-sm py-24">
                (이미지 없음)
              </div>
            )}
          </div>
        </div>

        {/* 의뢰/검증자 */}
        {(data.operator || data.org) && (
          <div className="mt-4 rounded-lg border bg-white p-4 text-[13px]">
            <Title text="의뢰/검증 정보" />
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <div className="text-slate-500">의뢰기관</div>
              <div className="font-medium">{data.org || "-"}</div>
              <div className="text-slate-500">검증자</div>
              <div className="font-medium">{data.operator || "-"}</div>
            </div>
          </div>
        )}

        {/* 노트/면책 */}
        <div className="mt-4 rounded-lg border bg-white p-4 text-[12px] leading-relaxed">
          <Title text="노트 및 면책" />
          <ul className="list-disc pl-5 space-y-1 text-slate-600">
            <li>본 결과는 입력된 임계치 기준으로 산정되었습니다.</li>
            <li>
              이미지 품질(해상도/노이즈/왜곡)과 전처리 조건에 따라 결과가 달라질 수
              있습니다.
            </li>
            <li>
              본 보고서는 참고 용도로 제공되며, 최종 법적 책임은 각 도입기관의
              내부 규정에 따릅니다.
            </li>
          </ul>
        </div>

        {/* 푸터 */}
        <div className="mt-6 text-[11px] text-slate-400">
          © {new Date().getFullYear()} AegisSign — All rights reserved.
        </div>
      </div>
    );
  }
);

export default VerifyReport;
