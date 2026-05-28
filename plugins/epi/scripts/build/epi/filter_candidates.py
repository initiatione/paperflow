from __future__ import annotations


def filter_candidates_with_report(candidates: list[dict], domains: list[str], require_pdf: bool) -> dict[str, list[dict]]:
    kept: list[dict] = []
    rejected: list[dict] = []
    domain_terms = [term.lower() for term in domains]
    for candidate in candidates:
        haystack = " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("abstract") or ""),
                str(candidate.get("venue") or ""),
            ]
        ).lower()
        reasons: list[str] = []
        if require_pdf and not candidate.get("pdf_url"):
            reasons.append("missing_pdf")
        if domain_terms and not any(term in haystack for term in domain_terms):
            robotics_terms = ["robot", "humanoid", "control", "navigation", "embodied"]
            if not any(term in haystack for term in robotics_terms):
                reasons.append("outside_domain")
        filtered = dict(candidate)
        filtered["filter_reasons"] = reasons
        filtered["filter_status"] = "rejected" if reasons else "kept"
        if reasons:
            rejected.append(filtered)
        else:
            kept.append(filtered)
    return {"kept": kept, "rejected": rejected}


def filter_candidates(candidates: list[dict], domains: list[str], require_pdf: bool) -> list[dict]:
    return filter_candidates_with_report(candidates, domains=domains, require_pdf=require_pdf)["kept"]
