import io
from pathlib import Path
from typing import List
import fitz  # PyMuPDF
import pdfplumber
from app.extractors.base import ParsedDocument, DocumentPage
from app.extractors.ocr import run_local_ocr_on_image, TESSERACT_AVAILABLE
from app.utils.logging import logger

class PDFExtractor:
    @staticmethod
    def parse(file_path: str) -> ParsedDocument:
        """Parse PDF document into structured pages with text, tables, image rendering, and OCR fallback."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        parsed = ParsedDocument(file_type="pdf", file_path=file_path)
        
        # 1. Open with PyMuPDF
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ValueError(f"Failed to open PDF document: {e}")

        if doc.is_encrypted:
            raise ValueError("Password-protected PDF documents are not supported")

        # 2. Extract with pdfplumber for table structures if available
        plumber_doc = None
        try:
            plumber_doc = pdfplumber.open(file_path)
        except Exception:
            pass

        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page = doc[page_idx]
            
            # Extract digital text
            text = page.get_text("text").strip()
            
            # Check for tables using pdfplumber
            tables: List[List[List[str]]] = []
            if plumber_doc and page_idx < len(plumber_doc.pages):
                try:
                    p_page = plumber_doc.pages[page_idx]
                    extracted_tables = p_page.extract_tables()
                    if extracted_tables:
                        for tbl in extracted_tables:
                            cleaned_tbl = [
                                [str(cell).strip() if cell is not None else "" for cell in row]
                                for row in tbl if any(c for c in row if c is not None and str(c).strip())
                            ]
                            if cleaned_tbl:
                                tables.append(cleaned_tbl)
                except Exception:
                    pass

            # Detect scanned page (few alphanumeric chars)
            alnum_chars = sum(1 for c in text if c.isalnum())
            is_scanned = (alnum_chars < 40)
            
            image_bytes = None
            if is_scanned:
                # Render page to image for multimodal vision reasoning
                try:
                    pix = page.get_pixmap(dpi=150)
                    image_bytes = pix.tobytes("png")
                    
                    # If local Tesseract is available, perform OCR
                    if TESSERACT_AVAILABLE:
                        ocr_text = run_local_ocr_on_image(image_bytes)
                        if ocr_text:
                            text = ocr_text
                except Exception as e:
                    logger.warning(f"Error rendering/OCR for page {page_num}: {e}")

            parsed.pages.append(
                DocumentPage(
                    page_number=page_num,
                    text=text,
                    tables=tables,
                    is_scanned=is_scanned,
                    image_bytes=image_bytes
                )
            )

        if plumber_doc:
            try:
                plumber_doc.close()
            except Exception:
                pass
        doc.close()

        return parsed
