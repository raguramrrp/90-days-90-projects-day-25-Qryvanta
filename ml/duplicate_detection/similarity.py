"""TF-IDF + Cosine Similarity Duplicate & Related Ticket Detection."""

from typing import Any, Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ml.preprocessing.text_cleaner import combine_ticket_text


def find_similar_tickets(
    query_subject: str,
    query_description: str,
    candidates: List[Dict[str, Any]],
    threshold: float = 0.25,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Compare a target ticket against authorized candidate tickets using TF-IDF cosine similarity.
    Never auto-merges or auto-closes tickets; returns ranked candidates above threshold.
    """
    if not candidates:
        return []

    query_clean = combine_ticket_text(query_subject, query_description)
    if not query_clean:
        return []

    candidate_texts = [
        combine_ticket_text(str(c.get("subject", "")), str(c.get("description", "")))
        for c in candidates
    ]

    corpus = [query_clean] + candidate_texts
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    ranked_indices = sims.argsort()[::-1]

    results: List[Dict[str, Any]] = []
    for idx in ranked_indices:
        score = float(sims[idx])
        if score < threshold:
            break
        item = candidates[int(idx)]
        results.append(
            {
                "ticket_id": item["id"],
                "ticket_reference": item["ticket_reference"],
                "subject": item["subject"],
                "category": item.get("category_name"),
                "status": item.get("status"),
                "priority": item.get("priority"),
                "similarity_score": round(score, 4),
            }
        )
        if len(results) >= top_k:
            break

    return results
