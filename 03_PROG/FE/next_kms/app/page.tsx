import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-zinc-50 font-sans text-zinc-900 dark:bg-black dark:text-zinc-50">
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-14">
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">
            RAG AI Playground
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            로컬에서 RAG(검색 증강 생성) 구조를 직접 구현·학습하기 위한 최소 UI입니다.
          </p>
        </header>

        <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-lg font-medium">바로 시작</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            먼저 PDF를 인입(`/documents/ingest`)한 뒤, 채팅에서 질문을 던지면 RAG 흐름이
            동작합니다.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              className="inline-flex h-10 items-center justify-center rounded-full bg-zinc-900 px-5 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
              href="/chat"
            >
              채팅 열기
            </Link>
            <a
              className="inline-flex h-10 items-center justify-center rounded-full border border-zinc-200 px-5 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
            >
              백엔드 API 문서(`/docs`)
            </a>
          </div>
        </section>

        <footer className="text-xs text-zinc-500">
          FE: Next.js / BE: FastAPI / Vector DB: Qdrant
        </footer>
      </main>
    </div>
  );
}
