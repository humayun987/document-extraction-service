import json
import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.llm.client import LLMClient, LLMConfigurationError, PERMITTED_MODELS
from app.llm.usage import UsageTracker
from app.llm.router import ModelRouter

def test_model_whitelist_enforcement():
    tracker = UsageTracker()
    client = LLMClient(tracker)
    
    # Disallowed model must raise ValueError
    with pytest.raises(ValueError, match="not permitted"):
        client.call_completion(model_id="unapproved/gpt-4-turbo", messages=[{"role": "user", "content": "hi"}])

def test_missing_credentials_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("app.config.settings.LLM_BASE_URL", "")
    monkeypatch.setattr("app.config.settings.LLM_API_KEY", "")
    
    tracker = UsageTracker()
    client = LLMClient(tracker)
    
    with pytest.raises(LLMConfigurationError, match="not configured"):
        client.call_completion(
            model_id="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": "test"}]
        )

def test_llm_retry_on_429_and_500():
    tracker = UsageTracker()
    client = LLMClient(tracker)

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "0.01"}

    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [{"message": {"content": '{"fields": {"rent": {"value": 1500, "citation": "[Page 1]"}}}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "cost": 0.0015
    }

    with patch("httpx.Client.post", side_effect=[mock_resp_429, mock_resp_500, mock_resp_200]):
        resp = client.call_completion(
            model_id="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": "extract"}]
        )
        assert "content" in resp
        data = client.extract_json(resp["content"])
        assert data["fields"]["rent"]["value"] == 1500

    assert tracker.total_calls == 1
    assert tracker.tokens_in == 100
    assert tracker.tokens_out == 50
    assert tracker.cost_usd == 0.0015

def test_llm_json_extraction_with_markdown_fences():
    content_with_fences = """```json
{
  "fields": {
    "tenant_name": {
      "value": "Acme Corp",
      "citation": "[Page 1] Acme Corp as Tenant",
      "confidence": 0.98
    }
  }
}
```"""
    data = LLMClient.extract_json(content_with_fences)
    assert data["fields"]["tenant_name"]["value"] == "Acme Corp"

def test_router_model_selection_and_budget_guard():
    # Test legal task routing
    m1 = ModelRouter.get_model_for_task(task_type="legal_reasoning", current_spend=0.0)
    assert m1 in PERMITTED_MODELS

    # Test vision model routing for scanned document
    m2 = ModelRouter.get_model_for_task(task_type="general_text", is_scanned=True, current_spend=0.0)
    assert m2 in {"google/gemini-3.8-flash", "qwen/qwen3-vl-235b-a22b-instruct"}

    # Test budget guard fallback when current spend exceeds limit
    m3 = ModelRouter.get_model_for_task(task_type="legal_reasoning", current_spend=9.50)
    assert m3 == "google/gemini-3.8-flash"  # Fallback economical model
