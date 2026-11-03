// src/pages/Home.tsx
import React from "react";
import { Link } from "react-router-dom";

/** '홍길동' 텍스트를 스트로크로 그려서 나타내는 버전(조금 더 크게/아래쪽) */
function SignatureHongAccurate() {
  const font =
    'Nanum Pen Script, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", system-ui, sans-serif';

  // 타이밍
  const drawDur = 1.8;
  const gap = 0.2;
  const d0 = 0.05;
  const d1 = d0 + drawDur + gap;
  const d2 = d1 + drawDur + gap;

  return (
    <div className="relative mx-auto w-full h-full flex items-center justify-center">
      {/* 프레임 없이 실제 글자 모양을 스트로크로 */}
      <svg
 	 viewBox="0 0 720 260"
  	className="w-full max-w-[640px] translate-y-12 md:translate-y-16 lg:translate-y-20"
	>

        <g
          fontFamily={font}
          fontSize="140"
          textAnchor="middle"
          dominantBaseline="middle"
          strokeWidth={4}
        >
          {/* 1) 홍 */}
          <text
            x="280"
            y="140"
            className="hong-stroke"
            style={{ animationDelay: `${d0}s` }}
          >
            홍
          </text>
          {/* 2) 길 */}
          <text
            x="400"
            y="140"
            className="hong-stroke"
            style={{ animationDelay: `${d1}s` }}
          >
            길
          </text>
          {/* 3) 동 */}
          <text
            x="520"
            y="140"
            className="hong-stroke"
            style={{ animationDelay: `${d2}s` }}
          >
            동
          </text>
        </g>
      </svg>
    </div>
  );
}

