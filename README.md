# RAG AI Project

## 👋 프로젝트 소개
**RAG AI**는 최신 생성형 AI 모델인 **Google Gemini**와 **RAG (Retrieval-Augmented Generation)** 기술을 결합하여 구축된 고성능 AI 질의응답 시스템입니다. 
사용자의 문서(PDF, Office, 한글 등)를 지식 베이스로 활용하여, 단순한 대화를 넘어 전문적인 정보에 기반한 정확한 답변을 제공합니다.

## 🌟 핵심 기술 스택 (Tech Stack)

### Backend (`rag_core`)
*   **Language**: Python 3.12+
*   **Framework**: FastAPI, LangChain
*   **AI Model**: Google Gemini 2.5 Flash, Text Embedding 004
*   **Vector DB**: PostgreSQL + PGVector (Neon Cloud)
*   **Infrastructure**: RESTful API Architecture

### Frontend (`chat_ui`)
*   **Framework**: React (Vite)
*   **Styling**: TailwindCSS
*   **Icons**: FontAwesome

## 📂 프로젝트 구성
이 저장소는 다음과 같이 구성되어 있습니다.

*   **`rag_core/`**: AI 백엔드 서버 및 RAG 엔진 소스코드
    *   상세한 설치 및 API 실행 방법은 [rag_core/README.md](rag_core/README.md)를 참고하세요.
*   **`chat_ui/`**: 사용자 인터페이스 웹 애플리케이션 (React)
    *   상세 가이드는 [chat_ui/README.md](chat_ui/README.md)를 참고하세요.

## 🚀 시작하기 (Quick Start)

가장 빠르게 프로젝트를 실행해보고 싶다면 백엔드 서버를 먼저 구동해보세요.

```bash
cd rag_core
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
# .env 설정 후...
python src/server.py
```

### 3. Web UI 실행 (선택사항)
브라우저에서 챗봇을 사용하려면 프론트엔드 프로젝트를 실행하세요.

```bash
cd chat_ui
npm install
npm run dev
```

## API 명세)를 확인해주세요.
