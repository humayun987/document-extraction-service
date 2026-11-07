import pytest
import io
import openpyxl
from app.utils.file_detection import detect_file_type
from app.extraction.normalizer import Normalizer
from app.extraction.calculators import DerivedCalculators
from app.extraction.citations import CitationManager
from app.extraction.verification import ContractVerifier
from app.extraction.table_parsers import CRETableParsers
from app.extraction.schema_analyzer import SchemaAnalyzer
from app.extractors.base import ParsedDocument, SpreadsheetSheet, DocumentParagraph

def test_file_detection():
    # PDF
    assert detect_file_type(b"%PDF-1.4\n...", "sample.pdf") == "pdf"
    # CSV
    assert detect_file_type(b"Col1,Col2\nVal1,Val2\n", "sample.csv") == "csv"

def test_normalizer_values():
    # Currencies with commas and symbols
    assert Normalizer.normalize_value("$1,250.00") == 1250.0
    assert Normalizer.normalize_value("€4,500") == 4500
    # Negative in parentheses
    assert Normalizer.normalize_value("(322,938)") == -322938.0
    # Percentages
    assert Normalizer.normalize_value("93.75%") == 93.75
    # Dates
    assert Normalizer.normalize_value("09/27/2026") == "2026-09-27"
    assert Normalizer.normalize_value("March 5, 1993") == "1993-03-05"
    assert Normalizer.normalize_value("21st day of August, 2025") == "2025-08-21"
    # Booleans
    assert Normalizer.normalize_value("true") is True
    assert Normalizer.normalize_value("No") is False
    # Null equivalents
    assert Normalizer.normalize_value("N/A") is None
    assert Normalizer.normalize_value("---") is None
    assert Normalizer.normalize_value("") is None

def test_derived_calculators():
    months = DerivedCalculators.calculate_months_between("1993-05-01", "1998-04-30")
    assert months == 60

    entry = {
        "rentable_square_footage": {"value": 1892.0},
        "rent_schedule_monthly_rent": {"value": [1932.0, 1990.0]}
    }
    reconciled = DerivedCalculators.compute_lease_fields(entry)
    rates = reconciled["rent_schedule_annual_rent_per_rsf"]["value"]
    assert len(rates) == 2
    assert rates[0] == round((1932.0 * 12) / 1892.0, 2)

def test_contract_verifier():
    schema = {
        "fields": {
            "prop_name": {"name": "Property", "description": "Property name"},
            "missing_field": {"name": "Missing", "description": "Missing description"}
        }
    }
    raw_entries = [
        {"prop_name": {"value": "Summit Plaza", "citation": "[Page 1] Summit Plaza", "confidence": 0.99}}
    ]
    verified = ContractVerifier.verify_and_clean_entries(raw_entries, schema)
    assert len(verified) == 1
    assert verified[0]["prop_name"]["value"] == "Summit Plaza"
    assert "missing_field" in verified[0]
    assert verified[0]["missing_field"]["value"] is None
    assert verified[0]["missing_field"]["citation"] == ""

def test_synthetic_csv_with_reordered_and_extra_columns():
    """Verify boxscore CSV parsing with reordered and extra columns."""
    doc = ParsedDocument(file_type="csv", file_path="dummy.csv")
    sheet = SpreadsheetSheet(name="Sheet1")
    sheet.rows = [
        ["Box Score Report - Confidential"],
        ["Evergreen Ridge Apartments"],
        ["For Week Ending: 08/15/2026"],
        [],
        ["Notes", "Code", "Units", "Name", "Irrelevant_Col", "Avg Rent", "Occupied No Notice"],
        ["Note1", "1B1B", "40", "The Birch", "N/A", "$1,450.00", "38"],
        ["Note2", "2B2B", "25", "The Maple", "N/A", "$1,895.00", "24"],
        ["Total Units", "65", "", "", "", "", ""]
    ]
    doc.sheets["Sheet1"] = sheet

    schema = {
        "fields": {
            "property_name": {"name": "Property Name", "description": "Property name"},
            "code": {"name": "Code", "primary": True},
            "name": {"name": "Plan Name"},
            "units": {"name": "Units", "description": "Total units in plan"},
            "avg_rent": {"name": "Average Rent", "description": "Average monthly rent"}
        }
    }

    entries = CRETableParsers.parse_boxscore_csv(doc, schema)
    assert entries is not None
    assert len(entries) == 2
    assert entries[0]["property_name"]["value"] == "Evergreen Ridge Apartments"
    assert entries[0]["code"]["value"] == "1B1B"
    assert entries[0]["name"]["value"] == "The Birch"
    assert entries[0]["units"]["value"] == 40
    assert entries[0]["avg_rent"]["value"] == 1450.0

def test_synthetic_rentroll_custom_sheet_name(tmp_path):
    """Verify rent roll parsing when sheet name is custom (not Willow Creek Commons)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Oak Ridge Towers"
    ws.cell(1, 1, "Rent Roll Summary")
    ws.cell(3, 1, "Oak Ridge Towers")
    ws.cell(4, 1, "Mar 2025")
    ws.cell(6, 1, "Unit")
    ws.cell(6, 2, "Unit Type")
    ws.cell(6, 3, "Square Feet")
    ws.cell(6, 4, "Status")
    ws.cell(6, 5, "Resident")
    ws.cell(6, 6, "Market Rent")

    ws.cell(7, 1, "101")
    ws.cell(7, 2, "A1")
    ws.cell(7, 3, 750)
    ws.cell(7, 4, "Current")
    ws.cell(7, 5, "John Doe")
    ws.cell(7, 6, 1350)

    xlsx_path = tmp_path / "synthetic_rentroll.xlsx"
    wb.save(xlsx_path)

    doc = ParsedDocument(file_type="xlsx", file_path=str(xlsx_path))
    schema = {
        "fields": {
            "unit_number": {"name": "Unit Number", "primary": True},
            "property_name": {"name": "Property Name"},
            "market_rent": {"name": "Market Rent"}
        }
    }

    entries = CRETableParsers.parse_rentroll_xlsx(doc, schema)
    assert entries is not None
    assert len(entries) == 1
    assert entries[0]["unit_number"]["value"] == "101"
    assert entries[0]["property_name"]["value"] == "Oak Ridge Towers"
    assert entries[0]["market_rent"]["value"] == 1350.0
    assert "Oak Ridge Towers" in entries[0]["unit_number"]["citation"]

def test_dynamic_schema_analyzer():
    schema = {
        "name": "custom_financial_schema",
        "fields": {
            "invoice_id": {"name": "Invoice #", "primary": True},
            "vendor_name": {"name": "Vendor"},
            "due_date": {"name": "Due Date", "description": "Date invoice is due (YYYY-MM-DD)"},
            "amount_cents": {"name": "Amount Cents", "description": "Total amount in cents"},
            "is_paid": {"name": "Paid Flag", "description": "Boolean flag whether invoice is paid"},
            "line_items": {"name": "Items", "description": "List of line item descriptions"}
        }
    }
    analyzed = SchemaAnalyzer.analyze(schema)
    assert analyzed.is_table_based is True
    assert analyzed.primary_field == "invoice_id"
    assert analyzed.fields["due_date"].inferred_type == "date"
    assert analyzed.fields["amount_cents"].inferred_type == "number"
    assert analyzed.fields["is_paid"].inferred_type == "boolean"
    assert analyzed.fields["line_items"].inferred_type == "list"
