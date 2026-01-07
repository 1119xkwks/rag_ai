import os
import psycopg2
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def get_connection():
    """데이터베이스 연결 객체를 반환합니다.
    DATABASE_URL 환경변수가 있으면 우선 사용하고,
    없으면 개별 PG* 환경변수들을 사용합니다.
    """
    # 1. DATABASE_URL 사용
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        try:
            return psycopg2.connect(dsn)
        except psycopg2.Error as e:
            print(f"Error connecting with DATABASE_URL: {e}")
            raise e

    # 2. 개별 환경 변수 사용
    # 사용자가 PGROLE을 사용할 수도 있으므로 PGUSER와 함께 확인
    user = os.getenv("PGUSER") or os.getenv("PGROLE")
    host = os.getenv("PGHOST")
    dbname = os.getenv("PGDATABASE")
    password = os.getenv("PGPASSWORD")
    sslmode = os.getenv("PGSSLMODE", "require")

    if host and dbname and user:
        try:
            conn = psycopg2.connect(
                host=host,
                database=dbname,
                user=user,
                password=password,
                sslmode=sslmode
            )
            return conn
        except psycopg2.Error as e:
            print(f"Error connecting with env vars: {e}")
            raise e
            
    raise ValueError("데이터베이스 연결 설정이 올바르지 않습니다. (.env 파일을 확인해주세요)")
