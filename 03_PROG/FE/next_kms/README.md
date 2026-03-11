학습용 RAG AI Playground의 프론트엔드(Next.js) 프로젝트입니다.

## Getting Started

### 1) 환경 변수 설정 (권장)

백엔드(FastAPI) 주소를 바꾸고 싶다면 `.env.example`을 복사해서 `.env.local`을 만드세요.

```
BACKEND_BASE_URL=http://127.0.0.1:8000
```

### 2) 개발 서버 실행

개발 서버 실행:

```bash
pnpm dev
```

브라우저에서 아래로 접속:

- `http://localhost:3000` (랜딩)
- `http://localhost:3000/chat` (최소 채팅 UI)

### 백엔드 연결

프론트는 브라우저에서 바로 백엔드를 호출하지 않고,
Next.js API 라우트가 프록시 역할을 하도록 구성했습니다.

- 프론트: `POST /api/chat/ask`
- 백엔드: `POST {BACKEND_BASE_URL}/chat/ask`

백엔드 실행 및 PDF 인입은 상위 프로젝트 README를 참고하세요.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy

학습용 로컬 실행을 우선합니다. (Kubernetes 배포는 `02_K8S` 디렉터리 참고)
