from typing import List, Dict, Any, Optional
from app.extractors.base import ParsedDocument
from app.extraction.schema_analyzer import AnalyzedSchema

class ExtractionPlanner:
    @staticmethod
    def select_relevant_context(parsed_doc: ParsedDocument, schema: AnalyzedSchema, max_chars: int = 12000) -> str:
        """
        Intelligently select relevant document sections, pages, or paragraphs
        based on schema keywords to minimize token consumption.
        """
        # If it's a small document (< max_chars), use full text
        full_text = parsed_doc.get_full_text()
        if len(full_text) <= max_chars:
            return full_text

        # For multi-page PDFs, select anchor pages:
        # 1. First 3 pages (always critical for summary/parties/premises)
        # 2. Pages mentioning rent schedule, base rent, financial analysis, NOI, occupancy
        if parsed_doc.pages:
            selected_pages = []
            keywords = [
                "rent schedule", "base rent", "article 43", "schedule a", "schedule b",
                "abatement", "operating expenses", "security deposit", "pro forma",
                "noi", "unit mix", "occupancy", "floor plans", "executive summary"
            ]
            
            for p in parsed_doc.pages:
                p_text_lower = p.text.lower()
                # Always take first 3 pages
                if p.page_number <= 3:
                    selected_pages.append(p)
                    continue
                # Check for keywords
                if any(kw in p_text_lower for kw in keywords):
                    selected_pages.append(p)
                    
            if selected_pages:
                # Combine selected pages
                combined = "\n\n".join(f"--- [Page {p.page_number}] ---\n{p.text}" for p in selected_pages)
                if len(combined) > max_chars:
                    return combined[:max_chars]
                return combined

        # For DOCX, select relevant paragraphs
        if parsed_doc.paragraphs:
            selected_paras = []
            for p in parsed_doc.paragraphs:
                p_lower = p.text.lower()
                if p.index <= 40 or p.is_table_like or any(w in p_lower for w in ["tenant", "landlord", "rent", "term", "commencement"]):
                    selected_paras.append(f"[Paragraph {p.index}] {p.text}")
                    if sum(len(s) for s in selected_paras) >= max_chars:
                        break
            return "\n".join(selected_paras)

        return full_text[:max_chars]

