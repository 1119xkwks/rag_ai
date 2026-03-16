import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

const CLEANUP_TIMEOUT_MS = 60 * 60 * 1000; // 1시간

export const maxDuration = 3600;

export async function POST(req: Request) {
  const payload = await req.json();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CLEANUP_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${getBackendBaseUrl()}/documents/cleanup-text-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    const msg =
      e instanceof Error && e.name === "AbortError"
        ? "텍스트 정제가 1시간 내에 완료되지 않아 중단되었습니다."
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
