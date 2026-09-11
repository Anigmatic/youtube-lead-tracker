def score_fit_rule_based(channel, config: dict) -> tuple:
    keywords = [k.strip().lower() for k in config.get("niche_keywords", []) if k.strip()]
    haystack = f"{channel.name} {channel.description}".lower()

    reasons = []
    score = 0
    max_score = 2

    if keywords:
        max_score = 3
        if any(k in haystack for k in keywords):
            score += 1
            reasons.append("matches niche keywords")
        else:
            reasons.append("no niche keyword match")

    sub_min = config.get("target_sub_min", 0)
    sub_max = config.get("target_sub_max", 10 ** 9)
    if sub_min <= channel.subscriber_count <= sub_max:
        score += 1
        reasons.append("subscriber count in target range")
    else:
        reasons.append("subscriber count outside target range")

    if channel.latest_upload_age_days <= 60:
        score += 1
        reasons.append("active in the last 60 days")
    else:
        reasons.append("no recent uploads in 60+ days")

    ratio = score / max_score if max_score else 0
    if ratio >= 0.99:
        level = "High"
    elif ratio >= 0.5:
        level = "Moderate"
    else:
        level = "Low"

    reason = (", ".join(reasons) + ".")
    reason = reason[0].upper() + reason[1:]
    return level, reason
