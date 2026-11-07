import base64
from typing import Dict, Any, List, Optional

EXTRACTION_SYSTEM_PROMPT = """You are an expert commercial real estate (CRE) document intelligence extractor.
Your task is to extract structured values from the provided document context strictly adhering to the requested field schema.

CRITICAL RULES:
1. NULL DISCIPLINE: If a field value is not explicitly and unambiguously present in the text, return null. NEVER guess, assume, or hallucinate a value. A hallucination is penalized far more severely than a null.
2. TYPES:
   - Numeric fields must be raw JSON numbers (int or float), NEVER strings. Do NOT include currency symbols ($, €, £), commas, or thousands separators. Example: 4250.00 not "$4,250.00".
   - Dates must be strictly in "YYYY-MM-DD" format.
   - Percentages must be the exact number stated in the source (e.g. 93.75 for 93.75%, not 0.9375).
   - Booleans must be actual JSON true/false.
   - Lists of scalars only when the description explicitly asks for multiple items (e.g. rent schedules, amenities).
3. CITATIONS:
   - For every non-null field, provide a short verbatim citation prefixed with its source location, e.g. "[Page 3] Base Rent: $4,250.00 per month" or "[Sheet1!F4] 4250".
   - If the value is null, the citation MUST be an empty string "".
   - Never invent or synthesize a citation.
4. CONFIDENCE:
   - Provide a realistic float between 0.0 and 1.0 representing your confidence.
   - High confidence (0.95 - 1.0) for unambiguous direct statements.
   - Lower confidence for ambiguous or inferred clauses.
   - Do NOT return 1.0 for everything.
5. OUTPUT FORMAT:
   Return ONLY a valid JSON object matching this structure:
   {
     "fields": {
       "field_key": {
         "value": <scalar or list or null>,
         "citation": "<exact verbatim quote with location prefix>",
         "confidence": <float 0.0 to 1.0>,
         "page_numbers": [<int page numbers>] (optional for PDFs),
         "source_locations": ["<Sheet!Cell>"] (optional for XLSX/CSV)
       }
     }
   }
"""

def build_extraction_prompt(
    schema_fields: Dict[str, Any],
    document_context: str,
    table_context: str = "",
    images_base64: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Build chat completion messages supporting text and multimodal image inputs.
    """
    fields_desc = []
    for k, v in schema_fields.items():
        name = v.get("name", k)
        desc = v.get("description", "")
        primary = v.get("primary", False)
        fields_desc.append(f"- Field Key: '{k}' (Name: {name}, Primary: {primary})\n  Description: {desc}")

    table_str = f"TABLE CONTEXT:\n{table_context}\n" if table_context else ""
    fields_str = "\n".join(fields_desc)
    prompt_body = f"""DOCUMENT CONTEXT:
{document_context}

{table_str}

FIELDS TO EXTRACT:
{fields_str}

Remember:
- Return every field key in the fields dictionary.
- Return null for missing fields.
- Verbatim citations prefixed with location.
- Numbers as JSON numbers without commas or currency symbols.
"""
    if images_base64:
        # Multimodal vision message payload
        user_content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt_body}
        ]
        for img_b64 in images_base64[:5]:  # limit to top relevant pages to control token payload
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high"
                }
            })
        return [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
    else:
        return [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_body}
        ]
