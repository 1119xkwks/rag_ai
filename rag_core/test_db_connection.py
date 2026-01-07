import sys
import os

# src 모듈을 임포트하기 위해 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database import get_connection

def test_connection():
    print("Connecting to Supabase PostgreSQL...")
    conn = None
    try:
        conn = get_connection()
        print("✅ Connection successful!")
        
        # 간단한 쿼리 실행 테스트
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"Server version: {version[0]}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        if conn:
            conn.close()
            print("Connection closed.")

if __name__ == "__main__":
    test_connection()
