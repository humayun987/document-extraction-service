from pathlib import Path
from typing import List
import docx
from app.extractors.base import ParsedDocument, DocumentParagraph
from app.utils.logging import logger

class DOCXExtractor:
    @staticmethod
    def parse(file_path: str) -> ParsedDocument:
        """Parse DOCX into structured paragraphs and tables."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"DOCX file not found: {file_path}")

        parsed = ParsedDocument(file_type="docx", file_path=file_path)

        try:
            doc = docx.Document(file_path)
        except Exception as e:
            raise ValueError(f"Failed to open DOCX document: {e}")

        # 1. Extract paragraphs
        for idx, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            is_table_like = "\t" in text or "|" in text
            is_heading = p.style.name.startswith("Heading") if p.style else False
            parsed.paragraphs.append(
                DocumentParagraph(
                    index=idx + 1,
                    text=text,
                    is_heading=is_heading,
                    is_table_like=is_table_like
                )
            )

        # 2. Extract native tables
        for tbl_idx, table in enumerate(doc.tables):
            table_data: List[List[str]] = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                if any(row_cells):
                    table_data.append(row_cells)
            if table_data:
                parsed.raw_tables.append(table_data)

        return parsed

