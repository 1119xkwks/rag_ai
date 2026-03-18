// route.ts
// 브라우저에서 백엔드로 직접 호출하면 CORS 문제가 생길 수 있어서,
// Next.js API 라우트를 “프록시”로 두고 여기서 FastAPI로 요청을 전달합니다.

import { NextResponse } from "next/server";

type ChatAskRequest = {
  question: string;
  top_k?: number;
  source?: string;
  llm_provider?: string;
  llm_model?: string;
  embedding_provider?: string;
  use_vector_db?: boolean;
  use_tools?: boolean;
};

function getBackendBaseUrl(): string {
  // 환경 변수로 백엔드 주소를 바꿀 수 있게 합니다.
  // 예: BACKEND_BASE_URL=http://127.0.0.1:8000
  //
  // 주의:
  // - Windows/Node 환경에 따라 localhost가 IPv6(::1)로 해석될 수 있습니다.
  // - FastAPI가 IPv4(127.0.0.1)로만 떠 있는 경우, ::1로 접속하면 ECONNREFUSED가 날 수 있어
  //   기본값을 127.0.0.1로 둡니다.
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

const CHAT_ASK_TIMEOUT_MS = 60 * 60 * 1000; // 1시간
export const maxDuration = 3600;

export async function POST(req: Request) {
  // 1) 클라이언트가 보낸 JSON을 파싱합니다.
  const body = (await req.json()) as ChatAskRequest;

  // 2) 최소한의 입력 검증 (프론트 실수로 빈 값이 들어오는 것을 방지)
  const question = (body.question || "").trim();
  if (!question) {
    return NextResponse.json(
      { ok: false, error: "question이 비어 있습니다." },
      { status: 400 },
    );
  }

  // 3) 백엔드로 그대로 전달할 페이로드를 구성합니다.
  const useVectorDb = body.use_vector_db ?? false;
  const payload = {
    question,
    top_k: useVectorDb ? (body.top_k ?? 5) : 5,
    source: useVectorDb ? (body.source || "").trim() : "",
    llm_provider: (body.llm_provider || "").trim(),
    llm_model: (body.llm_model || "").trim(),
    embedding_provider: useVectorDb ? (body.embedding_provider || "").trim() : "",
    use_vector_db: useVectorDb,
    use_tools: body.use_tools ?? true,
  };

  // 4) FastAPI 백엔드로 SSE 요청을 전달합니다.
  const backendUrl = `${getBackendBaseUrl()}/chat/ask-stream`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CHAT_ASK_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(backendUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    const msg =
      e instanceof Error && e.name === "AbortError"
        ? "채팅 응답이 1시간 내에 완료되지 않아 중단되었습니다."
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

