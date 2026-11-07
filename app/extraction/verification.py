from typing import Dict, Any, List
from app.extraction.normalizer import Normalizer
from app.extraction.citations import CitationManager
from app.extraction.calculators import DerivedCalculators

class ContractVerifier:
    @staticmethod
    def verify_and_clean_entries(
        entries: List[Dict[str, Any]],
        schema_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate and format entries against schema and output contract rules.
        - Guarantees every entry has EVERY schema field.
        - Replaces missing fields with null and empty citation.
        - Strips unknown fields.
        - Normalizes values and validates citations.
        """
        schema_fields = schema_dict.get("fields", {})
        cleaned_entries = []

        for entry in entries:
            cleaned_entry = {}
            for field_key, field_meta in schema_fields.items():
                inferred_type = "auto"
                if isinstance(field_meta, dict):
                    desc = field_meta.get("description", "").lower()
                    if "list" in desc or "array" in desc:
                        inferred_type = "list"
                    elif "string" in desc or "short phrase" in desc or field_key in {"zip_code", "postal_code", "unit", "unit_id", "suite", "base_rent_escalation"}:
                        inferred_type = "string"
                    elif "number" in desc or "amount" in desc or "percentage" in desc or "ratio" in desc:
                        inferred_type = "number"

                if field_key in entry and isinstance(entry[field_key], dict):
                    raw_fr = entry[field_key]
                    val = Normalizer.normalize_value(raw_fr.get("value"), expected_type=inferred_type)
                    cit = raw_fr.get("citation", "")
                    conf = raw_fr.get("confidence", 0.9 if val is not None else 0.0)
                    
                    cleaned_fr = {
                        "value": val,
                        "citation": str(cit) if cit is not None else "",
                        "confidence": conf
                    }
                    if "page_numbers" in raw_fr:
                        cleaned_fr["page_numbers"] = raw_fr["page_numbers"]
                    if "source_locations" in raw_fr:
                        cleaned_fr["source_locations"] = raw_fr["source_locations"]
                        
                    cleaned_entry[field_key] = CitationManager.clean_field_result(cleaned_fr)
                else:
                    # Genuinely absent field
                    cleaned_entry[field_key] = {
                        "value": None,
                        "citation": "",
                        "confidence": 0.0
                    }

            # Run deterministic calculations
            cleaned_entry = DerivedCalculators.compute_lease_fields(cleaned_entry)
            cleaned_entry = DerivedCalculators.compute_om_fields(cleaned_entry)

            cleaned_entries.append(cleaned_entry)

        if not cleaned_entries:
            # Fallback single empty row if none produced
            empty_entry = {
                k: {"value": None, "citation": "", "confidence": 0.0}
                for k in schema_fields
            }
            cleaned_entries.append(empty_entry)

        return cleaned_entries

