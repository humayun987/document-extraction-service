import os
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.llm.usage import UsageTracker
from app.utils.logging import logger

PERMITTED_MODELS = {
    "google/gemini-3.8-flash",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-haiku-5.5",
    "anthropic/claude-sonnet-5.5",
    "openai/gpt-6-luna",
    "openai/gpt-6.1-sol",
    "z-ai/glm-5.3-flash",
    "qwen/qwen3-vl-235b-a22b-instruct",
    "deepseek/deepseek-v3.2",
}

class LLMConfigurationError(RuntimeError):
    """Raised when LLM completion is attempted without proper credentials or base URL."""
    pass

class LLMClient:
    def __init__(self, usage_tracker: Optional[UsageTracker] = None):
        self.usage_tracker = usage_tracker or UsageTracker()

    def call_completion(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = True,
        max_retries: int = 4
    ) -> Dict[str, Any]:
        """
        Execute chat completion through configured OpenAI-compatible gateway.
        Enforces strict model whitelist and environment-based credentials.
        Raises LLMConfigurationError if gateway credentials are not configured.
        """
        if model_id not in PERMITTED_MODELS:
            raise ValueError(
                f"Model '{model_id}' is not permitted by assignment whitelist: {sorted(PERMITTED_MODELS)}"
            )

        base_url = (settings.LLM_BASE_URL or "").rstrip("/")
        api_key = settings.LLM_API_KEY

        if not base_url or not api_key:
            raise LLMConfigurationError(
                "LLM_BASE_URL or LLM_API_KEY environment variable is not configured. "
                "Set these variables with valid credentials to enable LLM extraction."
            )

        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://outcome.ai",
            "X-Title": "Outcome Document Extraction"
        }

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        delay = 1.0
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if not choices:
                            raise ValueError("OpenAI response contained no choices")
                            
                        content = choices[0].get("message", {}).get("content", "")
                        usage = data.get("usage", {})
                        t_in = usage.get("prompt_tokens", 0)
                        t_out = usage.get("completion_tokens", 0)
                        
                        reported_cost = None
                        if "cost" in data:
                            reported_cost = float(data["cost"])
                        elif "usage" in data and "cost" in data["usage"]:
                            reported_cost = float(data["usage"]["cost"])

                        self.usage_tracker.record_call(
                            model_id=model_id,
                            tokens_in=t_in,
                            tokens_out=t_out,
                            reported_cost=reported_cost
                        )
                        return {"content": content, "raw": data}

                    elif resp.status_code == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait_sec = float(retry_after) if retry_after and retry_after.isdigit() else delay + 0.5
                        logger.warning(f"HTTP 429 Rate limit on model {model_id}. Backing off for {wait_sec:.2f}s...")
                        import time
                        time.sleep(wait_sec)
                        delay *= 2

                    elif resp.status_code >= 500:
                        logger.warning(f"HTTP {resp.status_code} server error from LLM gateway on attempt {attempt}")
                        import time
                        time.sleep(delay)
                        delay *= 2
                    else:
                        error_text = resp.text
                        logger.error(f"HTTP {resp.status_code} permanent error from LLM gateway: {error_text}")
                        raise RuntimeError(f"LLM gateway returned HTTP {resp.status_code}: {error_text}")

            except (httpx.RequestError, ValueError) as exc:
                last_exception = exc
                logger.warning(f"Transient error connecting to LLM gateway on attempt {attempt}: {exc}")
                import time
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"LLM request exhausted {max_retries} retries for model {model_id}. Last error: {last_exception}")

    @staticmethod
    def extract_json(content: str) -> Dict[str, Any]:
        """Parse JSON from model response, handling markdown fences and common issues."""
        import re
        import json
        cleaned = content.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
            
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end+1])
            raise
