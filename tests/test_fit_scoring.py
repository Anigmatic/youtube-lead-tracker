from app.channel_resolver import ChannelData
from app.fit_scoring import score_fit_rule_based

_CONFIG = {
    "niche_keywords": ["ai", "smma", "growth"],
    "target_sub_min": 1000,
    "target_sub_max": 100_000,
}


def test_high_fit_when_keyword_matches_in_range_and_active():
    channel = ChannelData(
        name="AI Growth Integrator",
        description="Helping SMMA agencies scale with AI.",
        subscriber_count=5650,
        avg_views_max=4100,
        latest_upload_age_days=5,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "High"
    assert "niche" in reason.lower()


def test_low_fit_when_no_keyword_out_of_range_and_stale():
    channel = ChannelData(
        name="Random Cooking Channel",
        description="Recipes and cooking tips.",
        subscriber_count=500_000,
        avg_views_max=200,
        latest_upload_age_days=400,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "Low"


def test_moderate_fit_when_two_of_three_checks_pass():
    channel = ChannelData(
        name="Growth School",
        description="Learn growth marketing skool.com/growthschool",
        subscriber_count=29_800,
        avg_views_max=7900,
        latest_upload_age_days=400,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "Moderate"


def test_scorer_ignores_keyword_check_when_no_keywords_configured():
    channel = ChannelData(
        name="Anything",
        description="No relevant keywords here.",
        subscriber_count=5000,
        avg_views_max=1000,
        latest_upload_age_days=1,
    )
    level, _ = score_fit_rule_based(channel, {"niche_keywords": [], "target_sub_min": 0, "target_sub_max": 10**9})
    assert level == "High"
