from unittest.mock import patch, MagicMock

import pytest

from app.channel_resolver import ChannelData
from app.llm_fit import score_fit_llm, LLMError

_CHANNEL = ChannelData(
    name="AI Growth Integrator",
    description="Helping SMMA agencies scale with AI.",
    subscriber_count=5650,
    avg_views_display="1.5K-4.1K",
    latest_upload_age_days=5,
)
_CONFIG = {
    "llm_api_key": "fake-key",
    "llm_model": "llama-3.1-8b-instant",
    "niche_keywords": ["ai", "smma"],
    "target_sub_min": 1000,
    "target_sub_max": 100_000,
    "ideal_lead_description": "Small AI/SMMA education channels",
}


def _mock_llm_response(content, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = content
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def test_score_fit_llm_parses_high_fit_response():
    content = "High Fit - Consistent uploads and solid niche in AI/SMMA growth."
    with patch("app.llm_fit.requests.post", return_value=_mock_llm_response(content)):
        level, reason = score_fit_llm(_CHANNEL, _CONFIG)
    assert level == "High"
    assert "consistent uploads" in reason.lower()


def test_score_fit_llm_raises_without_api_key():
    with pytest.raises(LLMError):
        score_fit_llm(_CHANNEL, {**_CONFIG, "llm_api_key": ""})


def test_score_fit_llm_raises_on_non_200_response():
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "unauthorized"
    with patch("app.llm_fit.requests.post", return_value=resp):
        with pytest.raises(LLMError):
            score_fit_llm(_CHANNEL, _CONFIG)


def test_score_fit_llm_raises_when_level_cannot_be_determined():
    with patch("app.llm_fit.requests.post", return_value=_mock_llm_response("I'm not sure about this one.")):
        with pytest.raises(LLMError):
            score_fit_llm(_CHANNEL, _CONFIG)
