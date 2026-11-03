import React from "react";

// 상단에 상수로
const MIN_ENROLL = 5;


export default function Enroll() {
  const [userId, setUserId] = React.useState("");
  const [files, setFiles] = React.useState<File[]>([]);
  const [isDragging, setIsDragging] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [message, setMessage] = React.useState<{ type: "ok" | "warn" | null; text: string } | null>(null);
  const [showStatus, setShowStatus] = React.useState(false);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const MIN_COUNT = 5;

  const handleChooseFiles = () => fileInputRef.current?.click();

  const handleFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const picked = Array.from(list);
    setFiles((prev) => [...prev, ...picked]);
    setMessage(null);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const onDragLeave = () => setIsDragging(false);

  const canSubmit = userId.trim().length > 0 && files.length >= MIN_COUNT && !isSubmitting;

  const submit = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setMessage(null);

    try {
      // 실서버가 없을 때는 프론트만 동작하도록 더미 대기
      await new Promise((r) => setTimeout(r, 900));

      // 실제 서버 연동 시:
      // const api = import.meta.env.VITE_ENROLL_API;
      // if (!api) throw new Error("VITE_ENROLL_API 미설정");
      // const fd = new FormData();
      // fd.append("userId", userId);
      // files.forEach((f) => fd.append("files", f));
      // const res = await fetch(api, { method: "POST", body: fd });
      // if (!res.ok) throw new Error("등록 실패");

      setMessage({ type: "ok", text: `기준 서명 이미지 업로드가 완료되었습니다. (총 ${files.length}장)` });
    } catch (e: any) {
      setMessage({ type: "warn", text: e?.message || "업로드 중 오류가 발생했어요." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-[70vh] bg-gradient-to-b from-white to-slate-50 text-slate-800">
      <section className="py-10">
        <div className="mx-auto max-w-xl px-6">
          <h1 className="text-center text-2xl md:text-3xl font-bold">
            첫 등록 <span className="text-slate-900">(Enroll)</span>
          </h1>
          <p className="mt-2 text-center text-sm text-slate-500">
            처음 사용하는 경우, 본인 서명을 최소 {MIN_COUNT}장 업로드해 학습 데이터를 등록하세요.
          </p>

          <div className="mt-6 rounded-2xl border bg-white p-5 shadow-sm">
            {/* 사용자 ID */}
            <label className="text-sm font-medium text-slate-700">사용자 ID</label>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="예) jiwon"
              className="mt-2 w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-slate-300"
            />

            {/* 파일 박스 */}
            <div className="mt-5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">
                  기준 서명 이미지 <span className="text-slate-500">(여러 장, 최소 {MIN_COUNT}장)</span>
                </label>
                <button
                  type="button"
                  className="text-xs text-slate-500 hover:text-slate-700"
                  onClick={() => setFiles([])}
                >
                  선택 초기화
                </button>
              </div>

              <div
                onClick={handleChooseFiles}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                className={[
                  "mt-2 grid place-items-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors cursor-pointer",
                  isDragging ? "border-slate-400 bg-slate-50" : "border-slate-200 hover:border-slate-300",
                ].join(" ")}
              >
                <svg width="28" height="28" viewBox="0 0 24 24" className="text-slate-400">
                  <path
                    fill="currentColor"
                    d="M12 16V8m0 0l-3 3m3-3l3 3M6 20h12a2 2 0 0 0 2-2v-4a5 5 0 0 0-5-5h-1a4 4 0 0 0-8 0H6a5 5 0 0 0-5 5v4a2 2 0 0 0 2 2"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fillOpacity="0"
                  />
                </svg>

                <p className="mt-2 text-sm text-slate-700">
                  <span className="font-semibold">여기를 클릭</span>하거나 파일을 드래그하세요
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  최소 {MIN_COUNT}장 필요 · 지원 포맷: PNG · JPG · JPEG · PDF(스냅샷)
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,application/pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => handleFiles(e.target.files)}
                />
              </div>

              {/* 선택 개수/리스트 */}
              <div className="mt-3">
                <div className="inline-flex items-center rounded-full border px-2 py-1 text-xs text-slate-700">
                  선택됨: {files.length}장
                </div>

                {files.length > 0 && (
                  <div className="mt-2 max-h-36 overflow-auto rounded-lg border bg-slate-50 p-2 text-xs text-slate-700">
                    {files.map((f, i) => (
                      <div key={`${f.name}-${i}`} className="truncate">
                        • {f.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 완료/안내 메시지 */}
              {message && (
                <div
                  className={[
                    "mt-3 rounded-lg px-3 py-2 text-sm",
                    message.type === "ok"
                      ? "bg-emerald-50 border border-emerald-200 text-slate-800"
                      : "bg-amber-50 border border-amber-200 text-slate-800",
                  ].join(" ")}
                >
                  {message.text}
                </div>
              )}

              {/* 액션 버튼들 */}
              <div className="mt-4 flex items-center gap-2">
                <button
                  type="button"
                  onClick={submit}
                  disabled={!canSubmit}
                  className={[
                    "rounded-lg px-4 py-2 text-sm font-medium transition",
                    canSubmit
                      ? "bg-slate-900 text-white hover:bg-slate-800"
                      : "bg-slate-200 text-slate-500 cursor-not-allowed",
                  ].join(" ")}
                >
                  {isSubmitting ? "등록 중…" : "등록하기"}
                </button>

                <button
                  type="button"
                  onClick={() => setShowStatus(true)}
                  className="rounded-lg border px-4 py-2 text-sm hover:bg-slate-50"
                >
                  등록 상태 확인
                </button>
              </div>

              {/* 주의 문구 */}
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
                본 페이지에서 업로드되는 이미지/서명정보는 (가)업무/테스트/모의시나리오 용도로
                소속자 외 유출에 주의하여 처리를 권장합니다.
              </p>
            </div>
          </div>

          {/* 이동 버튼 */}
          <div className="mt-6 text-center">
            <a
              href="/photo"
              className="inline-flex items-center rounded-xl border bg-white px-5 py-2 text-sm hover:bg-slate-50"
            >
              Verify by Photo로 이동
            </a>
          </div>
        </div>
      </section>

      {/* 등록 상태 모달 */}
      {showStatus && (
        <StatusModal
          userId={userId || "-"}
          count={files.length}
          onClose={() => setShowStatus(false)}
        />
      )}
    </main>
  );
}

function StatusModal({
  userId,
  count,
  onClose,
}: {
  userId: string;
  count: number;
  onClose: () => void;
}) {
  const isDone = count >= 5;
  const now = new Date();
  const pad = (n: number) => n.toString().padStart(2, "0");
  const ts = `${now.getFullYear()}. ${now.getMonth() + 1}. ${now.getDate()}. ${now.getHours()}:${pad(
    now.getMinutes()
  )}:${pad(now.getSeconds())}`;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="text-lg font-bold text-slate-900">등록 상태</h3>

        <div className="mt-4 space-y-2 text-slate-800">
          <div>
            <span className="text-slate-500">사용자 ID:&nbsp;</span>
            <span className="font-medium">{userId}</span>
          </div>
          <div>
            <span className="text-slate-500">등록 여부:&nbsp;</span>
            <span className="font-medium">{isDone ? "완료" : "대기"}</span>
          </div>
          <div>
            <span className="text-slate-500">등록된 샘플 수:&nbsp;</span>
            <span className="font-medium">{count}</span>
          </div>
          <div className="text-slate-500">마지막 갱신: {ts}</div>
        </div>

        <div className="mt-6 text-right">
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-white hover:bg-slate-800"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
