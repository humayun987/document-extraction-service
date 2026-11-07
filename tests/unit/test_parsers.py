import pytest
from app.utils.file_detection import detect_file_type
from app.extraction.normalizer import Normalizer
from app.extraction.calculators import DerivedCalculators
from app.extraction.citations import CitationManager
from app.extraction.verification import ContractVerifier

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
    # Booleans
    assert Normalizer.normalize_value("true") is True
    assert Normalizer.normalize_value("No") is False
    # Null equivalents
    assert Normalizer.normalize_value("N/A") is None
    assert Normalizer.normalize_value("---") is None
    assert Normalizer.normalize_value("") is None

def test_derived_calculators():
    # Months between
    months = DerivedCalculators.calculate_months_between("1993-05-01", "1998-04-30")
    assert months == 60

    # Lease derived fields
    entry = {
        "rentable_square_footage": {"value": 1892.0},
        "rent_schedule_monthly_rent": {"value": [1932.0, 1990.0]}
    }
    reconciled = DerivedCalculators.compute_lease_fields(entry)
    rates = reconciled["rent_schedule_annual_rent_per_rsf"]["value"]
    assert len(rates) == 2
    assert rates[0] == round((1932.0 * 12) / 1892.0, 2)

    # OM derived ratios
    om_entry = {
        "total_units": {"value": 188},
        "total_square_footage": {"value": 190142.0},
        "total_parking_spaces": {"value": 266}
    }
    om_reconciled = DerivedCalculators.compute_om_fields(om_entry)
    assert om_reconciled["average_unit_size"]["value"] == 1011.4
    assert om_reconciled["parking_ratio"]["value"] == 1.41

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
    # Missing field must be present with value null and empty citation
    assert "missing_field" in verified[0]
    assert verified[0]["missing_field"]["value"] is None
    assert verified[0]["missing_field"]["citation"] == ""
