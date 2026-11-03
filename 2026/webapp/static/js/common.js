/** Shared HTTP, formatting and request-draft helpers. Model scores are never stored here. */
export const $ = (selector) => document.querySelector(selector);
export const $$ = (selector) => [...document.querySelectorAll(selector)];
export const number = (value) =>
  new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(
    value ?? 0,
  );
export const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export function dateTime(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export function clockTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export function duration(value) {
  const minutes = Math.round(value || 0);
  if (minutes < 60) return `${minutes}분`;
  return `${Math.floor(minutes / 60)}시간${minutes % 60 ? ` ${minutes % 60}분` : ""}`;
}
export function errorText(error) {
  const value =
    error?.error ??
    error?.message ??
    "요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.";
  return typeof value === "string" ? value : Object.values(value).join(" ");
}
export async function api(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: controller.signal,
    });
    const data = await response.json().catch(() => {
      throw new Error(
        "서버 응답을 읽지 못했습니다. 서버 실행 상태를 확인해주세요.",
      );
    });
    if (!response.ok || data.ok === false) throw data;
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error("응답 시간이 초과되었습니다. 다시 시도해주세요.");
    if (error instanceof TypeError)
      throw new Error(
        "서버에 연결할 수 없습니다. 서버 실행 상태를 확인해주세요.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
const DRAFT_KEY = "routeone.request.v2";
export function readDraft() {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY));
    return draft && typeof draft === "object" && !Array.isArray(draft)
      ? draft
      : null;
  } catch {
    return null;
  }
}
export function saveDraft(draft) {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    throw new Error(
      "입력 정보를 보관할 수 없습니다. 브라우저의 사이트 저장소 허용 설정을 확인해주세요.",
    );
  }
}
export function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast show${error ? " error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (node.className = "toast"), 4200);
}
export function badge(value, kind) {
  return `<span class="badge ${kind}">${escapeHTML(value)}</span>`;
}
export function gateBadge(status) {
  return badge(
    status,
    { OK: "ok", WARN: "warn", BLOCK: "block" }[status] || "neutral",
  );
}
export function ownerBadge(owner) {
  return badge(owner, owner === "자차" ? "own" : "charter");
}
