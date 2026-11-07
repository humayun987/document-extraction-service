from typing import Optional
from app.config import settings

class ModelRouter:
    @staticmethod
    def get_model_for_task(
        task_type: str = "general_text",
        is_scanned: bool = False,
        requires_legal_reasoning: bool = False,
        requires_escalation: bool = False,
        current_spend: float = 0.0
    ) -> str:
        """
        Dynamically route task to the most economical permitted model.
        Respects strict assignment budget ceiling ($9.00 limit).
        """
        # Budget guard: if spend is nearing the ceiling, force the cheapest permitted model
        if current_spend >= settings.LLM_BUDGET_CEILING_USD:
            return "google/gemini-3.8-flash"

        if is_scanned or task_type == "vision":
            return "google/gemini-3.8-flash"  # Highly capable, multimodal and economical

        if requires_escalation:
            # High-stakes ambiguous verification
            if current_spend < 7.0:
                return "google/gemini-3.1-pro-preview"
            return "deepseek/deepseek-v3.2"

        if requires_legal_reasoning:
            return "deepseek/deepseek-v3.2"

        # Standard extraction
        return "google/gemini-3.8-flash"

