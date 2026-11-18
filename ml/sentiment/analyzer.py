"""Transparent rule-based customer sentiment analyzer (supporting signal only, never drives priority)."""

import re
from typing import Dict, List, Tuple


POSITIVE_WORDS = {
    "thank", "thanks", "thankful", "appreciate", "appreciated", "great", "helpful",
    "awesome", "excellent", "resolved", "quick", "fast", "wonderful", "happy",
    "satisfied", "smooth", "love", "fantastic", "clear", "polite", "pleased",
}

NEGATIVE_WORDS = {
    "angry", "frustrated", "frustrating", "terrible", "horrible", "worst", "unacceptable",
    "disappointed", "useless", "broken", "failed", "failing", "stuck", "annoyed",
    "ridiculous", "furious", "awful", "poor", "pathetic", "delayed", "scam",
    "impossible", "hate", "upset", "unhelpful", "wasted", "wrong", "never",
}

INTENSIFIERS = {"very", "extremely", "really", "completely", "totally", "absolutely"}
NEGATIONS = {"not", "no", "never", "neither", "hardly", "barely"}

_TOKEN_RE = re.compile(r"[a-z']+")


def analyze_sentiment(text: str) -> Dict[str, object]:
    """
    Score customer text as positive, neutral, or negative using a transparent lexicon method.
    Explicitly labeled as 'rule_based_lexicon' so users know its method and limitations.
    """
    tokens = _TOKEN_RE.findall((text or "").lower())
    pos_score = 0.0
    neg_score = 0.0

    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else ""
        prev2 = tokens[i - 2] if i > 1 else ""
        weight = 1.5 if prev in INTENSIFIERS else 1.0
        negated = prev in NEGATIONS or prev2 in NEGATIONS

        if tok in POSITIVE_WORDS:
            if negated:
                neg_score += weight * 0.8
            else:
                pos_score += weight
        elif tok in NEGATIVE_WORDS:
            if negated:
                pos_score += weight * 0.5
            else:
                neg_score += weight

    total = pos_score + neg_score
    if total == 0:
        return {
            "label": "neutral",
            "confidence": 0.65,
            "method": "rule_based_lexicon",
            "note": "No strong positive or negative lexicon indicators detected; supporting context only.",
        }

    net = (pos_score - neg_score) / total
    if net >= 0.2:
        label = "positive"
        conf = min(0.55 + 0.40 * abs(net), 0.95)
    elif net <= -0.2:
        label = "negative"
        conf = min(0.55 + 0.40 * abs(net), 0.95)
    else:
        label = "neutral"
        conf = 0.55

    return {
        "label": label,
        "confidence": round(float(conf), 4),
        "method": "rule_based_lexicon",
        "note": "Rule-based sentiment lexicon (supporting context for agents; does not automatically escalate priority).",
    }


def analyze_conversation_trend(messages: List[str]) -> Tuple[str, List[Dict[str, object]]]:
    """Track sentiment across chronological customer messages."""
    if not messages:
        return "stable", []
    points = [analyze_sentiment(m) for m in messages]
    if len(points) < 2:
        return "single_message", points
    rank = {"negative": -1, "neutral": 0, "positive": 1}
    first_val = rank[str(points[0]["label"])]
    last_val = rank[str(points[-1]["label"])]
    if last_val > first_val:
        trend = "improving"
    elif last_val < first_val:
        trend = "worsening"
    else:
        trend = "stable"
    return trend, points
