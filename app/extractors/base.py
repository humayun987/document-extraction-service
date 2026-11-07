from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DocumentPage(BaseModel):
    page_number: int  # 1-based
    text: str = ""
    tables: List[List[List[str]]] = Field(default_factory=list)
    is_scanned: bool = False
    image_bytes: Optional[bytes] = None

class SpreadsheetCell(BaseModel):
    coordinate: str  # e.g. "A1"
    row: int         # 1-based
    col: int         # 1-based
    value: Any
    formula: Optional[str] = None
    data_type: str = "s"

class SpreadsheetSheet(BaseModel):
    name: str
    max_row: int = 0
    max_col: int = 0
    cells: Dict[str, SpreadsheetCell] = Field(default_factory=dict)
    rows: List[List[Any]] = Field(default_factory=list)

class DocumentParagraph(BaseModel):
    index: int
    text: str
    is_heading: bool = False
    is_table_like: bool = False

class ParsedDocument(BaseModel):
    file_type: str
    file_path: str
    pages: List[DocumentPage] = Field(default_factory=list)
    sheets: Dict[str, SpreadsheetSheet] = Field(default_factory=dict)
    paragraphs: List[DocumentParagraph] = Field(default_factory=list)
    raw_tables: List[List[List[str]]] = Field(default_factory=list)

    def get_full_text(self) -> str:
        if self.pages:
            return "\n\n".join(f"--- [Page {p.page_number}] ---\n{p.text}" for p in self.pages)
        if self.paragraphs:
            return "\n".join(p.text for p in self.paragraphs)
        if self.sheets:
            sheet_texts = []
            for name, sheet in self.sheets.items():
                lines = [", ".join(str(c) if c is not None else "" for c in row) for row in sheet.rows[:200]]
                sheet_texts.append(f"--- [Sheet: {name}] ---\n" + "\n".join(lines))
            return "\n\n".join(sheet_texts)
        return ""

