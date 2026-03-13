// route.ts
// 프론트에서 PDF를 업로드하면, Next.js 서버 라우트가 FastAPI `/documents/ingest`로 프록시합니다.

import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

export async function POST(req: Request) {
  const form = await req.formData();

  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { ok: false, error: "file 필드(PDF)가 필요합니다." },
      { status: 400 },
    );
  }

  const sourceName = String(form.get("source_name") || "").trim();
  const useLlmCleanup = String(form.get("use_llm_cleanup") || "false").trim();
  const cleanupProvider = String(form.get("cleanup_provider") || "").trim();
  const cleanupModel = String(form.get("cleanup_model") || "").trim();

  // FastAPI는 file은 multipart로 받고, 나머지는 Query로 받도록 구현되어 있으므로
  // 쿼리스트링으로 옮겨 전달합니다.
  const qs = new URLSearchParams();
  if (sourceName) qs.set("source_name", sourceName);
  qs.set("use_llm_cleanup", useLlmCleanup || "false");
  if (cleanupProvider) qs.set("cleanup_provider", cleanupProvider);
  if (cleanupModel) qs.set("cleanup_model", cleanupModel);

  const backendUrl = `${getBackendBaseUrl()}/documents/ingest?${qs.toString()}`;
  const body = new FormData();
  body.set("file", file);

  const res = await fetch(backendUrl, {
    method: "POST",
    body,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

