"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Provider = "openai" | "vllm" | "gemini";

type ChatModelsResponse = {
  ok: boolean;
  provider: string;
  models: string[];
  error?: string;
};

type DocumentIngestResponse = {
  ok: boolean;
  source?: string;
  chunks_created?: number;
  points_upserted?: number;
  llm_cleanup_used?: boolean;
  error?: string;
};

export default function IngestPage() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [useCleanup, setUseCleanup] = useState(true);
  const [cleanupProvider, setCleanupProvider] = useState<Provider>("gemini");
  const [cleanupModel, setCleanupModel] = useState("");
  const [cleanupModels, setCleanupModels] = useState<string[]>([]);
  const [cleanupModelsLoading, setCleanupModelsLoading] = useState(false);
  const [cleanupModelsError, setCleanupModelsError] = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCleanupModels() {
      if (!useCleanup) {
        setCleanupModels([]);
        setCleanupModel("");
        setCleanupModelsError("");
        setCleanupModelsLoading(false);
        return;
      }

      setCleanupModelsLoading(true);
      setCleanupModelsError("");
      try {
        const res = await fetch(
          `/api/chat/models?llm_provider=${encodeURIComponent(cleanupProvider)}`,
        );
        const data = (await res.json()) as ChatModelsResponse;
        if (!data.ok) {
          if (!cancelled) {
            setCleanupModels([]);
            setCleanupModel("");
            setCleanupModelsError(data.error || "정제 모델 목록 조회 실패");
          }
          return;
        }

        const models = Array.isArray(data.models) ? data.models : [];
        if (!cancelled) {
          setCleanupModels(models);
          setCleanupModel(models[0] || "");
        }
      } catch (e) {
        if (!cancelled) {
          setCleanupModels([]);
          setCleanupModel("");
          setCleanupModelsError(`정제 모델 목록 네트워크 오류: ${String(e)}`);
        }
      } finally {
        if (!cancelled) setCleanupModelsLoading(false);
      }
    }

    void loadCleanupModels();
    return () => {
      cancelled = true;
    };
  }, [cleanupProvider, useCleanup]);

  async function onIngestPdf() {
    if (!pdfFile || ingestLoading) return;

    setIngestLoading(true);
    setMessage("");

    try {
      const form = new FormData();
      form.set("file", pdfFile);
      form.set("source_name", sourceName.trim());
      form.set("use_llm_cleanup", String(useCleanup));
      form.set("cleanup_provider", cleanupProvider);
      form.set("cleanup_model", cleanupModel.trim());

      const res = await fetch("/api/documents/ingest", {
        method: "POST",
        body: form,
      });
      const data = (await res.json()) as DocumentIngestResponse;

      if (!data.ok) {
        setMessage(`인입 실패: ${data.error || "알 수 없는 오류"}`);
        return;
      }

      setMessage(
        `인입 완료: source=${data.source || "-"}, chunks=${data.chunks_created || 0}, points=${data.points_upserted || 0}`,
      );
    } catch (e) {
      setMessage(`인입 네트워크 오류: ${String(e)}`);
    } finally {
      setIngestLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
      <main className="mx-auto w-full max-w-4xl px-4 py-6">
        <header className="mb-4 flex items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">PDF Ingestion</h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              PDF를 업로드해 벡터 DB에 인입합니다.
            </p>
          </div>
          <Link
            href="/chat"
            className="inline-flex h-9 items-center rounded-xl border border-zinc-200 px-3 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            채팅 페이지
          </Link>
        </header>

        <section className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                PDF 파일
              </span>
              <input
                type="file"
                accept=".pdf,application/pdf"
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm file:mt-2 file:mr-2 file:rounded-md file:border-0 file:bg-zinc-100 file:px-2 file:py-1 file:text-xs dark:border-zinc-800 dark:bg-zinc-950 dark:file:bg-zinc-800"
                onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                source_name(선택)
              </span>
              <input
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                placeholder="비우면 파일명 사용"
              />
            </label>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={useCleanup}
                onChange={(e) => setUseCleanup(e.target.checked)}
              />
              <span>청킹 전 LLM 정제 사용</span>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                cleanup provider
              </span>
              <select
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                value={cleanupProvider}
                onChange={(e) => setCleanupProvider(e.target.value as Provider)}
                disabled={!useCleanup}
              >
                <option value="gemini">Gemini</option>
                <option value="vllm">vLLM (내부 서버)</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
          </div>

          <div className="mt-3 flex gap-3">
            <select
              className="h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600 dark:disabled:bg-zinc-900"
              value={cleanupModel}
              onChange={(e) => setCleanupModel(e.target.value)}
              disabled={!useCleanup || cleanupModelsLoading || cleanupModels.length === 0}
            >
              {cleanupModels.length === 0 ? (
                <option value="">
                  {cleanupModelsLoading ? "정제 모델 불러오는 중..." : "정제 모델 없음"}
                </option>
              ) : (
                cleanupModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))
              )}
            </select>
            <button
              className={[
                "h-10 shrink-0 rounded-xl px-4 text-sm font-medium",
                pdfFile && !ingestLoading
                  ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                  : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
              ].join(" ")}
              onClick={() => void onIngestPdf()}
              disabled={!pdfFile || ingestLoading}
            >
              {ingestLoading ? "인입 중..." : "PDF 인입"}
            </button>
          </div>

          {message ? (
            <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">{message}</p>
          ) : null}
          {cleanupModelsError ? (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              정제 모델 목록 오류: {cleanupModelsError}
            </p>
          ) : null}
        </section>
      </main>
    </div>
  );
}

