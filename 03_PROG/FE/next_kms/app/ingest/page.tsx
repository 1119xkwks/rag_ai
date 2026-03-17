"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

type Provider = "openai" | "vllm" | "gemini";
type PdfExtractMethod = "pypdf" | "vision_qwen";
type ExtractPagePreview = { page: number; text: string };

type ChatModelsResponse = {
  ok: boolean;
  provider: string;
  models: string[];
  error?: string;
};

type ExtractResponse = { ok: boolean; text?: string; text_len?: number; error?: string };
type CleanupResponse = {
  ok: boolean;
  text?: string;
  text_len?: number;
  cleanup_used?: boolean;
  error?: string;
};
type ChunkResponse = {
  ok: boolean;
  mode?: string;
  chunks_count?: number;
  chunks?: string[];
  error?: string;
};
type SaveResponse = {
  ok: boolean;
  source?: string;
  collection?: string;
  points_upserted?: number;
  error?: string;
};

export default function IngestPage() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  const [extractLoading, setExtractLoading] = useState(false);
  const [extractMethod, setExtractMethod] = useState<PdfExtractMethod>("pypdf");
  const [extractPagesInput, setExtractPagesInput] = useState("");
  const [extractLogs, setExtractLogs] = useState<string[]>([]);
  const [extractPageTexts, setExtractPageTexts] = useState<ExtractPagePreview[]>([]);
  const [extractTotalPages, setExtractTotalPages] = useState(0);
  const [rawText, setRawText] = useState("");

  const [useCleanup, setUseCleanup] = useState(true);
  const [cleanupProvider, setCleanupProvider] = useState<Provider>("gemini");
  const [cleanupModel, setCleanupModel] = useState("");
  const [cleanupDelimiter, setCleanupDelimiter] = useState("###");
  const [cleanupSendAsFile, setCleanupSendAsFile] = useState(false);
  const [cleanupModels, setCleanupModels] = useState<string[]>([]);
  const [cleanupModelsLoading, setCleanupModelsLoading] = useState(false);
  const [cleanupModelsError, setCleanupModelsError] = useState("");
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupLogs, setCleanupLogs] = useState<string[]>([]);
  const [cleanedText, setCleanedText] = useState("");

  const [preferMarkdownH3, setPreferMarkdownH3] = useState(true);
  const [chunkSize, setChunkSize] = useState(2000);
  const [chunkOverlap, setChunkOverlap] = useState(200);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkMode, setChunkMode] = useState("");
  const [chunks, setChunks] = useState<string[]>([]);

  const [embeddingProvider, setEmbeddingProvider] = useState<Provider>("gemini");
  const [saveLoading, setSaveLoading] = useState(false);

  const extractAbortRef = useRef<AbortController | null>(null);

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

  const textForChunking = useMemo(() => (cleanedText || rawText).trim(), [cleanedText, rawText]);
  const resolvedSourceName = useMemo(() => {
    const trimmed = sourceName.trim();
    if (trimmed) return trimmed;
    if (pdfFile?.name?.trim()) return pdfFile.name.trim();
    return "upload";
  }, [sourceName, pdfFile]);

  useEffect(() => {
    // PDF를 고르면 source를 파일명으로 기본 채움(사용자가 이후 자유롭게 수정 가능)
    if (!pdfFile) return;
    if (!sourceName.trim()) {
      setSourceName(pdfFile.name);
    }
  }, [pdfFile, sourceName]);

  function cancelExtract() {
    extractAbortRef.current?.abort();
  }

  async function runExtract() {
    if (!pdfFile || extractLoading) return;
    extractAbortRef.current = new AbortController();
    setExtractLoading(true);
    setStatusMsg("");
    setExtractLogs([]);
    setExtractPageTexts([]);
    setExtractTotalPages(0);
    try {
      const form = new FormData();
      form.set("file", pdfFile);
      form.set("extract_method", extractMethod);
      const pagesInput = extractPagesInput.trim();
      if (pagesInput) form.set("extract_pages", pagesInput);
      const res = await fetch("/api/documents/extract-text-stream", {
        method: "POST",
        body: form,
        signal: extractAbortRef.current.signal,
      });
      if (!res.ok || !res.body) {
        const err = (await res.json()) as { ok?: boolean; error?: string };
        setStatusMsg(`1단계 실패: ${err.error || res.statusText}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";
        for (const block of lines) {
          const m = block.match(/^data:\s*(\{[\s\S]*\})/);
          if (!m) continue;
          try {
            const payload = JSON.parse(m[1]) as {
              type: string;
              message?: string;
              ok?: boolean;
              text?: string;
              text_len?: number;
              page_index?: number;
              total_pages?: number;
              error?: string;
            };
            if (payload.type === "log" && payload.message != null) {
              setExtractLogs((prev) => [...prev, payload.message ?? ""]);
            } else if (payload.type === "page") {
              const pageIndex = payload.page_index ?? 0;
              const totalPages = payload.total_pages ?? 0;
              if (totalPages > 0) setExtractTotalPages(totalPages);
              if (pageIndex > 0) {
                setExtractPageTexts((prev) => {
                  const next = [...prev];
                  const idx = next.findIndex((x) => x.page === pageIndex);
                  if (idx >= 0) {
                    next[idx] = { page: pageIndex, text: payload.text ?? "" };
                  } else {
                    next.push({ page: pageIndex, text: payload.text ?? "" });
                    next.sort((a, b) => a.page - b.page);
                  }
                  return next;
                });
              }
            } else if (payload.type === "result" && payload.ok) {
              setRawText(payload.text ?? "");
              setCleanedText("");
              setChunks([]);
              setChunkMode("");
              setStatusMsg(
                `1단계 완료: ${extractMethod} 방식으로 텍스트 ${payload.text_len ?? 0}자 추출`,
              );
            } else if (payload.type === "cancelled") {
              setStatusMsg("취소되었습니다.");
            } else if (payload.type === "error" || (payload.type === "result" && !payload.ok)) {
              setStatusMsg(`1단계 실패: ${payload.error ?? "알 수 없는 오류"}`);
            }
          } catch {
            // ignore parse error for partial chunk
          }
        }
      }
      if (buffer.trim()) {
        const m = buffer.match(/^data:\s*(\{[\s\S]*\})/);
        if (m) {
          try {
            const payload = JSON.parse(m[1]) as {
              type: string;
              message?: string;
              ok?: boolean;
              text?: string;
              text_len?: number;
              page_index?: number;
              total_pages?: number;
              error?: string;
            };
            if (payload.type === "log" && payload.message != null) {
              setExtractLogs((prev) => [...prev, payload.message ?? ""]);
            } else if (payload.type === "page") {
              const pageIndex = payload.page_index ?? 0;
              const totalPages = payload.total_pages ?? 0;
              if (totalPages > 0) setExtractTotalPages(totalPages);
              if (pageIndex > 0) {
                setExtractPageTexts((prev) => {
                  const next = [...prev];
                  const idx = next.findIndex((x) => x.page === pageIndex);
                  if (idx >= 0) {
                    next[idx] = { page: pageIndex, text: payload.text ?? "" };
                  } else {
                    next.push({ page: pageIndex, text: payload.text ?? "" });
                    next.sort((a, b) => a.page - b.page);
                  }
                  return next;
                });
              }
            } else if (payload.type === "result" && payload.ok) {
              setRawText(payload.text ?? "");
              setCleanedText("");
              setChunks([]);
              setChunkMode("");
              setStatusMsg(
                `1단계 완료: ${extractMethod} 방식으로 텍스트 ${payload.text_len ?? 0}자 추출`,
              );
            } else if (payload.type === "cancelled") {
              setStatusMsg("취소되었습니다.");
            } else if (payload.type === "error" || (payload.type === "result" && !payload.ok)) {
              setStatusMsg(`1단계 실패: ${payload.error ?? "알 수 없는 오류"}`);
            }
          } catch {
            // ignore
          }
        }
      }
    } catch (e) {
      const isAbort = e instanceof Error && e.name === "AbortError";
      setStatusMsg(isAbort ? "취소되었습니다." : `1단계 네트워크 오류: ${String(e)}`);
    } finally {
      setExtractLoading(false);
      extractAbortRef.current = null;
    }
  }

  async function runCleanup() {
    if (!rawText.trim() || cleanupLoading) return;
    setCleanupLoading(true);
    setStatusMsg("");
    setCleanupLogs([]);
    try {
      const res = await fetch("/api/documents/cleanup-text-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: rawText,
          use_cleanup: useCleanup,
          cleanup_provider: cleanupProvider,
          cleanup_model: cleanupModel,
          cleanup_delimiter: cleanupDelimiter,
          cleanup_send_as_file: cleanupSendAsFile,
        }),
      });
      if (!res.ok || !res.body) {
        const err = (await res.json()) as { ok?: boolean; error?: string };
        setStatusMsg(`3단계 실패: ${err.error || res.statusText}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const m = block.match(/^data:\s*(\{[\s\S]*\})/);
          if (!m) continue;
          try {
            const payload = JSON.parse(m[1]) as {
              type: string;
              message?: string;
              ok?: boolean;
              text?: string;
              text_len?: number;
              cleanup_used?: boolean;
              error?: string;
            };
            if (payload.type === "log" && payload.message != null) {
              setCleanupLogs((prev) => [...prev, payload.message ?? ""]);
            } else if (payload.type === "result" && payload.ok) {
              setCleanedText(payload.text || "");
              setChunks([]);
              setChunkMode("");
              setStatusMsg(
                `3단계 완료: ${payload.cleanup_used ? "LLM 정제 적용" : "정제 생략"} / ${payload.text_len || 0}자`,
              );
            } else if (payload.type === "error" || (payload.type === "result" && !payload.ok)) {
              setCleanupLogs((prev) => [
                ...prev,
                `[ERROR] ${payload.error || "알 수 없는 오류"}`,
              ]);
              setStatusMsg(`3단계 실패: ${payload.error || "알 수 없는 오류"}`);
            }
          } catch {
            // ignore parse error for partial chunk
          }
        }
      }
      if (buffer.trim()) {
        const m = buffer.match(/^data:\s*(\{[\s\S]*\})/);
        if (m) {
          try {
            const payload = JSON.parse(m[1]) as {
              type: string;
              message?: string;
              ok?: boolean;
              text?: string;
              text_len?: number;
              cleanup_used?: boolean;
              error?: string;
            };
            if (payload.type === "log" && payload.message != null) {
              setCleanupLogs((prev) => [...prev, payload.message ?? ""]);
            } else if (payload.type === "result" && payload.ok) {
              setCleanedText(payload.text || "");
              setChunks([]);
              setChunkMode("");
              setStatusMsg(
                `3단계 완료: ${payload.cleanup_used ? "LLM 정제 적용" : "정제 생략"} / ${payload.text_len || 0}자`,
              );
            } else if (payload.type === "error" || (payload.type === "result" && !payload.ok)) {
              setCleanupLogs((prev) => [
                ...prev,
                `[ERROR] ${payload.error || "알 수 없는 오류"}`,
              ]);
              setStatusMsg(`3단계 실패: ${payload.error || "알 수 없는 오류"}`);
            }
          } catch {
            // ignore
          }
        }
      }
    } catch (e) {
      setStatusMsg(`3단계 네트워크 오류: ${String(e)}`);
    } finally {
      setCleanupLoading(false);
    }
  }

  async function runChunk() {
    if (!textForChunking || chunkLoading) return;
    setChunkLoading(true);
    setStatusMsg("");
    try {
      const res = await fetch("/api/documents/chunk-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textForChunking,
          prefer_markdown_h3: preferMarkdownH3,
          chunk_delimiter: cleanupDelimiter,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
        }),
      });
      const data = (await res.json()) as ChunkResponse;
      if (!data.ok) return void setStatusMsg(`4단계 실패: ${data.error || "알 수 없는 오류"}`);
      setChunkMode(data.mode || "");
      setChunks(data.chunks || []);
      setStatusMsg(`4단계 완료: ${data.chunks_count || 0}개 청크 생성`);
    } catch (e) {
      setStatusMsg(`4단계 네트워크 오류: ${String(e)}`);
    } finally {
      setChunkLoading(false);
    }
  }

  async function runSave() {
    if (!chunks.length || saveLoading) return;
    setSaveLoading(true);
    setStatusMsg("");
    try {
      const res = await fetch("/api/documents/save-chunks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_name: resolvedSourceName,
          chunks,
          embedding_provider: embeddingProvider,
        }),
      });
      const data = (await res.json()) as SaveResponse;
      if (!data.ok) return void setStatusMsg(`5단계 실패: ${data.error || "알 수 없는 오류"}`);
      setStatusMsg(
        `5단계 완료: source=${data.source || resolvedSourceName}, points=${data.points_upserted || 0}, collection=${data.collection || "-"}`,
      );
    } catch (e) {
      setStatusMsg(`5단계 네트워크 오류: ${String(e)}`);
    } finally {
      setSaveLoading(false);
    }
  }

  function resetAll() {
    setRawText("");
    setCleanedText("");
    setChunks([]);
    setChunkMode("");
    setExtractLogs([]);
    setExtractPageTexts([]);
    setExtractTotalPages(0);
    setStatusMsg("초기화 완료");
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
      <main className="mx-auto w-full max-w-7xl px-4 py-6">
        <header className="mb-4 flex items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">PDF Ingestion (Step-by-Step)</h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              단계별 확인/수정 후 마지막에 저장합니다.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/chat"
              className="inline-flex h-9 items-center rounded-xl border border-zinc-200 px-3 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
            >
              채팅 페이지
            </Link>
            <button
              className="inline-flex h-9 items-center rounded-xl border border-zinc-200 px-3 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
              onClick={resetAll}
            >
              다시하기(초기화)
            </button>
          </div>
        </header>

        <section className="mb-4 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold">1) PDF 업로드 - 글자 얻기</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">PDF 파일</span>
              <input
                type="file"
                accept=".pdf,application/pdf"
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm file:mr-2 file:mt-2 file:rounded-md file:border-0 file:bg-zinc-100 file:px-2 file:py-1 file:text-xs dark:border-zinc-800 dark:bg-zinc-950 dark:file:bg-zinc-800"
                onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">source_name(선택)</span>
              <input
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                placeholder="비우면 파일명 사용"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">텍스트 추출 방식</span>
              <select
                value={extractMethod}
                onChange={(e) => setExtractMethod(e.target.value as PdfExtractMethod)}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              >
                <option value="pypdf">pypdf (빠름, 텍스트 레이어)</option>
                <option value="vision_qwen">vision_qwen (Qwen-VL, 이미지 OCR)</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                추출 페이지 (비우면 전체)
              </span>
              <input
                value={extractPagesInput}
                onChange={(e) => setExtractPagesInput(e.target.value)}
                placeholder="예: 1, 2, 1-5, 7-9, 15"
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              />
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                비우면 전체, 값이 있으면 단일/CSV/범위(1-5) 자동 인식
              </span>
            </label>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              className={[
                "h-10 rounded-xl px-4 text-sm font-medium",
                pdfFile && !extractLoading
                  ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                  : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
              ].join(" ")}
              onClick={() => void runExtract()}
              disabled={!pdfFile || extractLoading}
            >
              {extractLoading ? "추출 중..." : "글자 얻기 실행"}
            </button>
            {extractLoading ? (
              <button
                type="button"
                className="h-10 rounded-xl border border-zinc-300 bg-white px-4 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                onClick={cancelExtract}
              >
                취소
              </button>
            ) : null}
          </div>
          {extractLogs.length > 0 ? (
            <div className="mt-3">
              <p className="mb-1 text-xs font-medium text-zinc-600 dark:text-zinc-400">
                실시간 로그 (SSE)
              </p>
              <pre className="max-h-48 overflow-y-auto rounded-xl border border-zinc-200 bg-zinc-100 p-3 text-xs text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                {extractLogs.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </pre>
            </div>
          ) : null}
          {extractMethod === "vision_qwen" && extractPageTexts.length > 0 ? (
            <div className="mt-3">
              <p className="mb-1 text-xs font-medium text-zinc-600 dark:text-zinc-400">
                페이지별 실시간 결과 ({extractPageTexts.filter((t) => !!t.text?.trim()).length}/
                {extractTotalPages || extractPageTexts.length})
              </p>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {extractPageTexts.map((item, i) => (
                  <div key={item.page} className="rounded-xl border border-zinc-200 p-2 dark:border-zinc-800">
                    <div className="mb-1 text-[11px] text-zinc-500">page #{item.page}</div>
                    <textarea
                      value={item.text || ""}
                      onChange={(e) =>
                        setExtractPageTexts((prev) => {
                          const next = [...prev];
                          next[i] = { ...next[i], text: e.target.value };
                          return next;
                        })
                      }
                      className="min-h-[140px] w-full rounded-lg border border-zinc-200 bg-white p-2 text-xs outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="mb-4 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold">2) 추출 텍스트 확인 및 수정</h2>
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            className="mt-3 min-h-[220px] w-full rounded-xl border border-zinc-200 bg-white p-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
            placeholder="Step 1 결과 텍스트가 여기에 표시됩니다."
          />
        </section>

        <section className="mb-4 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold">3) 정제 옵션 선택 + md 텍스트 확인 (optional)</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-5">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={useCleanup} onChange={(e) => setUseCleanup(e.target.checked)} />
              <span>cleanup 사용</span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">cleanup provider</span>
              <select
                value={cleanupProvider}
                onChange={(e) => setCleanupProvider(e.target.value as Provider)}
                disabled={!useCleanup}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              >
                <option value="gemini">Gemini</option>
                <option value="vllm">vLLM</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">cleanup model</span>
              <select
                value={cleanupModel}
                onChange={(e) => setCleanupModel(e.target.value)}
                disabled={!useCleanup || cleanupModelsLoading || cleanupModels.length === 0}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600 dark:disabled:bg-zinc-900"
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
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">구분 기호</span>
              <input
                value={cleanupDelimiter}
                onChange={(e) => setCleanupDelimiter(e.target.value)}
                placeholder="###"
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              />
            </label>
          </div>
          <div className="mt-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={cleanupSendAsFile}
                onChange={(e) => setCleanupSendAsFile(e.target.checked)}
                disabled={!useCleanup || cleanupProvider !== "gemini"}
              />
              <span>Gemini cleanup 요청을 txt 첨부파일로 보내기</span>
            </label>
          </div>
          {cleanupModelsError ? (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">정제 모델 목록 오류: {cleanupModelsError}</p>
          ) : null}
          <div className="mt-3">
            <button
              className={[
                "h-10 rounded-xl px-4 text-sm font-medium",
                rawText.trim() && !cleanupLoading
                  ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                  : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
              ].join(" ")}
              onClick={() => void runCleanup()}
              disabled={!rawText.trim() || cleanupLoading}
            >
              {cleanupLoading ? "정제 중..." : "정제 실행"}
            </button>
          </div>
          {cleanupLogs.length > 0 ? (
            <div className="mt-3">
              <p className="mb-1 text-xs font-medium text-zinc-600 dark:text-zinc-400">
                정제 실시간 로그 (SSE)
              </p>
              <pre className="max-h-48 overflow-y-auto rounded-xl border border-zinc-200 bg-zinc-100 p-3 text-xs text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                {cleanupLogs.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </pre>
            </div>
          ) : null}
          <textarea
            value={cleanedText}
            onChange={(e) => setCleanedText(e.target.value)}
            className="mt-3 min-h-[220px] w-full rounded-xl border border-zinc-200 bg-white p-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
            placeholder="정제 결과(md)가 여기에 표시됩니다. 필요 시 수정하세요."
          />
        </section>

        <section className="mb-4 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold">4) 청킹 하기 + 결과 갤러리(3열)</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={preferMarkdownH3}
                onChange={(e) => setPreferMarkdownH3(e.target.checked)}
              />
              <span>구분 기호 헤더 우선 청킹</span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">chunk_size</span>
              <input
                type="number"
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">chunk_overlap</span>
              <input
                type="number"
                value={chunkOverlap}
                onChange={(e) => setChunkOverlap(Number(e.target.value))}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              />
            </label>
          </div>
          <div className="mt-3">
            <button
              className={[
                "h-10 rounded-xl px-4 text-sm font-medium",
                textForChunking && !chunkLoading
                  ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                  : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
              ].join(" ")}
              onClick={() => void runChunk()}
              disabled={!textForChunking || chunkLoading}
            >
              {chunkLoading ? "청킹 중..." : "청킹 하기"}
            </button>
          </div>
          <p className="mt-2 text-xs text-zinc-500">mode: {chunkMode || "-"} / chunks: {chunks.length}</p>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            {chunks.map((chunk, i) => (
              <div key={i} className="rounded-xl border border-zinc-200 p-2 dark:border-zinc-800">
                <div className="mb-1 text-[11px] text-zinc-500">chunk #{i + 1}</div>
                <textarea
                  value={chunk}
                  onChange={(e) =>
                    setChunks((prev) => {
                      const next = [...prev];
                      next[i] = e.target.value;
                      return next;
                    })
                  }
                  className="min-h-[180px] w-full rounded-lg border border-zinc-200 bg-white p-2 text-xs outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                />
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold">5) 다시하기 또는 Vector DB 저장</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">source_name</span>
              <input
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              />
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                저장될 source: <code>{resolvedSourceName}</code>
              </span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">embedding provider</span>
              <select
                value={embeddingProvider}
                onChange={(e) => setEmbeddingProvider(e.target.value as Provider)}
                className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
              >
                <option value="gemini">Gemini</option>
                <option value="vllm">vLLM</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
          </div>
          <div className="mt-3 flex gap-3">
            <button
              className={[
                "h-10 rounded-xl px-4 text-sm font-medium",
                chunks.length > 0 && !saveLoading
                  ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                  : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
              ].join(" ")}
              onClick={() => void runSave()}
              disabled={chunks.length === 0 || saveLoading}
            >
              {saveLoading ? "저장 중..." : "Vector DB 저장"}
            </button>
            <button
              className="h-10 rounded-xl border border-zinc-200 px-4 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
              onClick={() => void runChunk()}
              disabled={!textForChunking || chunkLoading}
            >
              청킹 다시하기
            </button>
          </div>
        </section>

        {statusMsg ? (
          <div className="mt-4 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-950">
            {statusMsg}
          </div>
        ) : null}
      </main>
    </div>
  );
}
