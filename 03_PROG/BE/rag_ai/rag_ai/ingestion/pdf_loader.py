# pdf_loader.py
# PDF 파일에서 텍스트를 추출하는 모듈입니다.
# RAG 인입 파이프라인의 첫 단계에서 사용됩니다.

from pathlib import Path
from typing import List

from pypdf import PdfReader


def load_text_from_pdf(file_path: str | Path) -> str:
    """
    PDF 파일 경로를 받아 전체 페이지의 텍스트를 하나의 문자열로 반환합니다.

    인자:
        file_path: PDF 파일의 경로 (문자열 또는 pathlib.Path)

    반환:
        모든 페이지 텍스트를 이어 붙인 하나의 문자열.
        페이지 구분은 공백/줄바꿈으로만 되어 있으므로, 필요 시 chunker에서 잘라 씁니다.

    사용 예:
        ingestion 단계에서 업로드된 PDF를 저장한 뒤, 그 경로를 넘겨 호출합니다.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

    # pypdf로 PDF를 열어서 페이지 단위로 읽을 수 있는 리더 객체 생성
    reader = PdfReader(path)
    parts: List[str] = []

    # 각 페이지에서 텍스트를 추출해서 리스트에 넣습니다.
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)

    # 페이지별 텍스트를 줄바꿈 하나로 이어 붙여서 반환
    return "\n".join(parts)


def load_text_from_pdf_bytes(data: bytes) -> str:
    """
    PDF 바이트 데이터(예: 업로드된 파일 내용)에서 텍스트를 추출합니다.
    파일로 저장하지 않고 메모리에서 바로 처리할 때 사용합니다.

    인자:
        data: PDF 파일의 바이트 내용 (예: request.file.read())

    반환:
        전체 페이지 텍스트를 이어 붙인 문자열
    """
    from io import BytesIO

    # 바이트를 파일처럼 읽을 수 있는 객체로 감싼 뒤 PdfReader에 전달
    stream = BytesIO(data)
    reader = PdfReader(stream)
    parts: List[str] = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)

    return "\n".join(parts)
