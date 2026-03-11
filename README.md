# RAG AI Playground

로컬 환경에서 **RAG 기반 AI 시스템을 직접 구현하고 구조를 학습하기 위한 프로젝트**입니다.

이 프로젝트는 AI 플랫폼의 핵심 구성 요소인 **RAG, Vector DB, Tool Plugin, Agent 구조**를 이해하기 위해 만들어졌으며, 전체 구조는 **간소화된 Dify 스타일 아키텍처**를 참고하여 설계되었습니다.

목표는 다음과 같습니다.

* RAG (Retrieval Augmented Generation) 구현
* Vector Database 기반 문서 검색
* PDF 문서 Ingestion Pipeline 구축
* LLM Tool / Plugin 구조 구현
* Agent 기반 Tool 호출 구조 구현
* FastAPI 기반 AI Backend
* Next.js 기반 Chat UI
* Kubernetes 배포 구조 정리

본 프로젝트는 **학습 목적의 구조 이해용 프로젝트**입니다.

---

# Project Structure

```
project-root
│
├── 01_DOC
│   ├── DB
│   │   └── DDL.sql
│   │
│   └── README.md
│
├── 02_K8S
│   ├── README.md
│   └── manifests
│
└── 03_PROG
    │
    ├── BE
    │   └── rag_ai
    │
    └── FE
        └── next_kms
```

---

# Directory Description

## 01_DOC

프로젝트 관련 **설계 문서 및 사용자 정의 문서**를 관리하는 폴더입니다.

예시

* DB 스키마
* 시스템 설계 문서
* 아키텍처 다이어그램
* API 설계
* 기능 정의

```
01_DOC
 └── DB
      └── DDL.sql
```

### DB/DDL.sql

데이터베이스 테이블 생성 스크립트를 정리합니다.

예

* users
* datasets
* documents
* chunks
* chat_sessions
* chat_messages

---

## 02_K8S

Kubernetes 배포 관련 파일을 관리합니다.

```
02_K8S
 ├── README.md
 └── manifests
```

### README.md

서비스별 포트 및 NodePort 정보를 정리합니다.

예

```
Service Port

backend-api      : 8000
frontend-web     : 3000
qdrant-vector-db : 6333
postgres-db      : 5432
```

또는 NodePort 메모

```
backend-nodeport : 30080
frontend-nodeport: 30030
```

### manifests

Kubernetes 리소스 정의

예

```
deployment.yaml
service.yaml
configmap.yaml
ingress.yaml
```

---

## 03_PROG

실제 애플리케이션 코드가 위치하는 폴더입니다.

```
03_PROG
 ├── BE
 └── FE
```

---

# Backend

```
03_PROG/BE/rag_ai
```

Python 기반 AI Backend 프로젝트입니다.

주요 역할

* RAG 서비스
* PDF ingestion pipeline
* Vector DB 관리
* LLM 호출
* Tool / Agent 실행
* API 제공

## Backend Tech Stack

* Python 3.11+
* FastAPI
* Uvicorn
* Pydantic
* AsyncIO

AI / RAG

* LangChain (optional)
* LlamaIndex (optional)

Vector Database

* Qdrant

Database

* PostgreSQL

Embedding Model

* OpenAI Embedding API
* 또는 로컬 embedding 모델

LLM

* OpenAI
* 또는 로컬 LLM (Ollama)

---

## Backend Directory Example

```
rag_ai
│
├── api
│   ├── chat.py
│   ├── documents.py
│   └── dataset.py
│
├── services
│   ├── rag_service.py
│   ├── embedding_service.py
│   └── vector_service.py
│
├── tools
│   ├── base_tool.py
│   ├── math_tool.py
│   ├── time_tool.py
│   └── search_tool.py
│
├── agent
│   └── agent_executor.py
│
├── ingestion
│   ├── pdf_loader.py
│   └── chunker.py
│
└── main.py
```

---

# Frontend

```
03_PROG/FE/next_kms
```

Next.js 기반 프론트엔드 프로젝트입니다.

주요 기능

* Chat UI
* Dataset 관리
* 문서 업로드
* RAG 테스트
* Tool / Agent 실행 결과 확인

## Frontend Tech Stack

* Next.js (App Router)
* React
* TypeScript
* TailwindCSS
* React Query
* Zustand

UI

* shadcn/ui

---

## Frontend Directory Example

```
next_kms
│
├── app
│   ├── chat
│   ├── datasets
│   └── settings
│
├── components
│
├── lib
│
└── services
```

---

# Core Features

## 1. RAG System

RAG 기반 문서 검색 및 질문 응답

Flow

```
User Question
   ↓
Embedding
   ↓
Vector Search (Qdrant)
   ↓
Context 생성
   ↓
LLM Answer Generation
```

---

## 2. Document Ingestion Pipeline

PDF 문서를 Vector DB에 저장하는 처리 흐름

```
PDF Upload
   ↓
Text Extraction
   ↓
Chunk Splitting
   ↓
Embedding Generation
   ↓
Vector DB Insert
```

---

## 3. Tool Plugin System

LLM이 사용할 수 있는 Tool을 플러그인 형태로 제공합니다.

예시 Tool

* math 계산
* 현재 시간 조회
* DuckDuckGo 검색

예

```
세종대왕이 죽은지 몇년 되었지?
```

Agent 실행 흐름

```
Search Tool → 사망일 검색
Current Time Tool → 현재 날짜 확인
Math Tool → 연도 계산
```

---

## 4. Agent System

LLM이 필요에 따라 Tool을 선택하고 실행합니다.

Flow

```
User Question
   ↓
LLM 판단
   ↓
Tool 호출
   ↓
Tool 결과 반환
   ↓
LLM 답변 생성
```

---

# Vector Database

Vector 검색을 위해 전용 Vector DB를 사용합니다.

추천

* Qdrant

역할

* Document Embedding 저장
* Semantic Search 수행

---

# Database

일반 데이터 저장을 위해 PostgreSQL을 사용합니다.

예시 테이블

```
users
datasets
documents
chunks
chat_sessions
chat_messages
```

---

# Local Development

개발 환경 예시

```
Python 3.11
Node 20+
Docker
```

Backend (Windows / PowerShell 기준)

1. 백엔드 디렉터리로 이동

```
cd 03_PROG/BE/rag_ai
```

2. 가상환경(선택 사항이지만 권장) 생성 및 활성화

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. FastAPI + Uvicorn 등 의존성 설치

```
pip install -r requirements.txt
```

4. Uvicorn으로 개발 서버 실행 (포트 8000)

```
cd 03_PROG\BE\rag_ai
python -m venv venv
venv\Scripts\activate
uvicorn rag_ai.main:app --reload --port 8000
```

→ 브라우저에서 `http://localhost:8000` 또는 `http://localhost:8000/docs` 접속

Frontend

```
cd 03_PROG/FE/next_kms
npm install
npm run dev
```

---

# Future Improvements

향후 추가 가능한 기능

* Workflow UI (Node based)
* Multi-dataset RAG
* Streaming response
* Evaluation pipeline
* Prompt management
* Tool Plugin Marketplace

---

# Purpose

이 프로젝트의 목적은

* AI 플랫폼 내부 구조 이해
* RAG 시스템 직접 구현
* Agent + Tool 시스템 학습

을 통해 **AI 서비스 아키텍처를 실습 수준에서 이해하는 것**입니다.

---

# License

MIT License
