
import os
from dotenv import load_dotenv

def load_config():
    """
    APP_ENV 환경변수에 따라 적절한 .env 파일을 로드합니다.
    - default: 개발 환경 (.env, .env.dev 순서로 우선순위 고려 가능하지만 여기서는 명시적 로드)
    - prod: 운영 환경 (.env.prod)
    """
    env = os.getenv("APP_ENV", "dev")
    
    env_file = f".env.{env}"
    fallback_file = ".env"
    
    if os.path.exists(env_file):
        print(f"Loading config from {env_file}")
        load_dotenv(env_file, override=True)
    elif os.path.exists(fallback_file):
        print(f"Loading config from {fallback_file} (fallback)")
        load_dotenv(fallback_file, override=True)
    else:
        print("No .env file found. Using system environment variables.")

# 모듈 import 시 자동으로 설정 로드
load_config()
