from typing import Dict, Any, List, Optional

class CitationManager:
    @staticmethod
    def format_citation(
        snippet: str,
        page_number: Optional[int] = None,
        source_location: Optional[str] = None
    ) -> str:
        """Format citation with standard prefix."""
        clean_snippet = snippet.strip().replace("\n", " ")
        if len(clean_snippet) > 200:
            clean_snippet = clean_snippet[:197] + "..."
            
        if page_number is not None:
            return f"[Page {page_number}] {clean_snippet}"
        if source_location is not None:
            return f"[{source_location}] {clean_snippet}"
        return clean_snippet

    @staticmethod
    def clean_field_result(field_res: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure field result follows contract constraints exactly."""
        val = field_res.get("value")
        cit = field_res.get("citation", "")
        conf = field_res.get("confidence", 0.0)
        
        # Enforce float confidence in [0, 1]
        try:
            conf = max(0.0, min(1.0, float(conf)))
        except (ValueError, TypeError):
            conf = 0.5 if val is not None else 0.0

        if val is None:
            cit = ""
        else:
            if not isinstance(cit, str) or not cit.strip():
                cit = f"Extracted from document"

        res: Dict[str, Any] = {
            "value": val,
            "citation": cit,
            "confidence": round(conf, 3)
        }
        
        # Optional page_numbers
        pn = field_res.get("page_numbers")
        if pn and isinstance(pn, list):
            valid_pn = [p for p in pn if isinstance(p, int) and p >= 1]
            if valid_pn:
                res["page_numbers"] = valid_pn

        # Optional source_locations
        sl = field_res.get("source_locations")
        if sl and isinstance(sl, list):
            valid_sl = [s for s in sl if isinstance(s, str) and s.strip()]
            if valid_sl:
                res["source_locations"] = valid_sl

        return res

