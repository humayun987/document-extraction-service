from pathlib import Path
from typing import Dict, Any, List
import openpyxl
from openpyxl.utils.cell import get_column_letter
from app.extractors.base import ParsedDocument, SpreadsheetSheet, SpreadsheetCell
from app.utils.logging import logger

class XLSXExtractor:
    @staticmethod
    def parse(file_path: str) -> ParsedDocument:
        """Parse all sheets of an XLSX workbook into structured cells and rows."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"XLSX file not found: {file_path}")

        parsed = ParsedDocument(file_type="xlsx", file_path=file_path)

        try:
            # Load with data_only=True to get evaluated values
            wb = openpyxl.load_workbook(file_path, data_only=True)
        except Exception as e:
            raise ValueError(f"Failed to open XLSX document: {e}")

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_obj = SpreadsheetSheet(
                name=sheet_name,
                max_row=ws.max_row or 0,
                max_col=ws.max_column or 0
            )

            # Extract row-by-row
            for row_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
                row_vals = []
                has_content = False
                for col_idx, cell in enumerate(row, start=1):
                    val = cell.value
                    if val is not None:
                        has_content = True
                    coord = f"{get_column_letter(col_idx)}{row_idx}"
                    
                    # Convert date/datetime objects to ISO string if needed
                    val_repr = val
                    if hasattr(val, "strftime"):
                        val_repr = val.strftime("%Y-%m-%d")
                        
                    sheet_obj.cells[coord] = SpreadsheetCell(
                        coordinate=coord,
                        row=row_idx,
                        col=col_idx,
                        value=val_repr,
                        data_type=cell.data_type
                    )
                    row_vals.append(val_repr)

                sheet_obj.rows.append(row_vals)

            parsed.sheets[sheet_name] = sheet_obj

        wb.close()
        return parsed

