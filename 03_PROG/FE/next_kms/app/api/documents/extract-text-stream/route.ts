import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

const EXTRACT_TEXT_TIMEOUT_MS = 60 * 60 * 1000; // 1시간

export const maxDuration = 3600;

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

  const backendUrl = `${getBackendBaseUrl()}/documents/extract-text-stream?extract_method=${encodeURIComponent(extractMethod)}`;
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
    const msg =
      e instanceof Error && e.name === "AbortError"
        ? "텍스트 추출이 1시간 내에 완료되지 않아 중단되었습니다."
        : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 504 });
  }
  clearTimeout(timeoutId);

  if (!res.ok || !res.body) {
    const text = await res.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: res.status });
    } catch {
      return NextResponse.json({ ok: false, error: text || res.statusText }, { status: res.status });
    }
  }

  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
