from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class PopularityAnalysis:
    score: int
    level: str
    signals: list[str]
    warnings: list[str]


def analyze_popularity(profile) -> PopularityAnalysis:
    """
    Stage 1 popularity analysis.

    This measures social/web PRESENCE and profile quality.

    It does NOT yet measure:
    - follower counts
    - tweet/post engagement
    - web mention growth
    - Google search growth
    - Telegram member growth
    - organic virality

    Those signals will be added separately so paid promotion
    is not confused with genuine organic popularity.
    """

    score = 0
    signals = []
    warnings = []

    website_url = _clean(profile.website_url)
    twitter_url = _clean(profile.twitter_url)
    telegram_url = _clean(profile.telegram_url)
    discord_url = _clean(profile.discord_url)
    tiktok_url = _clean(profile.tiktok_url)
    instagram_url = _clean(profile.instagram_url)
    description = _clean(profile.description)

    social_channels = 0

    # --------------------------------------------------
    # WEBSITE
    # --------------------------------------------------

    if website_url:
        score += 15
        signals.append("Website present")

    # --------------------------------------------------
    # X / TWITTER
    # --------------------------------------------------

    if twitter_url:
        x_type = classify_x_link(twitter_url)

        if x_type == "profile":
            score += 20
            social_channels += 1
            signals.append("Dedicated X profile")

        elif x_type == "community":
            score += 10
            social_channels += 1
            signals.append("X community present")

        elif x_type == "post":
            score += 4
            signals.append("Referenced by an X post")

            warnings.append(
                "X link is a single post, not a dedicated project account"
            )

        else:
            score += 3

            warnings.append(
                "Unrecognized X link type"
            )

    # --------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------

    if telegram_url:
        score += 15
        social_channels += 1
        signals.append("Telegram present")

    # --------------------------------------------------
    # DISCORD
    # --------------------------------------------------

    if discord_url:
        score += 10
        social_channels += 1
        signals.append("Discord present")

    # --------------------------------------------------
    # TIKTOK
    # --------------------------------------------------

    if tiktok_url:
        score += 10
        social_channels += 1
        signals.append("TikTok present")

    # --------------------------------------------------
    # INSTAGRAM
    # --------------------------------------------------

    if instagram_url:
        score += 8
        social_channels += 1
        signals.append("Instagram present")

    # --------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------

    if description:
        score += 7
        signals.append("Project description present")

    # --------------------------------------------------
    # CROSS-PLATFORM PRESENCE
    # --------------------------------------------------

    if social_channels >= 4:
        score += 15
        signals.append(
            "Strong cross-platform social presence"
        )

    elif social_channels >= 3:
        score += 12
        signals.append(
            "Good cross-platform social presence"
        )

    elif social_channels >= 2:
        score += 7
        signals.append(
            "Multiple social channels"
        )

    # --------------------------------------------------
    # LOW-PRESENCE WARNINGS
    # --------------------------------------------------

    if social_channels == 0:
        warnings.append(
            "No dedicated social community detected"
        )

    if not website_url:
        warnings.append(
            "No website detected"
        )

    # Keep score between 0 and 100.
    score = max(
        0,
        min(100, score),
    )

    if score >= 75:
        level = "STRONG"

    elif score >= 50:
        level = "ESTABLISHED"

    elif score >= 30:
        level = "DEVELOPING"

    elif score >= 15:
        level = "LIMITED"

    else:
        level = "MINIMAL"

    return PopularityAnalysis(
        score=score,
        level=level,
        signals=signals,
        warnings=warnings,
    )


def classify_x_link(url: str) -> str:
    """
    Classify an X/Twitter URL.

    Returns:
        profile
        community
        post
        unknown
    """

    if not url:
        return "unknown"

    try:
        parsed = urlparse(url)

        host = parsed.netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        if host not in {
            "x.com",
            "twitter.com",
            "mobile.twitter.com",
        }:
            return "unknown"

        path = parsed.path.strip("/")

        if not path:
            return "unknown"

        parts = path.split("/")

        # x.com/i/communities/123...
        if (
            len(parts) >= 3
            and parts[0].lower() == "i"
            and parts[1].lower() == "communities"
        ):
            return "community"

        # x.com/user/status/123...
        if (
            len(parts) >= 3
            and parts[1].lower() == "status"
        ):
            return "post"

        # x.com/username
        if len(parts) == 1:
            reserved = {
                "home",
                "explore",
                "search",
                "notifications",
                "messages",
                "settings",
                "compose",
                "login",
                "signup",
                "i",
            }

            if parts[0].lower() not in reserved:
                return "profile"

        return "unknown"

    except Exception:
        return "unknown"


def _clean(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value