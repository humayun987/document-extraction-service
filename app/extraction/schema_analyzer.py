from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

class FieldMetadata(BaseModel):
    key: str
    name: str
    description: str
    is_primary: bool = False
    inferred_type: str = "string"  # "number", "date", "string", "boolean", "list"
    is_document_level: bool = False

class AnalyzedSchema(BaseModel):
    name: Optional[str] = None
    is_table_based: bool = False
    primary_field: Optional[str] = None
    fields: Dict[str, FieldMetadata] = Field(default_factory=dict)
    doc_level_field_keys: List[str] = Field(default_factory=list)
    row_level_field_keys: List[str] = Field(default_factory=list)

class SchemaAnalyzer:
    @staticmethod
    def analyze(schema_dict: Dict[str, Any]) -> AnalyzedSchema:
        schema_name = schema_dict.get("name")
        raw_fields = schema_dict.get("fields", {})
        
        primary_key = None
        for k, v in raw_fields.items():
            if isinstance(v, dict) and v.get("primary") is True:
                primary_key = k
                break

        is_table = (primary_key is not None)
        
        # Document-level field keywords
        doc_level_keywords = {
            "property", "building", "report_date", "date", "budget_year",
            "as_of_date", "period", "tenant_name", "landlord", "landlord_legal_name"
        }

        analyzed = AnalyzedSchema(
            name=schema_name,
            is_table_based=is_table,
            primary_field=primary_key
        )

        for k, v in raw_fields.items():
            if not isinstance(v, dict):
                continue
            name = v.get("name", k)
            desc = v.get("description", "").lower()
            is_primary = (k == primary_key)

            # Infer type
            inferred_type = "string"
            if any(w in desc for w in ["list of", "array of", "multiple"]):
                inferred_type = "list"
            elif any(w in desc for w in ["true/false", "boolean", "whether"]):
                inferred_type = "boolean"
            elif any(w in desc for w in ["date", "yyyy-mm-dd", "when"]):
                inferred_type = "date"
            elif any(w in desc for w in ["amount", "rent", "number", "count", "square feet", "sq ft", "percentage", "rate", "ratio", "total", "balance", "deposit", "rsf", "variance"]):
                inferred_type = "number"

            # Infer doc level vs row level
            is_doc_level = False
            if is_table:
                if any(w in k.lower() for w in doc_level_keywords) and not is_primary:
                    if "unit" not in k.lower() and "line" not in k.lower() and "gl" not in k.lower():
                        is_doc_level = True
            else:
                is_doc_level = True

            meta = FieldMetadata(
                key=k,
                name=name,
                description=v.get("description", ""),
                is_primary=is_primary,
                inferred_type=inferred_type,
                is_document_level=is_doc_level
            )
            analyzed.fields[k] = meta
            if is_doc_level:
                analyzed.doc_level_field_keys.append(k)
            else:
                analyzed.row_level_field_keys.append(k)

        return analyzed

