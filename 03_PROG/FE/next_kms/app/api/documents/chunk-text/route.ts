import { NextResponse } from "next/server";

function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
}

export async function POST(req: Request) {
  const payload = await req.json();
  const res = await fetch(`${getBackendBaseUrl()}/documents/chunk-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

