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
  const payload = {
    question,
    top_k: body.top_k ?? 5,
    source: (body.source || "").trim(),
    llm_provider: (body.llm_provider || "").trim(),
    llm_model: (body.llm_model || "").trim(),
    embedding_provider: (body.embedding_provider || "").trim(),
  };

  // 4) FastAPI 백엔드로 요청을 전달합니다.
  const backendUrl = `${getBackendBaseUrl()}/chat/ask`;
  const res = await fetch(backendUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  // 5) 백엔드 응답을 그대로 반환합니다.
  //    (ok/answer/contexts 등 응답 포맷은 FastAPI 쪽 구현을 따릅니다.)
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

