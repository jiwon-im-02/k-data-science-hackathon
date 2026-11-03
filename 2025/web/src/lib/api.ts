// src/lib/api.ts
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8010";

// 기존
export async function verifyByPhoto(refFile: File, probeFile: File, threshold = 0.72) {
  const fd = new FormData();
  fd.append("refs", refFile);
  fd.append("probe", probeFile);
  const res = await fetch(`${API_URL}/verify/image?threshold=${threshold}`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<{ similarities: number[]; final: number; verdict: "genuine"|"forgery" }>;
}

// 신규: 등록(Enroll)
export async function enrollByPhoto(userId: string, files: File[]) {
  const fd = new FormData();
  fd.append("user_id", userId);
  files.forEach(f => fd.append("refs", f));
  const res = await fetch(`${API_URL}/enroll/image`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<{ user_id: string; saved: number }>;
}

// 신규: 등록 상태 조회
export async function getEnrollStatus(userId: string) {
  const res = await fetch(`${API_URL}/enroll/status?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<{ user_id: string; count: number }>;
}

// 신규: 등록 샘플로 검증 (refs 안 보냄)
export async function verifyByPhotoUsingEnrolled(userId: string, probeFile: File, threshold = 0.72) {
  const fd = new FormData();
  fd.append("probe", probeFile);
  const url = `${API_URL}/verify/image?user_id=${encodeURIComponent(userId)}&threshold=${threshold}`;
  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<{ similarities: number[]; final: number; verdict: "genuine"|"forgery" }>;
}
