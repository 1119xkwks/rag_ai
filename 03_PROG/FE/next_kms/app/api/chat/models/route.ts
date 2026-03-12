// route.ts
// provider별 모델 목록 조회를 백엔드(`/chat/models`)로 프록시합니다.

import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const llmProvider = (url.searchParams.get("llm_provider") || "vllm").trim();

  const backendUrl = `${getBackendBaseUrl()}/chat/models?llm_provider=${encodeURIComponent(llmProvider)}`;
  const res = await fetch(backendUrl, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