export default function Home() {
  return (
    <main className="bg-gradient-to-b from-slate-50 to-white text-slate-800">
      {/* === HERO =================================================== */}
      <section className="relative overflow-hidden">
        {/* 얇은 그리드/메시 배경 — 뒤로 보냄 */}
        <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none z-0" />
        <div className="absolute inset-0 bg-mesh opacity-70 pointer-events-none z-0" />
        {/* 블롭 — 뒤로 보냄 */}
        <div className="pointer-events-none absolute -top-16 -left-16 h-64 w-64 rounded-full bg-indigo-400/40 blur-3xl animate-blob z-0" />
        <div className="pointer-events-none absolute -top-12 right-10 h-64 w-64 rounded-full bg-emerald-400/40 blur-3xl animate-blob animation-delay-2000 z-0" />
        <div className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 h-64 w-64 rounded-full bg-sky-400/30 blur-3xl animate-blob animation-delay-4000 z-0" />

        {/* 콘텐츠 래퍼 — 앞으로 끌어올림 */}
        <div className="relative z-10 max-w-screen-xl mx-auto px-6 pt-20 pb-10">
          <div className="grid md:grid-cols-2 gap-10 items-center">
            {/* LEFT -------------------------------------------------- */}
            <div>
              <p className="text-sm font-semibold tracking-wider text-slate-500 relative z-20">
                안전한 전자서명 · 비대면 본인확인
              </p>

              {/* 각 줄이 한 줄로(랩 금지) + 텍스트를 최상위로 */}
              <h1 className="mt-3 font-extrabold tracking-tight leading-tight relative z-20">
                <span className="block text-4xl md:text-6xl lg:text-7xl bg-gradient-to-r from-indigo-600 to-emerald-600 bg-clip-text text-transparent whitespace-nowrap">
                  서명이 필요한 모든 순간,
                </span>
                <span className="block text-4xl md:text-6xl lg:text-7xl text-slate-900 whitespace-nowrap">
                  AI 기반 자필 서명 진위 판별
                </span>
              </h1>

              <p className="mt-5 text-lg text-slate-600 max-w-[56ch] relative z-20">
                이미지 또는 실시간 필기 패턴으로 서명의 진위를 정확하게 판별합니다.
                등록만 해두면 사진 한 장으로도 신속하게 검증할 수 있어요.
              </p>

              <div className="mt-8 flex items-center gap-3 relative z-20">
                <Link
                  to="/photo"
                  className="rounded-xl bg-slate-900 text-white px-6 py-3 hover:bg-slate-800"
                >
                  Verify by Photo 시작
                </Link>
                <Link
                  to="/enroll"
                  className="rounded-xl border border-slate-300 bg-white px-6 py-3 hover:bg-slate-50"
                >
                  첫 등록(Enroll)
                </Link>
              </div>

              <div className="mt-3 text-xs text-slate-500 relative z-20">
                지원 포맷:&nbsp;
                <span className="font-medium text-slate-700">
                  PNG · JPG · JPEG · PDF(스냅샷)
                </span>
              </div>

              <div className="mt-6 flex flex-wrap gap-3 text-sm text-slate-600 relative z-20">
                <span className="inline-flex items-center gap-2 rounded-full border bg-white/70 px-3 py-1">
                  ▪︎ 모사 탐지 강화(행동 패턴 분석)
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border bg-white/70 px-3 py-1">
                  ▪︎ 멀티 모드(이미지 / 실시간)
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border bg-white/70 px-3 py-1">
                  ▪︎ 쉬운 통합(API 기반)
                </span>
              </div>
            </div>

            {/* RIGHT — ‘홍길동’ 사인 애니메이션(더 크게 + 아래로) */}
            <div className="relative z-10 h-[380px] md:h-[460px]">
              <div className="absolute -inset-6 rounded-3xl bg-gradient-to-br from-indigo-100 to-emerald-100 blur-2xl" />
              <SignatureHongAccurate />
            </div>
          </div>
        </div>
      </section>

      {/* === TRUST REASONS ========================================= */}
      <section className="py-14">
        <div className="max-w-screen-xl mx-auto px-6">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900">
            왜 AegisSign일까요?
          </h2>

          <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-2xl">🎯</div>
              <h3 className="mt-3 font-semibold text-slate-900">정확도 지향</h3>
              <p className="mt-2 text-sm text-slate-600">
                Siamese Network 기반 이미지 유사도와 필압·속도·곡률 등
                행동 패턴을 함께 고려합니다.
              </p>
            </div>
            <div className="rounded-xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-2xl">🖊️</div>
              <h3 className="mt-3 font-semibold text-slate-900">모사 탐지</h3>
              <p className="mt-2 text-sm text-slate-600">
                CNN+LSTM 시암즈가 필기 습관(미세 간격·속도)을 학습하여, 임베딩 L1 차이로 진위를 판별합니다.
              </p>
            </div>
            <div className="rounded-xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-2xl">⚡</div>
              <h3 className="mt-3 font-semibold text-slate-900">즉시 검증</h3>
              <p className="mt-2 text-sm text-slate-600">
                이미지 업로드는 수 초 내, 실시간 모드는 필기와 동시에
                판단 결과를 제공합니다.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* === PRODUCT MODULES ======================================= */}
      <section className="py-10">
        <div className="max-w-screen-xl mx-auto px-6">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900">
            주요 기능
          </h2>

          <div className="mt-6 grid gap-6 md:grid-cols-3">
            <div className="rounded-2xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-sm font-semibold text-emerald-600">
                Module
              </div>
              <h3 className="mt-1 text-xl font-bold">Verify by Photo</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                <li>• 사진/스캔 이미지만으로 즉시 판별</li>
                <li>• PNG/JPG/JPEG/PDF(스냅샷) 지원</li>
                <li>• 결과 스코어/사유 포함 리포트</li>
              </ul>
              <Link
                to="/photo"
                className="mt-4 inline-block rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
              >
                바로 체험 →
              </Link>
            </div>

            <div className="rounded-2xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-sm font-semibold text-emerald-600">
                Module
              </div>
              <h3 className="mt-1 text-xl font-bold">Verify in Real-Time</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                <li>• 입력 중 필기 패턴(압력/속도/곡률) 분석</li>
                <li>• 서명 UX와 자연스럽게 결합</li>
              </ul>
              <a
                href="#"
                className="mt-4 inline-block rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
              >
                문의하기 →
              </a>
            </div>

            <div className="rounded-2xl border bg-white p-6 hover:shadow-md transition">
              <div className="text-sm font-semibold text-emerald-600">
                Module
              </div>
              <h3 className="mt-1 text-xl font-bold">Enroll</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                <li>• 최초 1회 레퍼런스 서명 등록</li>
                <li>• 사용자/거래처 단위로 관리</li>
                <li>• 만료/재등록 정책 지원</li>
              </ul>
              <Link
                to="/enroll"
                className="mt-4 inline-block rounded-lg border px-3 py-2 text-sm hover:bg-slate-50"
              >
                등록하러 가기 →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* === FLOW =================================================== */}
      <section className="py-10">
        <div className="max-w-screen-xl mx-auto px-6">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900">
            사용 흐름
          </h2>

          <ol className="mt-6 grid gap-6 md:grid-cols-4">
            {[
              { n: 1, t: "Enroll", d: "신뢰할 레퍼런스 서명 등록" },
              { n: 2, t: "업로드/필기", d: "이미지 업로드 혹은 실시간 입력" },
              { n: 3, t: "판별", d: "이미지/행동 모델로 진위 판별" },
              { n: 4, t: "리포트", d: "스코어·사유·감사 로그 제공" },
            ].map((s) => (
              <li
                key={s.n}
                className="rounded-xl border bg-white p-6 hover:shadow-md transition"
              >
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-full bg-slate-900 text-white grid place-items-center text-sm">
                    {s.n}
                  </div>
                  <div className="font-semibold">{s.t}</div>
                </div>
                <p className="mt-3 text-sm text-slate-600">{s.d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* === INDUSTRIES ============================================ */}
      <section className="py-10">
        <div className="max-w-screen-xl mx-auto px-6">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900">
            적용 분야
          </h2>

          <div className="mt-6 flex flex-wrap gap-3">
            {[
              "금융/여신",
              "보험 청구",
              "공공/민원",
              "교육/자격",
              "부동산/계약",
              "전자서명 서비스",
              "내부결재/HR",
            ].map((chip) => (
              <span
                key={chip}
                className="inline-flex items-center rounded-full border bg-white px-4 py-2 text-sm text-slate-700"
              >
                {chip}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* === CTA ==================================================== */}
      <section className="py-14">
        <div className="max-w-screen-xl mx-auto px-6">
          <div className="rounded-2xl bg-gradient-to-r from-indigo-600 to-emerald-600 p-1">
            <div className="rounded-2xl bg-white p-8 flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <h3 className="text-xl font-bold">사진만으로 빠르게 시작해보세요</h3>
                <p className="text-slate-600">샘플 파일로도 바로 데모 가능합니다.</p>
              </div>
              <div className="flex gap-3">
                <Link
                  to="/photo"
                  className="inline-flex items-center rounded-xl bg-slate-900 text-white px-6 py-3 hover:bg-slate-800"
                >
                  Verify by Photo 시작 →
                </Link>
                <Link
                  to="/enroll"
                  className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-6 py-3 hover:bg-slate-50"
                >
                  첫 등록(Enroll)
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
