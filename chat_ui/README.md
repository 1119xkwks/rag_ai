# Chat UI Project

`rag_core` 백엔드 서버와 통신하는 RAG 챗봇 시스템의 프론트엔드 프로젝트입니다.
React와 Vite를 사용하여 빠르고 현대적인 웹 애플리케이션 환경을 제공합니다.

## 🛠 기술 스택
*   **Framework**: React (Vite)
*   **Styling**: TailwindCSS
*   **Icons**: FontAwesome 5 (Free)
*   **State Management**: React Hooks

## 🚀 시작하기

### 1. 설치
```bash
cd chat_ui
npm install
```

### 2. 환경 설정
포트 번호 등을 환경변수로 제어할 수 있습니다.
*   `.env`: 공통 설정
*   `.env.dev`: 개발 모드 (`npm run dev`) 시 로드
*   `.env.prod`: 프로덕션 (`npm run prod` 또는 build) 시 로드

```ini
# .env 예시
PORT=5173
```

### 3. 실행
```bash
# 개발 서버 실행 (기본 포트: 3000 or 5173)
npm run dev
```

## 🔌 백엔드 연동
이 UI는 `http://localhost:8000`에서 실행 중인 `rag_core` API 서버와 통신하도록 설계되었습니다.
백엔드 서버가 먼저 실행되어 있는지 확인해주세요.
