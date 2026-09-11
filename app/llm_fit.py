import requests

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


def score_fit_llm(channel, config: dict) -> tuple:
    api_key = config.get("llm_api_key")
    if not api_key:
        raise LLMError("No LLM API key configured")
    model = config.get("llm_model") or "llama-3.1-8b-instant"

    try:
        resp = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a lead-qualification assistant for YouTube outreach. "
                            "Respond with exactly one line in the form: "
                            "'<High|Moderate|Low> Fit - <one short reason>'."
                        ),
                    },
                    {"role": "user", "content": _build_prompt(channel, config)},
                ],
                "temperature": 0.2,
                "max_tokens": 60,
            },
            timeout=20,
        )
    except requests.RequestException as e:
        raise LLMError(f"LLM request failed: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:200]}")

    try:
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected LLM response shape: {e}") from e

    return _parse_verdict(content)


def _build_prompt(channel, config: dict) -> str:
    return (
        f"Ideal lead criteria: {config.get('ideal_lead_description', 'Not specified')}\n"
        f"Niche keywords: {', '.join(config.get('niche_keywords', []))}\n"
        f"Target subscriber range: {config.get('target_sub_min', 0)}-{config.get('target_sub_max', 'unlimited')}\n\n"
        f"Channel name: {channel.name}\n"
        f"Description: {channel.description[:500]}\n"
        f"Subscribers: {channel.subscriber_count}\n"
        f"Recent video views range: {channel.avg_views_display}\n"
        f"Most recent upload: {channel.latest_upload_age_days} days ago\n"
    )


def _parse_verdict(content: str) -> tuple:
    lower = content.lower()
    if "high" in lower:
        level = "High"
    elif "moderate" in lower:
        level = "Moderate"
    elif "low" in lower:
        level = "Low"
    else:
        raise LLMError(f"Could not determine fit level from LLM response: {content!r}")

    reason = content
    if "-" in content:
        reason = content.split("-", 1)[1].strip()
    elif ":" in content:
        reason = content.split(":", 1)[1].strip()
    return level, reason
