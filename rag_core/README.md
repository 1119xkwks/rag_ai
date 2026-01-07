# RAG AI Core Project

## 프로젝트 개요
이 프로젝트는 RAG (Retrieval-Augmented Generation) 기술을 활용한 AI 챗봇의 핵심 백엔드 로직을 구현한 것입니다.
터미널 기반의 테스트를 시작으로, 추후 API 서버 및 웹 UI 연동을 목표로 합니다.

## 기술 스택 (Tech Stack)
*   **Language**: Python 3.x
*   **Framework**: LangChain
*   **Vector DB**: ChromaDB
*   **LLM Integration**: **Google Gemini (gemini-1.5-flash)**
*   **PDF Processing**: PyPDFLoader

## 프로젝트 구조
```
rag_ai_core/
├── data/               # RAG에 사용할 문서(PDF 등) 저장소
├── src/                # 소스 코드 디렉토리
│   ├── main.py         # 애플리케이션 진입점 (터미널 실행용)
│   └── rag_manager.py  # RAG 핵심 로직 (Gemini 적용)
├── .gitignore          # Git 무시 설정
├── env.example         # 환경 변수 예시 파일
├── README.md           # 프로젝트 설명
└── requirements.txt    # 의존성 패키지 목록
```

## 핵심 파일 설명
### `src/rag_manager.py`
RAG의 주요 단계를 처리하는 클래스가 포함되어 있습니다.
1.  **Document Loading**: `data/` 폴더의 PDF 파일을 읽어옵니다.
2.  **Splitting**: 텍스트를 적절한 청크(Chunk) 단위로 분할합니다.
3.  **Embedding & Vector Store**: Google `embedding-001`을 사용하여 텍스트를 임베딩하고 ChromaDB에 저장합니다.
4.  **Retrieval & Generation**: 질문과 유사한 문서를 검색하고 Gemini를 통해 답변을 생성합니다.

## 🚀 상세 실행 가이드 (Execution Guide)

터미널에서 다음 순서대로 실행하여 테스트해 보실 수 있습니다.

### 1. 가상환경 생성 및 패키지 설치
Python 가상환경을 생성하여 관리자 권한 없이도 독립적인 실행 환경을 구축합니다.
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows Powershell 기준
# (Mac/Linux의 경우: source venv/bin/activate)

pip install -r requirements.txt
```

### 2. 환경 변수 설정
Gemini API 사용을 위해 키 설정이 필요합니다.

**ℹ️ Google Gemini API Key 발급 방법**
1. [Google AI Studio](https://aistudio.google.com/app/apikey)에 접속하여 로그인합니다.
2. **"Create API key"** 버튼을 클릭합니다.
3. 생성된 키를 복사합니다.

이제 발급받은 키를 프로젝트에 등록합니다:
```bash
copy env.example .env
# .env 파일을 열어 GOOGLE_API_KEY 값을 본인의 키로 변경하세요.
```

### 3. 데이터 준비
RAG가 학습할 PDF 문서를 준비합니다.
`rag_ai_core/data/` 폴더 안에 테스트하고 싶은 PDF 파일들을 넣어주세요.

### 4. 챗봇 실행
```bash
python src/main.py
```

### 5. 사용 방법
프로그램이 실행되면 메뉴가 나타납니다.
1.  **`1. 문서 데이터 로드 및 학습`**: 최초 1회 실행 필수. `data/` 폴더의 문서를 읽어 벡터 DB(`chroma_db/`)를 생성합니다.
2.  **`2. 챗봇과 대화하기`**: 학습된 데이터를 바탕으로 질문할 수 있습니다.
3.  **`3. 종료`**: 프로그램을 종료합니다.
