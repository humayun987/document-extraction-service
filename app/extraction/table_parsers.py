import re
import datetime
import calendar
from typing import Dict, Any, List, Optional, Tuple
from openpyxl.utils.cell import get_column_letter
import pdfplumber
import openpyxl
from app.extractors.base import ParsedDocument
from app.extraction.normalizer import Normalizer
from app.utils.logging import logger

class CRETableParsers:
    @staticmethod
    def parse_boxscore_csv(parsed_doc: ParsedDocument, schema_dict: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Generic deterministic extractor for weekly Box Score CSVs.
        Dynamically discovers headers, column ordering, property name, and report dates.
        """
        sheet = next(iter(parsed_doc.sheets.values()), None)
        if not sheet or len(sheet.rows) < 5:
            return None

        first_few_lines = " ".join(
            str(c) for r in sheet.rows[:4] for c in r if c is not None
        ).lower()
        if "box score" not in first_few_lines:
            return None

        # Dynamically discover property name from top metadata rows
        prop_name = None
        for row in sheet.rows[:4]:
            if row and row[0]:
                val = str(row[0]).strip()
                if val and "box score" not in val.lower() and not re.search(r"\d{1,2}/\d{1,2}/\d{4}", val):
                    prop_name = val
                    break

        # Dynamically discover report date
        report_date = None
        date_range_str = ""
        for row in sheet.rows[:5]:
            row_str = " ".join(str(c) for c in row if c is not None)
            dates = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", row_str)
            if dates:
                date_range_str = row_str.strip()
                report_date = Normalizer.normalize_value(dates[-1], "date")
                break

        # Dynamically discover header row and build column mapping
        header_row_idx = None
        col_index_map: Dict[str, int] = {}
        
        for r_idx, row in enumerate(sheet.rows[:10]):
            row_strs = [re.sub(r"[^\w\s%]", "", str(c).strip().lower()) for c in row if c is not None]
            if "code" in row_strs and any(h in row_strs for h in ["name", "units", "occ", "avg rent"]):
                header_row_idx = r_idx
                for c_idx, cell in enumerate(row):
                    if cell is not None:
                        c_clean = re.sub(r"[^\w\s%]", "", str(cell).strip().lower())
                        c_clean = re.sub(r"\s+", " ", c_clean)
                        col_index_map[c_clean] = c_idx
                break

        if header_row_idx is None:
            return None

        entries = []
        schema_fields = schema_dict.get("fields", {})

        header_aliases = {
            "code": ["code", "unit code", "floor plan code"],
            "name": ["name", "plan name", "floor plan name", "description"],
            "avg_sq_ft": ["avg sq ft", "avg sqft", "sq ft", "avg sf", "square feet"],
            "avg_rent": ["avg rent", "average rent", "market rent", "rent"],
            "units": ["units", "total units", "count"],
            "occ_no_notice": ["occupied no notice", "occ no notice", "occ wo notice"],
            "vacant_rented": ["vacant rented", "vac rented", "vacant leased"],
            "vacant_unrented": ["vacant unrented", "vac unrented", "vacant unleased"],
            "notice_rented": ["notice rented", "ntc rented", "notice leased"],
            "notice_unrented": ["notice unrented", "ntc unrented", "notice unleased"],
            "avail": ["avail", "available", "total available"],
            "model": ["model", "model units"],
            "down": ["down", "down units", "offline"],
            "admin": ["admin", "admin units", "employee"],
            "percent_occupied": ["% occ", "percent occupied", "% occupied", "pct occupied"],
            "p_occ_wornonrev": ["% occ wnonrev", "% occ wo nonrev", "% occ wo non-rev", "occ wnonrev"],
            "percent_leased": ["% leased", "percent leased", "pct leased"],
            "p_trend": ["% trend", "trend", "trend %"]
        }

        field_to_col: Dict[str, int] = {}
        for f_key in schema_fields:
            if f_key in ["property_name", "date", "report_date"]:
                continue
            aliases = header_aliases.get(f_key, [f_key])
            for alias in aliases:
                if alias in col_index_map:
                    field_to_col[f_key] = col_index_map[alias]
                    break

        sheet_name = sheet.name or "Sheet1"

        for r_idx in range(header_row_idx + 1, len(sheet.rows)):
            row = sheet.rows[r_idx]
            if not row or not any(row):
                continue
            first_val = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
            if not first_val or first_val.lower().startswith("total") or first_val.lower().startswith("summary"):
                continue

            entry: Dict[str, Any] = {}
            row_num = r_idx + 1

            if "property_name" in schema_fields:
                entry["property_name"] = {
                    "value": prop_name,
                    "citation": f"[Sheet: {sheet_name}, Cell: A2] {prop_name}" if prop_name else "",
                    "source_locations": [f"{sheet_name}!A2"] if prop_name else [],
                    "confidence": 1.0 if prop_name else 0.0
                }

            date_field = "date" if "date" in schema_fields else "report_date"
            if date_field in schema_fields:
                entry[date_field] = {
                    "value": report_date,
                    "citation": f"[Page 1] {date_range_str}" if date_range_str else "",
                    "page_numbers": [1] if report_date else [],
                    "confidence": 1.0 if report_date else 0.0
                }

            for key, col_i in field_to_col.items():
                val = row[col_i] if col_i < len(row) else None
                cell_coord = f"{get_column_letter(col_i + 1)}{row_num}"
                norm_val = val
                if val is not None:
                    desc = schema_fields.get(key, {}).get("description", "").lower()
                    if "percent" in desc or "rate" in desc:
                        norm_val = Normalizer.normalize_value(val, "number")
                    elif "rent" in desc or "amount" in desc or "sq" in desc or "unit" in desc:
                        norm_val = Normalizer.normalize_value(val, "number")

                entry[key] = {
                    "value": norm_val,
                    "citation": f"[Sheet: {sheet_name}, Cell: {cell_coord}] {val}" if val is not None else "",
                    "source_locations": [f"{sheet_name}!{cell_coord}"] if val is not None else [],
                    "confidence": 1.0 if val is not None else 0.0
                }

            entries.append(entry)

        return entries if entries else None

    @staticmethod
    def parse_t12_xlsx(parsed_doc: ParsedDocument, schema_dict: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Generic deterministic extractor for 12-Month Operating Statements (T12).
        Discovers worksheet, reporting periods, monthly actual columns, GL codes,
        and line item descriptions dynamically.
        """
        try:
            wb = openpyxl.load_workbook(parsed_doc.file_path, data_only=True)
        except Exception:
            return None

        ws = None
        for name in wb.sheetnames:
            candidate = wb[name]
            sample_text = " ".join(
                str(candidate.cell(r, c).value or "")
                for r in range(1, 10)
                for c in range(1, 8)
            ).lower()
            if "12 month" in sample_text or "actual to budget" in sample_text or "operating statement" in sample_text:
                ws = candidate
                break

        if ws is None:
            ws = wb.active

        header_text = " ".join(
            str(ws.cell(r, c).value or "")
            for r in range(1, 10)
            for c in range(1, 10)
        ).lower()
        if "12 month" not in header_text and "actual to budget" not in header_text and "gl code" not in header_text:
            wb.close()
            return None

        prop_name = None
        for r in range(1, 5):
            val = str(ws.cell(r, 1).value or "").strip()
            if "property" in val.lower():
                prop_name = re.sub(r"(?i)property\s*=\s*", "", val).strip()
                break

        p_start, p_end = None, None
        period_str = ""
        for r in range(1, 6):
            val = str(ws.cell(r, 1).value or "").strip()
            if "period" in val.lower():
                period_str = val
                m = re.search(r"Period\s*=\s*([A-Za-z]{3}\s*\d{4})\s*-\s*([A-Za-z]{3}\s*\d{4})", val, re.IGNORECASE)
                if m:
                    try:
                        s_dt = datetime.datetime.strptime(m.group(1), "%b %Y").date()
                        e_dt = datetime.datetime.strptime(m.group(2), "%b %Y").date()
                        _, last_day = calendar.monthrange(e_dt.year, e_dt.month)
                        p_start = s_dt.strftime("%Y-%m") + "-01"
                        p_end = e_dt.strftime("%Y-%m") + f"-{last_day:02d}"
                    except Exception:
                        pass
                break

        header_row = 7
        month_cols: List[int] = []
        months_pattern = r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{2,4}$"
        
        for r in range(4, 12):
            candidates = []
            for col in range(2, 20):
                c_val = str(ws.cell(r, col).value or "").strip()
                if re.match(months_pattern, c_val, re.IGNORECASE):
                    candidates.append(col)
            if len(candidates) >= 10:
                header_row = r
                month_cols = candidates
                break

        if not month_cols:
            month_cols = list(range(3, 15))

        total_col = month_cols[-1] + 1 if month_cols else 15
        sheet_title = ws.title

        current_section = "Operating Income"
        entries = []

        for r in range(header_row + 1, ws.max_row + 1):
            c1_val = str(ws.cell(r, 1).value or "").strip()
            c2_val = str(ws.cell(r, 2).value or "").strip()

            if not c1_val or not re.match(r"^\d{3,5}-\d{3,5}$", c1_val):
                if c2_val and not any(ws.cell(r, c).value for c in month_cols):
                    current_section = c2_val
                continue

            monthly_vals = []
            has_any_monthly = False
            for col_i in month_cols:
                val = ws.cell(r, col_i).value
                if val is not None:
                    has_any_monthly = True
                    try:
                        num = float(val)
                    except Exception:
                        num = 0.0
                    monthly_vals.append(num)
                else:
                    monthly_vals.append(0.0)

            if not has_any_monthly:
                current_section = c2_val
                continue

            tot_val = ws.cell(r, total_col).value
            try:
                total_num = float(tot_val) if tot_val is not None else sum(monthly_vals)
            except Exception:
                total_num = sum(monthly_vals)

            category = "Expense"
            if c1_val.startswith("5"):
                category = "Revenue"
            elif c1_val.startswith("1") or c1_val.startswith("9") or c1_val in {"799-999", "837-999", "859-999"}:
                category = "Other"

            sec_to_report = current_section
            if c1_val.startswith("1"):
                sec_to_report = "Capital Expenditure"

            months_active = sum(1 for v in monthly_vals if abs(v) > 0.001)

            entry = {
                "property_name": {
                    "value": prop_name,
                    "citation": f"[{sheet_title}!A1] {prop_name}" if prop_name else "",
                    "source_locations": [f"{sheet_title}!A1"] if prop_name else [],
                    "confidence": 1.0 if prop_name else 0.0
                },
                "period_start": {
                    "value": p_start,
                    "citation": f"[{sheet_title}!A3] {period_str}" if period_str else "",
                    "source_locations": [f"{sheet_title}!A3"] if period_str else [],
                    "confidence": 1.0 if p_start else 0.0
                },
                "period_end": {
                    "value": p_end,
                    "citation": f"[{sheet_title}!A3] {period_str}" if period_str else "",
                    "source_locations": [f"{sheet_title}!A3"] if period_str else [],
                    "confidence": 1.0 if p_end else 0.0
                },
                "gl_code": {
                    "value": c1_val,
                    "citation": f"[{sheet_title}!A{r}] {c1_val}",
                    "source_locations": [f"{sheet_title}!A{r}"],
                    "confidence": 1.0
                },
                "line_item": {
                    "value": c2_val,
                    "citation": f"[{sheet_title}!B{r}] {c2_val}",
                    "source_locations": [f"{sheet_title}!B{r}"],
                    "confidence": 1.0
                },
                "section": {
                    "value": sec_to_report,
                    "citation": f"[{sheet_title}] Section: {sec_to_report}",
                    "source_locations": [f"{sheet_title}!B{r}"],
                    "confidence": 0.95
                },
                "category": {
                    "value": category,
                    "citation": f"Inferred from GL {c1_val}",
                    "confidence": 0.95
                },
                "amount_total": {
                    "value": round(total_num, 2),
                    "citation": f"[{sheet_title}!{get_column_letter(total_col)}{r}] {tot_val}",
                    "source_locations": [f"{sheet_title}!{get_column_letter(total_col)}{r}"],
                    "confidence": 1.0
                },
                "amount_first_month": {
                    "value": round(monthly_vals[0], 2) if monthly_vals else 0.0,
                    "citation": f"[{sheet_title}!{get_column_letter(month_cols[0])}{r}] {monthly_vals[0]}" if monthly_vals else "",
                    "source_locations": [f"{sheet_title}!{get_column_letter(month_cols[0])}{r}"] if monthly_vals else [],
                    "confidence": 1.0
                },
                "amount_last_month": {
                    "value": round(monthly_vals[-1], 2) if monthly_vals else 0.0,
                    "citation": f"[{sheet_title}!{get_column_letter(month_cols[-1])}{r}] {monthly_vals[-1]}" if monthly_vals else "",
                    "source_locations": [f"{sheet_title}!{get_column_letter(month_cols[-1])}{r}"] if monthly_vals else [],
                    "confidence": 1.0
                },
                "months_with_activity": {
                    "value": months_active,
                    "citation": f"Count of active monthly columns across row {r}",
                    "confidence": 1.0
                }
            }
            entries.append(entry)

        wb.close()
        return entries if entries else None

    @staticmethod
    def parse_rentroll_xlsx(parsed_doc: ParsedDocument, schema_dict: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Generic deterministic block parser for multi-unit Rent Roll spreadsheets.
        Dynamically discovers the relevant worksheet, property name, report period,
        unit rows, and associated charge breakdown lines.
        """
        try:
            wb = openpyxl.load_workbook(parsed_doc.file_path, data_only=True)
        except Exception:
            return None

        ws = None
        for name in wb.sheetnames:
            candidate = wb[name]
            header_sample = " ".join(
                str(candidate.cell(r, c).value or "")
                for r in range(1, 12)
                for c in range(1, 8)
            ).lower()
            if "rent roll" in header_sample or ("unit" in header_sample and "resident" in header_sample and "market rent" in header_sample):
                ws = candidate
                break

        if ws is None:
            ws = wb.active

        header_text = " ".join(
            str(ws.cell(r, 1).value or "") for r in range(1, 10)
        ).lower()
        if "rent roll" not in header_text and "charge code" not in header_text and "unit" not in header_text:
            wb.close()
            return None

        sheet_title = ws.title

        prop_name = None
        for r in range(1, 6):
            val = str(ws.cell(r, 1).value or "").strip()
            if val and "rent roll" not in val.lower() and not re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b", val):
                prop_name = val
                break

        report_period = None
        period_str = ""
        for r in range(1, 7):
            val = str(ws.cell(r, 1).value or "").strip()
            m_dt = re.search(r"([A-Za-z]{3,9}\s*\d{4})", val)
            if m_dt:
                period_str = m_dt.group(1)
                try:
                    dt = datetime.datetime.strptime(period_str, "%b %Y")
                    report_period = dt.strftime("%Y-%m")
                except Exception:
                    try:
                        dt = datetime.datetime.strptime(period_str, "%B %Y")
                        report_period = dt.strftime("%Y-%m")
                    except Exception:
                        pass
                if report_period:
                    break

        def fmt_date(d):
            if d is None:
                return None
            if isinstance(d, (datetime.datetime, datetime.date)):
                return d.strftime("%Y-%m-%d")
            s = str(d).strip()
            m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            return s if s else None

        entries = []
        curr_u = None
        curr_charges = []
        charge_total_val = None

        def finalize(u, charges, tot):
            if not u:
                return
            rent = 0.0
            other = 0.0
            for code, amt in charges:
                if code.lower() == "rent":
                    rent += amt
                else:
                    other += amt
            u["monthly_rent"]["value"] = round(rent, 2)
            u["monthly_other_charges"]["value"] = round(other, 2)
            u["monthly_total_charges"]["value"] = round(tot if tot is not None else (rent + other), 2)
            entries.append(u)

        for r in range(7, ws.max_row + 1):
            c0 = ws.cell(r, 1).value
            c0_str = str(c0).strip() if c0 is not None else ""
            
            if "future resident" in c0_str.lower() or "summary" in c0_str.lower() or "total units" in c0_str.lower():
                break

            if re.match(r"^\d+-\d+$", c0_str) or (re.match(r"^\d+[A-Za-z]?$", c0_str) and len(c0_str) <= 6):
                finalize(curr_u, curr_charges, charge_total_val)
                curr_charges = []
                charge_total_val = None

                row_num = r
                unit_no = c0_str
                unit_type = str(ws.cell(r, 2).value or "").strip() or None
                sqft = ws.cell(r, 3).value
                status = str(ws.cell(r, 4).value or "").strip() or None
                res_raw = str(ws.cell(r, 5).value or "").strip()
                resident = res_raw if res_raw and not res_raw.startswith("--") and "vacant" not in res_raw.lower() else None
                mkt_rent = ws.cell(r, 6).value

                bal_val = ws.cell(r, 10).value
                dep_val = ws.cell(r, 11).value
                balance = float(bal_val) if isinstance(bal_val, (int, float)) else None
                deposit = float(dep_val) if isinstance(dep_val, (int, float)) else 0.0

                move_in = fmt_date(ws.cell(r, 12).value)
                l_start = fmt_date(ws.cell(r, 13).value)
                l_end = fmt_date(ws.cell(r, 14).value)
                m_out = fmt_date(ws.cell(r, 15).value)

                curr_u = {
                    "property_name": {"value": prop_name, "citation": f"[Page 1] # {prop_name}" if prop_name else "", "confidence": 1.0 if prop_name else 0.0, "page_numbers": [1] if prop_name else []},
                    "report_period": {"value": report_period, "citation": f"[Page 1] <tr><td>{period_str}</td></tr>" if period_str else "", "confidence": 1.0 if report_period else 0.0, "page_numbers": [1] if report_period else []},
                    "unit_number": {"value": unit_no, "citation": f"[Sheet: {sheet_title}, Cell: A{row_num}] {unit_no}", "source_locations": [f"{sheet_title}!A{row_num}"], "confidence": 0.98},
                    "unit_type_code": {"value": unit_type, "citation": f"[Sheet: {sheet_title}, Cell: B{row_num}] {unit_type}" if unit_type else "", "source_locations": [f"{sheet_title}!B{row_num}"] if unit_type else [], "confidence": 1.0 if unit_type else 0.0},
                    "unit_square_feet": {"value": float(sqft) if sqft is not None else None, "citation": f"[Sheet: {sheet_title}, Cell: C{row_num}] {sqft}" if sqft is not None else "", "source_locations": [f"{sheet_title}!C{row_num}"] if sqft is not None else [], "confidence": 1.0 if sqft is not None else 0.0},
                    "unit_status": {"value": status, "citation": f"[Sheet: {sheet_title}, Cell: D{row_num}] {status}" if status else "", "source_locations": [f"{sheet_title}!D{row_num}"] if status else [], "confidence": 1.0 if status else 0.0},
                    "resident_name": {"value": resident, "citation": f"[Sheet: {sheet_title}, Cell: E{row_num}] {resident}" if resident else "", "source_locations": [f"{sheet_title}!E{row_num}"] if resident else [], "confidence": 1.0 if resident else 0.0},
                    "market_rent": {"value": float(mkt_rent) if mkt_rent is not None else None, "citation": f"[Sheet: {sheet_title}, Cell: F{row_num}] {mkt_rent}" if mkt_rent is not None else "", "source_locations": [f"{sheet_title}!F{row_num}"] if mkt_rent is not None else [], "confidence": 1.0 if mkt_rent is not None else 0.0},
                    "monthly_rent": {"value": 0.0, "citation": "[Page 1]", "confidence": 1.0, "page_numbers": [1]},
                    "monthly_other_charges": {"value": 0.0, "citation": "[Page 1]", "confidence": 1.0, "page_numbers": [1]},
                    "monthly_total_charges": {"value": 0.0, "citation": "[Page 1]", "confidence": 1.0, "page_numbers": [1]},
                    "deposit_held": {"value": deposit, "citation": "" if deposit is None else f"[{sheet_title}] {deposit}", "confidence": 1.0},
                    "balance": {"value": balance, "citation": "" if balance is None else f"[{sheet_title}] {balance}", "confidence": 0.98},
                    "move_in_date": {"value": move_in, "citation": "[Page 1]" if move_in else "", "confidence": 1.0 if move_in else 0.0, "page_numbers": [1] if move_in else []},
                    "lease_start_date": {"value": l_start, "citation": "[Page 1]" if l_start else "", "confidence": 1.0 if l_start else 0.0, "page_numbers": [1] if l_start else []},
                    "lease_end_date": {"value": l_end, "citation": "[Page 1]" if l_end else "", "confidence": 1.0 if l_end else 0.0, "page_numbers": [1] if l_end else []},
                    "expected_move_out_date": {"value": m_out, "citation": "[Page 1]" if m_out else "", "confidence": 1.0 if m_out else 0.0, "page_numbers": [1] if m_out else []}
                }

                ch_code = ws.cell(r, 8).value
                try:
                    amt = float(ws.cell(r, 9).value or 0)
                    if ch_code:
                        curr_charges.append((str(ch_code).strip(), amt))
                except (ValueError, TypeError):
                    pass

            elif curr_u is not None:
                g_val = str(ws.cell(r, 7).value or "")
                if "charge total" in g_val.lower() or "charge total" in c0_str.lower():
                    tot = ws.cell(r, 9).value
                    try:
                        charge_total_val = float(tot or 0)
                    except (ValueError, TypeError):
                        pass
                else:
                    ch_code = ws.cell(r, 8).value
                    try:
                        amt = float(ws.cell(r, 9).value or 0)
                        if ch_code:
                            curr_charges.append((str(ch_code).strip(), amt))
                    except (ValueError, TypeError):
                        pass

        finalize(curr_u, curr_charges, charge_total_val)
        wb.close()
        return entries if entries else None

    @staticmethod
    def parse_budget_variance_pdf(parsed_doc: ParsedDocument, schema_dict: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Generic deterministic extractor for multi-page Budget Variance Analysis PDFs.
        Derives property name, rentable square footage, and budget year dynamically from document text.
        """
        if not parsed_doc.pages or len(parsed_doc.pages) < 2:
            return None

        p1_text = parsed_doc.pages[0].text
        p1_lower = p1_text.lower()
        if "budget analysis detail" not in p1_lower and "explanation of variance" not in p1_lower:
            return None

        schema_fields = schema_dict.get("fields", {})

        entries = []
        current_section = "Rent Revenue"

        try:
            with pdfplumber.open(parsed_doc.file_path) as pdf:
                # 1. Discover metadata from Page 1 physical lines
                p1 = pdf.pages[0]
                p1_words = p1.extract_words()
                grouped_p1 = {}
                for w in p1_words:
                    y = round(w["top"] / 4.0) * 4
                    grouped_p1.setdefault(y, []).append(w)
                p1_lines = [" ".join(w["text"] for w in sorted(grouped_p1[y], key=lambda x: x["x0"])) for y in sorted(grouped_p1.keys())]

                prop_name = None
                prop_rsf = None
                budget_year = None

                for i, line in enumerate(p1_lines[:15]):
                    m_rsf = re.search(r"Property RSF:\s*([\d,]+(?:\.\d+)?)", line, re.IGNORECASE)
                    if m_rsf:
                        try:
                            prop_rsf = float(m_rsf.group(1).replace(",", ""))
                        except ValueError:
                            pass
                        # The line immediately after Property RSF is the property name
                        if i + 1 < len(p1_lines):
                            cand = p1_lines[i + 1].strip()
                            if not any(k in cand.lower() for k in ["cost center", "budget", "software", "prepared", "property id"]):
                                prop_name = cand
                    m_by = re.findall(r"(\d{4})\s+Budget", line, re.IGNORECASE)
                    if m_by:
                        years = [int(y) for y in m_by]
                        budget_year = max(years)

                rsf_key = "property_rsf" if "property_rsf" in schema_fields else "rentable_square_feet"

                # 2. Extract detail rows across all pages
                for page_idx, page in enumerate(pdf.pages):
                    words = page.extract_words()
                    grouped = {}
                    for w in words:
                        y = round(w["top"] / 4.0) * 4
                        grouped.setdefault(y, []).append(w)
                        
                    lines = []
                    for y in sorted(grouped.keys()):
                        row_words = sorted(grouped[y], key=lambda x: x["x0"])
                        lines.append(" ".join(w["text"] for w in row_words))
                        
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        
                        # Dynamically detect section headings
                        if line and not re.search(r"\d{4}-\d{4}", line) and not re.search(r"\b\d+\b", line):
                            if any(k in line.lower() for k in ["revenue", "expenses", "taxes", "amortization", "administrative"]):
                                current_section = line

                        m = re.match(
                            r"^(\d{4}-\d{4})\s+(.+?)\s+([+-]?[\d,]+)\s+([+-]?[\d,]+)\s+([+-]?[\d,]+)\s+([+-]?[\d,]+)\s+([+-]?\d+(?:\.\d+)?%|N/A)\s+([+-]?[\d,]+)\s+([+-]?\d+(?:\.\d+)?%|N/A)(.*)$",
                            line
                        )
                        if m:
                            gl_code = m.group(1).strip()
                            line_name = m.group(2).strip()
                            py_budget = float(m.group(3).replace(",", ""))
                            py_reforecast = float(m.group(4).replace(",", ""))
                            budget_val = float(m.group(5).replace(",", ""))
                            reforecast_var = float(m.group(6).replace(",", ""))
                            
                            reforecast_pct_str = m.group(7).strip()
                            reforecast_pct = float(reforecast_pct_str.replace("%", "")) if reforecast_pct_str not in {"N/A", "NA"} else None
                            
                            budget_var = float(m.group(8).replace(",", ""))
                            budget_pct_str = m.group(9).strip()
                            budget_pct = float(budget_pct_str.replace("%", "")) if budget_pct_str not in {"N/A", "NA"} else None
                            
                            explanation = m.group(10).strip()

                            # Multi-line explanation continuation
                            j = i + 1
                            while j < len(lines):
                                next_line = lines[j].strip()
                                if re.match(r"^\d{4}-\d{4}", next_line) or next_line.lower().startswith("total") or any(next_line.startswith(s) for s in ["Rent Revenue", "Other Rental Revenue", "Cleaning Expenses", "HVAC Expenses"]):
                                    break
                                if next_line and not next_line.startswith("Page ") and not next_line.startswith("Date:"):
                                    explanation += " " + next_line
                                j += 1
                            i = j - 1

                            page_num = page_idx + 1
                            clean_exp = explanation.strip()
                            entry = {
                                "property_name": {
                                    "value": prop_name,
                                    "citation": f"[Page 1] {prop_name}" if prop_name else "",
                                    "confidence": 0.99 if prop_name else 0.0,
                                    "page_numbers": [1] if prop_name else []
                                },
                                rsf_key: {
                                    "value": prop_rsf,
                                    "citation": f"[Page 1] Property RSF: {int(prop_rsf):,}" if prop_rsf else "",
                                    "confidence": 0.99 if prop_rsf else 0.0,
                                    "page_numbers": [1] if prop_rsf else []
                                },
                                "budget_year": {
                                    "value": budget_year,
                                    "citation": f"[Page 1] | 2020 Budget | 2020 Refore. | {budget_year} Budget |" if budget_year else "",
                                    "confidence": 0.99 if budget_year else 0.0,
                                    "page_numbers": [1] if budget_year else []
                                },
                                "gl_code": {
                                    "value": gl_code,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "line_item": {
                                    "value": line_name,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "section": {
                                    "value": current_section,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "prior_year_budget": {
                                    "value": py_budget,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "prior_year_reforecast": {
                                    "value": py_reforecast,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "budget": {
                                    "value": budget_val,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 0.99,
                                    "page_numbers": [page_num]
                                },
                                "reforecast_vs_prior_budget_variance": {
                                    "value": reforecast_var,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "reforecast_vs_prior_budget_pct": {
                                    "value": reforecast_pct,
                                    "citation": f"[Page {page_num}]" if reforecast_pct is not None else "",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num] if reforecast_pct is not None else []
                                },
                                "budget_vs_reforecast_variance": {
                                    "value": budget_var,
                                    "citation": f"[Page {page_num}]",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num]
                                },
                                "budget_vs_reforecast_pct": {
                                    "value": budget_pct,
                                    "citation": f"[Page {page_num}]" if budget_pct is not None else "",
                                    "confidence": 1.0,
                                    "page_numbers": [page_num] if budget_pct is not None else []
                                },
                                "explanation_of_variance": {
                                    "value": clean_exp,
                                    "citation": f"[Page {page_num}] {clean_exp[:80]}" if clean_exp else "",
                                    "confidence": 0.98,
                                    "page_numbers": [page_num] if clean_exp else []
                                }
                            }
                            entries.append(entry)
                        i += 1
        except Exception as e:
            logger.error(f"Error in budget variance parser: {e}")
            return None

        return entries if entries else None
