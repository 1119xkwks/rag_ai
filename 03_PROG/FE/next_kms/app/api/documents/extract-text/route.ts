import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

/** vision_qwen 시 모델 다운로드·페이지별 OCR로 수십 분 걸릴 수 있음 */
const EXTRACT_TEXT_TIMEOUT_MS = 60 * 60 * 1000; // 1시간

export const maxDuration = 3600; // 1시간 (초). Vercel 등 플랫폼용.

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("file");
  const extractMethod = String(form.get("extract_method") || "pypdf");

  if (!(file instanceof File)) {
    return NextResponse.json(
      { ok: false, error: "file 필드(PDF)가 필요합니다." },
      { status: 400 },
    );
  }

  const body = new FormData();
  body.set("file", file);

  const backendUrl = `${getBackendBaseUrl()}/documents/extract-text?extract_method=${encodeURIComponent(extractMethod)}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), EXTRACT_TEXT_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(backendUrl, {
      method: "POST",
      body,
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    const msg = e instanceof Error && e.name === "AbortError"
      ? "텍스트 추출이 1시간 내에 완료되지 않아 중단되었습니다. (vision_qwen은 페이지당 수 분 걸릴 수 있음)"
      : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 504 });
  }
  clearTimeout(timeoutId);

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

