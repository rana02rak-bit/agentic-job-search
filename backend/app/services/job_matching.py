import re

TARGET_ROLE_PATTERNS = (
    r"\bassociate product manager\b",
    r"\bsenior product manager\b",
    r"\bproduct manager\b",
    r"\bplatform product\b",
    r"\bproduct lead\b",
    r"\bhead of product\b",
    r"\bchief of staff\b",
    r"\bfounder'?s office\b",
    r"\bstrategy\b",
    r"\bgrowth\b",
)
TARGET_LOCATION_PATTERNS = (
    r"\bbangalore\b",
    r"\bbengaluru\b",
    r"\bgurgaon\b",
    r"\bgurugram\b",
    r"\bmumbai\b",
    r"\bremote\b",
    r"\bindia\b",
)
EXCLUDED_TITLE_PATTERNS = (
    r"\bproduct marketing\b",
    r"\bproduct designer\b",
    r"\bproduct design\b",
    r"\bproduct analyst\b",
)


def is_target_job(title: str, location: str) -> bool:
    normalized_title = " ".join(title.casefold().split())
    normalized_location = " ".join(location.casefold().split())
    role_match = any(re.search(pattern, normalized_title) for pattern in TARGET_ROLE_PATTERNS)
    excluded = any(re.search(pattern, normalized_title) for pattern in EXCLUDED_TITLE_PATTERNS)
    location_match = any(
        re.search(pattern, normalized_location) for pattern in TARGET_LOCATION_PATTERNS
    )
    return role_match and not excluded and location_match
