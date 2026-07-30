import re


def score_reply_probability(
    designation: str | None,
    activity: str | None,
    mutuals: int,
) -> int:
    score = 35
    title = (designation or "").casefold()
    activity_text = (activity or "").casefold()

    if re.search(r"\b(recruiter|talent|hiring|people)\b", title):
        score += 20
    if re.search(r"\b(founder|chief of staff|head of product|vp product)\b", title):
        score += 12
    if re.search(r"\b(hiring|opening|role|join our team)\b", activity_text):
        score += 15
    if activity_text:
        score += 5
    score += min(mutuals * 3, 15)
    return min(score, 95)
