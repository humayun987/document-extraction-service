from app.extractors.base import ParsedDocument
from app.extractors.pdf_extractor import PDFExtractor
from app.extractors.docx_extractor import DOCXExtractor
from app.extractors.xlsx_extractor import XLSXExtractor
from app.extractors.csv_extractor import CSVExtractor

def extract_document(file_path: str, file_type: str) -> ParsedDocument:
    """Route document to format-specific extractor."""
    ft = file_type.lower()
    if ft == "pdf":
        return PDFExtractor.parse(file_path)
    elif ft == "docx":
        return DOCXExtractor.parse(file_path)
    elif ft == "xlsx":
        return XLSXExtractor.parse(file_path)
    elif ft == "csv":
        return CSVExtractor.parse(file_path)
    else:
        raise ValueError(f"No extractor available for file type: {file_type}")

