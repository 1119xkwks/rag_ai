import olefile
import zlib
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
import os

class HwpLoader(BaseLoader):
    """
    HWP (한글 5.0) 파일을 텍스트로 로드하는 로더.
    BodyText 섹션의 텍스트를 추출하며, 완벽한 포맷팅보다는 텍스트 내용 확보에 중점을 둡니다.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        if not os.path.exists(self.file_path):
            return []
            
        try:
            text = self._get_hwp_text(self.file_path)
            if not text:
                return []
            return [Document(page_content=text, metadata={"source": self.file_path})]
        except Exception as e:
            print(f"HWP 로딩 실패 ({self.file_path}): {e}")
            return []

    def _get_hwp_text(self, filename):
        try:
            f = olefile.OleFileIO(filename)
            dirs = f.listdir()
            
            # HWP 파일 구조 확인 (BodyText/SectionN)
            valid_dirs = [d for d in dirs if d[0] == "BodyText"]
            if not valid_dirs:
                return ""
                
            text_list = []
            # 섹션 순서대로 정렬
            for d in sorted(valid_dirs, key=lambda x: int(x[1].replace("Section", ""))):
                body_data = f.openstream(d).read()
                try:
                    # HWP 글 본문 압축 해제 (raw deflate)
                    unpacked = zlib.decompress(body_data, -15)
                    # UTF-16LE 디코딩
                    extracted = unpacked.decode('utf-16le', errors='ignore')
                    
                    # 텍스트 정제 (제어문자 등 제거 필요 시 추가)
                    # HWP 텍스트에는 포맷팅 정보가 섞여 있을 수 있으나, 
                    # 텍스트만 쭉 뽑아도 RAG에는 쓸만함.
                    # 일반적인 텍스트만 남기기 위해 간단한 필터링을 할 수도 있음.
                    # 여기서는 원본 그대로 반환
                    text_list.append(extracted)
                except Exception:
                    continue
            
            return "\n".join(text_list)
        except Exception:
            return ""
