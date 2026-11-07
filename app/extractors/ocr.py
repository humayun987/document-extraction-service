import io
import shutil
from typing import Optional
from PIL import Image
from app.utils.logging import logger

try:
    import pytesseract
    # Check if tesseract binary is actually found in PATH or standard location
    TESSERACT_AVAILABLE = (shutil.which("tesseract") is not None)
    if not TESSERACT_AVAILABLE:
        # Check standard Windows or Linux locations
        for candidate in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Users\Hp\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract"
        ]:
            if shutil.which(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                TESSERACT_AVAILABLE = True
                break
except ImportError:
    TESSERACT_AVAILABLE = False

def run_local_ocr_on_image(image_bytes: bytes) -> str:
    """Run Tesseract OCR on image bytes with local preprocessing."""
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")  # Convert to grayscale
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        logger.warning(f"Local Tesseract OCR execution failed: {e}")
        return ""
