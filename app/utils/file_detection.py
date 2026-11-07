import io
import zipfile
from pathlib import Path
from typing import Tuple

SUPPORTED_TYPES = {"pdf", "docx", "xlsx", "csv"}

def detect_file_type(content: bytes, filename: str) -> str:
    """
    Detect and validate file type using magic byte signatures and filename extension.
    Supports: PDF, DOCX, XLSX, CSV.
    Raises ValueError if unsupported or corrupted.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    
    # 1. Check PDF signature (%PDF-)
    if content.startswith(b"%PDF-"):
        return "pdf"
        
    # 2. Check ZIP-based formats (DOCX and XLSX)
    if content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06") or content.startswith(b"PK\x07\x08"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = set(zf.namelist())
                if "word/document.xml" in namelist:
                    return "docx"
                if "xl/workbook.xml" in namelist or any(n.startswith("xl/") for n in namelist):
                    return "xlsx"
        except zipfile.BadZipFile:
            pass
            
    # If extension is docx/xlsx and content starts with PK, trust extension if zip check passed partially
    if ext in {"docx", "xlsx"} and content.startswith(b"PK"):
        return ext

    # 3. Check CSV
    # If extension is csv or text, check if it's readable as text and contains common CSV patterns
    if ext == "csv":
        try:
            # Check text decoding
            sample = content[:4096].decode("utf-8", errors="replace")
            # If it decodes reasonably without excessive null bytes
            if "\x00" not in sample:
                return "csv"
        except Exception:
            pass

    # 4. Fallback checking with extension matching if signature matches
    if ext in SUPPORTED_TYPES:
        if ext == "pdf" and b"%PDF" in content[:1024]:
            return "pdf"
        if ext == "csv" and b"\x00" not in content[:1024]:
            return "csv"

    raise ValueError(f"Unsupported or corrupted file format. Detected extension: '{ext}'")

