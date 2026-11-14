import logging
import re
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Extracts text, preserves page and section metadata,
    and chunks content from PDF, DOCX, TXT, and HTML.
    """

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
        words = text.split()
        if not words:
            return []
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end == len(words):
                break
            start += chunk_size - overlap
        return chunks

    @classmethod
    def parse_txt(cls, content: str) -> list[dict[str, Any]]:
        chunks = cls.chunk_text(content)
        return [
            {
                "chunk_index": i,
                "content": c,
                "page_number": 1,
                "section_title": "General",
            }
            for i, c in enumerate(chunks)
        ]

    @classmethod
    def parse_html(cls, html_content: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove scripts, styles
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()

        results = []
        current_section = "Introduction"
        idx = 0

        # Group by headings if possible
        for elem in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            if elem.name in ["h1", "h2", "h3"]:
                current_section = elem.get_text().strip()
            elif elem.name in ["p", "li"]:
                text = elem.get_text().strip()
                if len(text) > 30:
                    chunks = cls.chunk_text(text, chunk_size=300, overlap=50)
                    for c in chunks:
                        results.append(
                            {
                                "chunk_index": idx,
                                "content": c,
                                "page_number": 1,
                                "section_title": current_section,
                            }
                        )
                        idx += 1

        if not results:
            full_text = soup.get_text(separator=" ").strip()
            return cls.parse_txt(full_text)

        return results

    @classmethod
    def parse_pdf(cls, file_bytes: bytes) -> list[dict[str, Any]]:
        try:
            import io

            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            results = []
            idx = 0
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    chunks = cls.chunk_text(text, chunk_size=400, overlap=80)
                    for c in chunks:
                        results.append(
                            {
                                "chunk_index": idx,
                                "content": c,
                                "page_number": page_num,
                                "section_title": f"Page {page_num}",
                            }
                        )
                        idx += 1
            return results
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return []

    @classmethod
    def parse_docx(cls, file_bytes: bytes) -> list[dict[str, Any]]:
        try:
            import io

            import docx

            doc = docx.Document(io.BytesIO(file_bytes))
            results = []
            idx = 0
            current_section = "Document Section"
            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                if p.style.name.startswith("Heading"):
                    current_section = text
                else:
                    chunks = cls.chunk_text(text, chunk_size=300, overlap=50)
                    for c in chunks:
                        results.append(
                            {
                                "chunk_index": idx,
                                "content": c,
                                "page_number": 1,
                                "section_title": current_section,
                            }
                        )
                        idx += 1
            return results
        except Exception as e:
            logger.error(f"Error parsing DOCX: {e}")
            return []


document_parser = DocumentParser()
