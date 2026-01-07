import os
import config
from rag_manager import RAGManager
# load_dotenv() # config.py에서 처리됨

def main():
    print("=== RAG AI 챗봇 (터미널 버전) ===")
    
    rag = RAGManager()
    
    while True:
        print("\n[메뉴]")
        print("1. 문서 데이터 로드 및 학습 (PDF -> DB)")
        print("2. 텍스트 직접 입력하여 학습")
        print("3. 챗봇과 대화하기")
        print("4. 종료")
        
        choice = input("선택하세요 > ")
        
        if choice == "1":
            rag.load_and_index()
            rag.init_chat_chain()
            
        elif choice == "2":
            text = input("학습할 내용을 입력하세요:\n")
            if text.strip():
                rag.add_text_content(text)
            else:
                print("내용이 입력되지 않았습니다.")
                
        elif choice == "3":
            # 체인이 없으면 초기화 (DB 없어도 일반 대화 가능하게)
            if not rag.chain:
                rag.init_chat_chain()
            
            print("\n질문을 입력하세요. (종료하려면 'exit' 입력)")
            while True:
                user_input = input("\n나: ")
                if user_input.lower() in ["exit", "quit", "종료"]:
                    break
                
                print("AI 생각 중...", end="\r")
                answer = rag.ask(user_input)
                print(f"AI: {answer}")
                
        elif choice == "4":
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 입력입니다.")

if __name__ == "__main__":
    main()
