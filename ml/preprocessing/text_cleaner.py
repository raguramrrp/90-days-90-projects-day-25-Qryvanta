"""Text preprocessing and normalization utilities for QRYVANTA NLP pipelines."""

import re
import unicodedata


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
_ORDER_ID_RE = re.compile(r"\b(?:ORD|INV|TXN|TKT|QRY)[-#]?\d{3,10}\b", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def anonymize_pii(text: str) -> str:
    """Replace emails, phone numbers, URLs, and long numeric references with neutral tokens."""
    if not text:
        return ""
    cleaned = _EMAIL_RE.sub(" [email] ", text)
    cleaned = _PHONE_RE.sub(" [phone] ", cleaned)
    cleaned = _URL_RE.sub(" [url] ", cleaned)
    cleaned = _ORDER_ID_RE.sub(" [ref_id] ", cleaned)
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def normalize_text(text: str) -> str:
    """Normalize support ticket text for TF-IDF vectorization while preserving domain signal."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = anonymize_pii(text)
    text = text.lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def combine_ticket_text(subject: str, description: str, product_reference: str | None = None) -> str:
    """Combine subject (weighted twice for stronger topic signal) and description."""
    parts = [subject or "", subject or "", description or ""]
    if product_reference:
        parts.append(product_reference)
    return normalize_text(" ".join(parts))
