"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
};

type RagContextHit = {
  id: string;
  score: number;
  payload: Record<string, unknown>;
};

type ChatLlmProvider = "openai" | "vllm" | "gemini";
type ChatEmbeddingProvider = "openai" | "vllm" | "gemini";

type ChatAskResponse = {
  ok: boolean;
  answer?: string;
  contexts?: RagContextHit[];
  error?: string;
};

type ChatModelsResponse = {
  ok: boolean;
  provider: string;
  models: string[];
  error?: string;
};

function safeString(value: unknown): string {
  if (typeof value === "string") return value;
  return "";
}

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [source, setSource] = useState("");
  const [topK, setTopK] = useState(5);
  const [llmProvider, setLlmProvider] = useState<ChatLlmProvider>("vllm");
  const [llmModel, setLlmModel] = useState("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState("");
  const [embeddingProvider, setEmbeddingProvider] =
    useState<ChatEmbeddingProvider>("gemini");
  const [isLoading, setIsLoading] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "채팅 전용 화면입니다. PDF 인입은 상단 'PDF 인입 페이지'에서 먼저 진행해 주세요.",
    },
  ]);

  const [contexts, setContexts] = useState<RagContextHit[]>([]);
  const lastAssistantIdRef = useRef<string | null>(null);

  const canSubmit = useMemo(() => {
    return question.trim().length > 0 && !isLoading;
  }, [question, isLoading]);

  useEffect(() => {
    let cancelled = false;

    async function loadModels() {
      setModelsLoading(true);
      setModelsError("");
      try {
        const res = await fetch(
          `/api/chat/models?llm_provider=${encodeURIComponent(llmProvider)}`,
        );
        const data = (await res.json()) as ChatModelsResponse;
        if (!data.ok) {
          if (!cancelled) {
            setAvailableModels([]);
            setLlmModel("");
            setModelsError(data.error || "모델 목록 조회 실패");
          }
          return;
        }
        const models = Array.isArray(data.models) ? data.models : [];
        if (!cancelled) {
          setAvailableModels(models);
          setLlmModel(models[0] || "");
        }
      } catch (e) {
        if (!cancelled) {
          setAvailableModels([]);
          setLlmModel("");
          setModelsError(`모델 목록 네트워크 오류: ${String(e)}`);
        }
      } finally {
        if (!cancelled) setModelsLoading(false);
      }
    }

    void loadModels();
    return () => {
      cancelled = true;
    };
  }, [llmProvider]);

  async function onSubmit() {
    if (!canSubmit) return;

    const q = question.trim();
    setQuestion("");

    // 1) 화면에 사용자 메시지를 먼저 추가합니다. (즉시 피드백)
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    setMessages((prev) => [...prev, userMsg]);

    // 2) 로딩 상태를 켠 뒤, 백엔드로 질문을 보냅니다.
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          top_k: topK,
          source: source.trim(),
          llm_provider: llmProvider,
          llm_model: llmModel,
          embedding_provider: embeddingProvider,
        }),
      });

      const data = (await res.json()) as ChatAskResponse;
      if (!data.ok) {
        const errText = data.error || "알 수 없는 오류가 발생했습니다.";
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `오류: ${errText}`,
        };
        lastAssistantIdRef.current = assistantMsg.id;
        setMessages((prev) => [...prev, assistantMsg]);
        setContexts([]);
        return;
      }

      // 3) 정상 응답이면, assistant 답변과 contexts(근거)를 화면에 반영합니다.
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: (data.answer || "").trim(),
      };
      lastAssistantIdRef.current = assistantMsg.id;
      setMessages((prev) => [...prev, assistantMsg]);
      setContexts(data.contexts || []);
    } catch (e) {
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `오류: 네트워크 요청에 실패했습니다. (${String(e)})`,
      };
      lastAssistantIdRef.current = assistantMsg.id;
      setMessages((prev) => [...prev, assistantMsg]);
      setContexts([]);
    } finally {
      setIsLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSubmit();
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-3">
        <section className="md:col-span-2">
          <header className="mb-4 flex items-end justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Chat</h1>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                채팅 전용 화면입니다. PDF 인입은 별도 페이지에서 진행해 주세요.
              </p>
            </div>
            <Link
              href="/ingest"
              className="inline-flex h-9 items-center rounded-xl border border-zinc-200 px-3 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
            >
              PDF 인입 페이지
            </Link>
          </header>

          <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
            {/* 메시지 리스트 */}
            <div className="max-h-[65vh] overflow-auto p-4">
              <div className="flex flex-col gap-3">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={[
                      "flex",
                      m.role === "user" ? "justify-end" : "justify-start",
                    ].join(" ")}
                  >
                    <div
                      className={[
                        "max-w-[90%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6",
                        m.role === "user"
                          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                          : "bg-zinc-100 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-50",
                      ].join(" ")}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                {isLoading ? (
                  <div className="flex justify-start">
                    <div className="rounded-2xl bg-zinc-100 px-4 py-3 text-sm text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
                      답변 생성 중...
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            {/* 입력 영역 */}
            <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    source(선택)
                  </span>
                  <input
                    className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="예: my.pdf (비우면 전체)"
                  />
                </label>

                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    top_k
                  </span>
                  <input
                    className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                    type="number"
                    min={1}
                    max={20}
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                  />
                </label>

                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    LLM provider
                  </span>
                  <select
                    className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value as ChatLlmProvider)}
                  >
                    <option value="vllm">vLLM (내부 서버)</option>
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                  </select>
                </label>

                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    LLM model
                  </span>
                  <select
                    className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600 dark:disabled:bg-zinc-900"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    disabled={modelsLoading || availableModels.length === 0}
                  >
                    {availableModels.length === 0 ? (
                      <option value="">
                        {modelsLoading ? "모델 불러오는 중..." : "모델 없음"}
                      </option>
                    ) : (
                      availableModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))
                    )}
                  </select>
                </label>

                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    Embedding provider
                  </span>
                  <select
                    className="h-10 rounded-xl border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                    value={embeddingProvider}
                    onChange={(e) =>
                      setEmbeddingProvider(e.target.value as ChatEmbeddingProvider)
                    }
                  >
                    <option value="vllm">vLLM (내부 서버)</option>
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                  </select>
                </label>
              </div>

              <div className="mt-3 flex gap-3">
                <textarea
                  className="min-h-[44px] w-full resize-y rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:focus:border-zinc-600"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="질문을 입력하세요. (Enter=전송, Shift+Enter=줄바꿈)"
                />
                <button
                  className={[
                    "h-11 shrink-0 rounded-2xl px-5 text-sm font-medium",
                    canSubmit
                      ? "bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                      : "cursor-not-allowed bg-zinc-200 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
                  ].join(" ")}
                  onClick={() => void onSubmit()}
                  disabled={!canSubmit}
                >
                  보내기
                </button>
              </div>

              <p className="mt-3 text-xs text-zinc-500">
                팁: `/ingest`에서 문서를 먼저 인입하면 source 기준 검색이 가능합니다.
              </p>
              {modelsError ? (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                  모델 목록 오류: {modelsError}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {/* 오른쪽: 근거(컨텍스트) 패널 */}
        <aside className="md:col-span-1">
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-sm font-semibold">근거(Contexts)</h2>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              최신 응답에서 사용된 검색 결과 청크를 보여줍니다.
            </p>

            <div className="mt-4 flex flex-col gap-3">
              {contexts.length === 0 ? (
                <div className="rounded-xl bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                  아직 표시할 근거가 없습니다. 질문을 보내면 여기에 검색 결과가 표시됩니다.
                </div>
              ) : (
                contexts.map((c, idx) => {
                  const text = safeString(c.payload?.["text"]);
                  const src = safeString(c.payload?.["source"]);
                  return (
                    <div
                      key={`${c.id}-${idx}`}
                      className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <div className="text-xs font-medium">
                          #{idx + 1} {src ? `· ${src}` : ""}
                        </div>
                        <div className="text-[11px] text-zinc-500">
                          score: {c.score.toFixed(4)}
                        </div>
                      </div>
                      <div className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-xs leading-5 text-zinc-700 dark:text-zinc-300">
                        {text || "(text 없음)"}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="mt-4 text-[11px] text-zinc-500">
              last assistant message id: {lastAssistantIdRef.current || "-"}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

