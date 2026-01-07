# RAG AI Core Project
## 프로젝트 개요
`rag_core` 모듈은 문서 기반 질의응답 시스템의 **백엔드 엔진** 역할을 수행합니다.
다양한 문서 포맷을 처리하여 Vector DB에 인덱싱하고, Google Gemini LLM을 통해 사용자 질문에 대한 정확한 답변을 생성합니다.

이 모듈은 **FastAPI** 기반의 REST API 서버로 동작하며, 웹 프론트엔드 또는 다른 서비스와 연동될 수 있습니다.

## 📂 프로젝트 구조
```
rag_core/
├── data/               # 문서 파일 저장소 (PDF, HWP, Office 등) 
├── src/                # 소스 코드
│   ├── main.py         # CLI 실행 진입점
│   ├── server.py       # FastAPI 서버 진입점
│   ├── config.py       # 환경 설정(Profile) 로더
│   ├── rag_manager.py  # RAG 핵심 로직 (Loader, Splitter, VectorDB, Chain)
│   └── hwp_loader.py   # HWP 파일 전용 커스텀 로더
├── .env                # 환경 변수 (Dev/Default)
├── .env.prod           # 운영 환경 변수
├── README.md           # 상세 문서
└── requirements.txt    # 의존성 패키지
```

## 🛠 주요 기능 및 기술 상세
### 1. 다양한 문서 로딩 (Document Loading)
다음 포맷의 문서를 자동으로 인식하고 텍스트를 추출하여 학습합니다.
*   **텍스트류**: `.txt`, `.md`, `.py` (UTF-8 자동 감지)
*   **데이터**: `.csv`
*   **PDF**: `.pdf` (PyPDFLoader)
*   **Microsoft Office**: `.docx`, `.xlsx`, `.pptx` (Unstructured)
*   **한글**: `.hwp` (olefile 기반 자체 구현 로더)

### 2. RAG 파이프라인
*   **Embedding**: Google `text-embedding-004` 모델
*   **Vector DB**: PostgreSQL + `pgvector` (Cloud: Neon DB)
*   **LLM**: Google `gemini-2.5-flash`
*   **Prompt**: 한국어 최적화 프롬프트 템플릿 적용

### 3. REST API Server
*   **Framework**: FastAPI
*   **Docs**: Swagger UI (`/docs`), ReDoc (`/redoc`) 제공
*   **Profile**: 개발(`dev`) 및 운영(`prod`) 환경 분리 지원

---

## 🚀 상세 실행 가이드

### 1. 필수 조건
* Python 3.8+
* Google Gemini API Key
* PostgreSQL (PGVector 확장 가능) 접속 정보 (Neon DB 추천)

### 2. 설치 하기
```bash
# 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력하세요.

```ini
# Database Connection (Neon DB 예시)
PGHOST=your-db-host.neon.tech
PGDATABASE=neondb
PGUSER=your-db-user
PGPASSWORD=your-db-password
PGSSLMODE=require

# Google AI
GOOGLE_API_KEY=your_gemini_api_key

# Sever Config
SERVER_PORT=8000
```

> **환경별 설정 관리**
> * `.env`: 기본 설정 (개발용)
> * `.env.prod`: 운영용 설정
> * 실행 시 `APP_ENV=prod` 환경변수로 선택 가능

### 4. 서버 실행

**기본 실행 (개발 모드)**
```bash
python src/server.py
# 또는
uvicorn src.server:app --reload
```
서버가 시작되면 `http://localhost:8000/docs`에서 API를 테스트할 수 있습니다.

**운영 모드 실행**
```bash
# Windows PowerShell
$env:APP_ENV="prod"; python src/server.py
```

### 5. API 사용법
| Method | Endpoint | 설명 |
| :--- | :--- | :--- |
| **POST** | `/train/files-scan` | `data` 폴더의 모든 파일을 스캔하여 학습 |
| **POST** | `/train/upload-file` | 파일을 업로드하고 즉시 학습 |
| **POST** | `/train/text` | 텍스트 직접 입력 학습 (`{"text": "..."}`) |
| **POST** | `/chat` | 챗봇 대화 (`{"message": "..."}`) |


### 6. CLI 모드 실행 (테스트용)
서버 없이 터미널에서 바로 대화해볼 수 있습니다.
```bash
python src/main.py
```
