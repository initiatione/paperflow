from __future__ import annotations

from math import log10


def rank_candidates(candidates: list[dict], positive_keywords: list[str], venue_tiers: dict[str, float]) -> list[dict]:
    ranked: list[dict] = []
    keywords = [keyword.lower() for keyword in positive_keywords]
    for candidate in candidates:
        text = f"{candidate.get('title', '')} {candidate.get('abstract', '')}".lower()
        keyword_hits = sum(1 for keyword in keywords if keyword in text)
        topic_score = min(1.0, keyword_hits / max(1, len(keywords)))
        venue_score = venue_tiers.get(str(candidate.get("venue") or "").lower(), 0.45)
        citation_score = min(1.0, log10(int(candidate.get("citation_count") or 0) + 1) / 3)
        freshness_score = 1.0 if int(candidate.get("year") or 0) >= 2024 else 0.7
        pdf_score = 1.0 if candidate.get("pdf_url") else 0.0
        code_score = 1.0 if candidate.get("code_url") else 0.0
        score = (
            topic_score * 0.35
            + venue_score * 0.18
            + citation_score * 0.15
            + freshness_score * 0.10
            + pdf_score * 0.08
            + code_score * 0.08
            + 0.06
        )
        ranked_candidate = dict(candidate)
        ranked_candidate["score"] = round(score, 4)
        ranked_candidate["ranking_signals"] = {
            "topic_score": round(topic_score, 4),
            "venue_score": round(venue_score, 4),
            "citation_score": round(citation_score, 4),
            "freshness_score": freshness_score,
            "pdf_score": pdf_score,
            "code_score": code_score,
        }
        ranked.append(ranked_candidate)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)
