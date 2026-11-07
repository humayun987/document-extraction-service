from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Pricing per million tokens (OpenRouter approximate rates for permitted models)
# Used if provider doesn't report cost directly in response
ESTIMATED_RATES = {
    "google/gemini-3.8-flash": {"prompt": 0.15, "completion": 0.60},
    "google/gemini-3.1-pro-preview": {"prompt": 1.25, "completion": 5.00},
    "anthropic/claude-haiku-5.5": {"prompt": 0.80, "completion": 4.00},
    "anthropic/claude-sonnet-5.5": {"prompt": 3.00, "completion": 15.00},
    "openai/gpt-6-luna": {"prompt": 0.60, "completion": 2.40},
    "openai/gpt-6.1-sol": {"prompt": 2.50, "completion": 10.00},
    "z-ai/glm-5.3-flash": {"prompt": 0.10, "completion": 0.40},
    "qwen/qwen3-vl-235b-a22b-instruct": {"prompt": 0.50, "completion": 1.50},
    "deepseek/deepseek-v3.2": {"prompt": 0.27, "completion": 1.10},
}

class ModelUsageStats(BaseModel):
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

class UsageTracker:
    def __init__(self):
        self.model_calls: int = 0
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        self.cost_usd: float = 0.0
        self.models: Dict[str, ModelUsageStats] = {}

    def record_call(
        self,
        model_id: str,
        tokens_in: int,
        tokens_out: int,
        reported_cost: Optional[float] = None
    ):
        self.model_calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        
        # Calculate cost
        cost = reported_cost
        if cost is None:
            rates = ESTIMATED_RATES.get(model_id, {"prompt": 0.5, "completion": 2.0})
            cost = (tokens_in * rates["prompt"] + tokens_out * rates["completion"]) / 1_000_000.0
            
        self.cost_usd += cost
        
        if model_id not in self.models:
            self.models[model_id] = ModelUsageStats()
            
        st = self.models[model_id]
        st.calls += 1
        st.tokens_in += tokens_in
        st.tokens_out += tokens_out
        st.cost_usd += cost

    def to_metadata(self, latency_ms: int = 0) -> Dict[str, Any]:
        return {
            "model_calls": self.model_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": latency_ms,
            "models": {k: v.model_dump() for k, v in self.models.items()}
        }

