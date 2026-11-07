import csv
import io
from pathlib import Path
from typing import List, Any
from openpyxl.utils.cell import get_column_letter
from app.extractors.base import ParsedDocument, SpreadsheetSheet, SpreadsheetCell
from app.utils.logging import logger

class CSVExtractor:
    @staticmethod
    def parse(file_path: str) -> ParsedDocument:
        """Parse CSV file preserving row/column coordinates."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        raw_bytes = path.read_bytes()
        
        # Detect encoding
        text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
                
        if text is None:
            text = raw_bytes.decode("utf-8", errors="replace")

        # Sniff delimiter
        delimiter = ","
        try:
            sniffer = csv.Sniffer()
            sample = text[:4096]
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
        except Exception:
            pass

        parsed = ParsedDocument(file_type="csv", file_path=file_path)
        sheet_obj = SpreadsheetSheet(name="Sheet1")
        
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for row_idx, row in enumerate(reader, start=1):
            sheet_obj.max_row = row_idx
            sheet_obj.max_col = max(sheet_obj.max_col, len(row))
            row_vals = []
            for col_idx, cell_str in enumerate(row, start=1):
                clean_val = cell_str.strip()
                coord = f"{get_column_letter(col_idx)}{row_idx}"
                sheet_obj.cells[coord] = SpreadsheetCell(
                    coordinate=coord,
                    row=row_idx,
                    col=col_idx,
                    value=clean_val
                )
                row_vals.append(clean_val)
            sheet_obj.rows.append(row_vals)

        parsed.sheets["Sheet1"] = sheet_obj
        return parsed

