import os
from langchain_community.document_loaders import (
    PyPDFLoader, DirectoryLoader, TextLoader, CSVLoader, 
    UnstructuredExcelLoader, UnstructuredWordDocumentLoader, 
    UnstructuredPowerPointLoader
)
from hwp_loader import HwpLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import StrOutputParser
import config  # 환경변수 로드

# load_dotenv() # config.py에서 처리됨

class RAGManager:
    """
    RAG(Retrieval-Augmented Generation) 챗봇의 핵심 로직을 담당하는 클래스
    데이터 로드, 분할, 벡터 저장(PostgreSQL PGVector), 검색 및 답변 생성을 수행합니다.
    (Google Gemini 버전)
    """
    
    def __init__(self, data_dir="./data"):
        self.data_dir = data_dir
        
        # Google API Key 확인
        if not os.getenv("GOOGLE_API_KEY"):
            print("경고: GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # PostgreSQL 연결 문자열 구성
        # Neon DB 정보가 개별 환경변수로 존재하는 경우 조합
        host = os.getenv("PGHOST")
        database = os.getenv("PGDATABASE")
        user = os.getenv("PGUSER") or os.getenv("PGROLE")
        password = os.getenv("PGPASSWORD")
        sslmode = os.getenv("PGSSLMODE", "require")
        
        if os.getenv("DATABASE_URL"):
             self.connection_string = os.getenv("DATABASE_URL")
        elif host and database and user:
            self.connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:5432/{database}?sslmode={sslmode}"
        else:
             print("오류: 데이터베이스 연결 정보가 부족합니다. .env 파일을 확인해주세요.")
             self.connection_string = None

        # Google 임베딩 모델 사용 (models/embedding-001) - 모델명 수정: gemini-embedding-001 -> embedding-001 or text-embedding-004
        # 보통 'models/embedding-001' 또는 'models/text-embedding-004'를 사용합니다. 여기서는 004 권장.
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        
        self.vector_store = None
        self.retriever = None
        self.chain = None
        
        # 초기화 시 벡터 스토어 연결 시도
        if self.connection_string:
            try:
                self.vector_store = PGVector(
                    embeddings=self.embeddings,
                    collection_name="gemini_documents",
                    connection=self.connection_string,
                    use_jsonb=True,
                )
                self.retriever = self.vector_store.as_retriever()
                print("Neon DB(PGVector)에 연결되었습니다.")
            except Exception as e:
                print(f"벡터 스토어 연결 초기화 중 오류: {e}")

    def load_and_index(self):
        """
        데이터 폴더의 문서를 로드하고, 분할하여 벡터 스토어(PGVector)에 저장(인덱싱)합니다.
        """
        if not self.connection_string:
            print("DB 연결 정보가 없어 작업을 수행할 수 없습니다.")
            return

        print(f"[{self.data_dir}] 에서 문서를 로드 중입니다...")
        
        all_documents = []
        
        # 지원하는 확장자별 로더 매핑
        # HWP는 olefile 필요, 나머지는 requirements.txt에 명시된 패키지 필요
        loaders_map = {
            ".pdf": PyPDFLoader,
            ".txt": lambda p: TextLoader(p, encoding='utf-8', autodetect_encoding=True),
            ".md": lambda p: TextLoader(p, encoding='utf-8', autodetect_encoding=True),
            ".py": lambda p: TextLoader(p, encoding='utf-8', autodetect_encoding=True),
            ".csv": lambda p: CSVLoader(p, encoding='utf-8'),
            ".xlsx": UnstructuredExcelLoader,
            ".xls": UnstructuredExcelLoader,
            ".docx": UnstructuredWordDocumentLoader,
            ".doc": UnstructuredWordDocumentLoader,
            ".pptx": UnstructuredPowerPointLoader,
            ".ppt": UnstructuredPowerPointLoader,
            ".hwp": HwpLoader
        }

        # 디렉토리 순회
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in loaders_map:
                    file_path = os.path.join(root, file)
                    try:
                        loader_cls = loaders_map[ext]
                        # 람다 함수인 경우(TextLoader 등 설정이 필요한 경우)와 클래스인 경우 구분
                        if callable(loader_cls) and not isinstance(loader_cls, type):
                            loader = loader_cls(file_path)
                        else:
                            loader = loader_cls(file_path)
                            
                        docs = loader.load()
                        all_documents.extend(docs)
                        print(f"로드 성공: {file}")
                    except Exception as e:
                        print(f"로드 실패 ({file}): {e}")
        
        if not all_documents:
            print("로딩된 문서가 없습니다. data 폴더에 지원하는 파일이 있는지 확인하세요.")
            return

        print(f"총 {len(all_documents)}개의 문서를 로드했습니다.")

        # 2. 텍스트 분할 (Chunking)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(all_documents)
        
        print(f"문서를 {len(splits)}개의 청크(Chunk)로 분할했습니다.")

        # 3. 벡터 스토어 저장
        print("벡터 데이터베이스(Neon DB)에 저장 중입니다...")
        try:
            self.vector_store.add_documents(splits)
            print("벡터 데이터베이스 저장이 완료되었습니다.")
        except Exception as e:
            print(f"벡터 저장 중 오류 발생: {e}")
        
    def add_text_content(self, text):
        """
        사용자가 입력한 텍스트를 바로 학습(벡터 DB 저장)합니다.
        """
        if not self.connection_string:
             print("DB 연결 정보가 없어 작업을 수행할 수 없습니다.")
             return

        from langchain_core.documents import Document
        
        print("입력된 텍스트를 학습 중입니다...")
        
        # 문서를 Document 객체로 변환
        doc = Document(page_content=text, metadata={"source": "user_input"})
        
        # 텍스트 분할
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents([doc])
        
        # 벡터 스토어에 추가
        try:
            self.vector_store.add_documents(splits)
            
            # 체인이 초기화되어 있지 않다면 초기화 (최초 실행 시)
            if not self.chain:
                 self.init_chat_chain()
                 
            print("학습이 완료되었습니다.")
        except Exception as e:
             print(f"텍스트 학습 중 오류 발생: {e}")
        
    def init_chat_chain(self):
        """
        LLM과 체인을 초기화합니다.
        벡터 스토어가 연결되어 있으면 RAG를 사용합니다.
        """
        # LLM 모델 설정 (Google Gemini) - 모델명 수정: gemini-2.5-flash
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

        # 벡터 스토어(Retriever) 확인
        if self.retriever:
            # RAG 모드 프롬프트
            template = """
            당신은 질문에 답변하는 AI 어시스턴트입니다.
            아래의 제공된 문맥(Context)을 바탕으로 질문에 대해 한국어로 답변해주세요.
            문맥에서 답을 찾을 수 없다면, 당신의 일반적인 지식을 활용하여 답변해주세요.

            문맥(Context):
            {context}

            질문(Question):
            {question}

            답변:
            """
            prompt = PromptTemplate.from_template(template)

            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

            self.chain = (
                {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )
            print("RAG 대화 체인이 준비되었습니다 (Neon DB 기반).")
        else:
            # 일반 대화 모드 프롬프트
            template = """
            당신은 유용한 AI 어시스턴트입니다.
            사용자의 질문에 대해 한국어로 친절하게 답변해주세요.

            질문(Question):
            {question}

            답변:
            """
            prompt = PromptTemplate.from_template(template)

            self.chain = (
                {"question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )
            print("일반 대화 체인이 준비되었습니다 (문서 연동 실패).")

    def ask(self, question):
        """
        질문을 받아 RAG 기반 답변을 반환합니다.
        """
        if not self.chain:
            print("시스템이 아직 초기화되지 않았습니다.")
            return "오류: 시스템 미초기화"
            
        return self.chain.invoke(question)
