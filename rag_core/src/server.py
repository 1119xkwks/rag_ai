from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import config # 환경변수 설정 로드
from rag_manager import RAGManager
import os
import shutil
from typing import List

# FastAPI 앱 초기화
app = FastAPI(
    title="RAG AI Chatbot API", 
    description="Google Gemini & PGVector 기반 RAG 챗봇 API",
    version="1.0.0"
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 편의를 위해 모든 오리진 허용. 배포 시 보안 주의.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAG 매니저 인스턴스 (싱글톤처럼 사용)
rag_manager = None

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 RAGManager 초기화"""
    global rag_manager
    # data 디렉토리가 없으면 생성
    if not os.path.exists("./data"):
        os.makedirs("./data")
        
    rag_manager = RAGManager(data_dir="./data")
    print("RAG Manager initialized")
    
    # 초기 체인 설정 (가능하다면)
    if rag_manager.connection_string:
        rag_manager.init_chat_chain()

class TextTrainRequest(BaseModel):
    text: str

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str

@app.get("/")
async def root():
    return {"message": "RAG AI Chatbot API is running"}

@app.post("/train/files-scan")
async def train_files_scan():
    """
    [메뉴 1] data 폴더의 모든 지원되는 파일(PDF, TXT, Excel, Word, PPT, HWP 등)을 스캔하여 학습합니다.
    """
    if not rag_manager:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    try:
        rag_manager.load_and_index()
        rag_manager.init_chat_chain() # 인덱싱 후 체인 갱신
        return {"status": "success", "message": "All supported files in data directory indexed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/train/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """
    파일을 업로드하여 data 폴더에 저장하고 학습합니다.
    지원 포맷: PDF, TXT, MD, CSV, XLSX, DOCX, PPTX, HWP 등
    """
    if not rag_manager:
        raise HTTPException(status_code=500, detail="System not initialized")
        
    # 파일 확장자 검사 로직 제거 (모든 파일 허용 후 rag_manager에서 처리)

    file_path = os.path.join(rag_manager.data_dir, file.filename)
    
    try:
        # 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 전체 리로드 방식 차용
        rag_manager.load_and_index()
        rag_manager.init_chat_chain()
        
        return {"status": "success", "message": f"File '{file.filename}' uploaded and indexed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/train/text")
async def train_text(request: TextTrainRequest):
    """
    [메뉴 2] 텍스트를 직접 입력하여 학습합니다.
    """
    if not rag_manager:
        raise HTTPException(status_code=500, detail="System not initialized")
        
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
        
    try:
        rag_manager.add_text_content(request.text)
        return {"status": "success", "message": "Text content indexed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    [메뉴 3] 챗봇과 대화합니다.
    """
    if not rag_manager:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    # 체인 미초기화 상태 방어
    if not rag_manager.chain:
        rag_manager.init_chat_chain()
        
    try:
        answer = rag_manager.ask(request.message)
        return {"answer": answer}
    except Exception as e:
        # 시스템 미초기화 메시지 등 처리
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    # 환경변수에서 포트 읽기 (기본값 8000)
    server_port = int(os.getenv("SERVER_PORT", 8000))
    
    # 호스트 0.0.0.0으로 설정하여 외부 접근 가능하게 함
    uvicorn.run("server:app", host="0.0.0.0", port=server_port, reload=True)
