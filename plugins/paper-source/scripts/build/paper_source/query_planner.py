from __future__ import annotations

import argparse
import json
import re
from typing import Any

from paper_source.concept_groups import derive_required_concept_groups, required_concept_group_contract
from paper_source.filter_candidates import default_discovery_exclusion_terms


GENERIC_QUALITY_SIGNALS = [
    "benchmark",
    "experiment",
    "case study",
    "dataset",
    "field study",
    "open source",
    "replication",
]

GENERIC_CONTEXT_TERMS = [
    "application",
    "evaluation",
    "method",
    "system",
    "implementation",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "for",
    "from",
    "high",
    "in",
    "latest",
    "new",
    "of",
    "on",
    "paper",
    "papers",
    "quality",
    "recent",
    "related",
    "research",
    "the",
    "to",
    "with",
}

TOPIC_ANCHOR_STOPWORDS = STOPWORDS | {
    "exclude",
    "excluding",
    "non",
    "not",
    "review",
    "reviews",
    "survey",
    "surveys",
}

METHOD_FAMILY_PHRASES = [
    "deep reinforcement learning",
    "offline reinforcement learning",
    "model based reinforcement learning",
    "model-based reinforcement learning",
    "reinforcement learning",
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "graph neural networks",
    "graph neural network",
    "neural networks",
    "neural network",
    "large language models",
    "large language model",
    "diffusion models",
    "diffusion model",
    "diffusion policy",
    "transformer",
    "transformers",
    "model predictive control",
    "adaptive control",
    "robust control",
    "learning based control",
    "learning-based control",
    "control barrier function",
    "physics informed",
    "physics-informed",
    "foundation model",
    "foundation models",
    "algorithm",
    "algorithms",
    "approach",
    "approaches",
    "framework",
    "frameworks",
    "method",
    "methods",
    "rl",
    "ai",
]

RESEARCH_MODE_RULES = [
    {
        "mode": "systematic-review",
        "spectrum": "fidelity",
        "oversight": "medium",
        "signals": ("systematic review", "meta-analysis", "meta analysis", "prisma"),
        "reason": "User asks for a systematic evidence synthesis.",
    },
    {
        "mode": "fact-check",
        "spectrum": "fidelity",
        "oversight": "medium",
        "signals": ("fact-check", "fact check", "verify claims", "evidence verification"),
        "reason": "User asks to verify claims rather than discover a broad reading list.",
    },
    {
        "mode": "guided",
        "spectrum": "originality",
        "oversight": "very-high",
        "signals": ("guide my research", "help me think", "not sure what to research", "research direction"),
        "reason": "User asks for guided research scoping before discovery.",
    },
    {
        "mode": "lit-review",
        "spectrum": "fidelity",
        "oversight": "medium",
        "signals": ("literature review", "annotated bibliography", "survey papers", "survey paper"),
        "reason": "User asks for a literature review or survey-oriented corpus.",
    },
    {
        "mode": "quick-brief",
        "spectrum": "fidelity",
        "oversight": "medium",
        "signals": ("quick brief", "quick research", "30 minute", "short summary"),
        "reason": "User asks for a compact research brief.",
    },
]

NON_REVIEW_MODE_BLOCKERS = (
    "not review",
    "no review",
    "non-review",
    "exclude review",
    "not survey",
    "no survey",
    "non-survey",
    "exclude survey",
)

QUERY_PLAN_DIAGNOSTICS_SCHEMA_VERSION = "paper-source-query-plan-diagnostics-v1"


def _as_terms(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    terms: list[str] = []
    for value in values:
        for item in str(value).split(","):
            item = " ".join(item.strip().split())
            if item:
                terms.append(item)
    return terms


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        normalized = " ".join(str(item).lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        kept.append(str(item))
    return kept


def _topic_terms(topic: str, *, limit: int = 8) -> list[str]:
    words = [
        word
        for word in re.split(r"[^A-Za-z0-9+\-]+", topic.lower())
        if len(word) > 2 and word not in STOPWORDS
    ]
    terms: list[str] = []
    for width in (3, 2):
        for index in range(0, max(0, len(words) - width + 1)):
            terms.append(" ".join(words[index : index + width]))
    terms.extend(words)
    return unique(terms)[:limit]


def topic_focus_terms(topic: str, *, limit: int = 8) -> list[str]:
    return _topic_terms(topic, limit=limit)


def infer_research_mode(topic: str) -> dict[str, Any]:
    lowered = topic.lower()
    non_review_requested = any(phrase in lowered for phrase in NON_REVIEW_MODE_BLOCKERS)
    for rule in RESEARCH_MODE_RULES:
        if non_review_requested and rule["mode"] in {"lit-review", "systematic-review"}:
            continue
        signals = [signal for signal in rule["signals"] if signal in lowered]
        if signals:
            return {
                "schema_version": "paper-source-research-mode-v1",
                "mode": rule["mode"],
                "spectrum": rule["spectrum"],
                "oversight": rule["oversight"],
                "signals": signals,
                "reason": rule["reason"],
            }
    return {
        "schema_version": "paper-source-research-mode-v1",
        "mode": "targeted-discovery",
        "spectrum": "balanced",
        "oversight": "medium",
        "signals": [],
        "reason": "Default Paper Source mode for profile-driven paper discovery and ranking.",
    }


def _remove_method_family_phrases(topic: str) -> str:
    lowered = f" {topic.lower()} "
    for phrase in sorted(METHOD_FAMILY_PHRASES, key=len, reverse=True):
        pattern = r"(?<![a-z0-9])" + re.escape(phrase).replace(r"\ ", r"[\s\-]+") + r"(?![a-z0-9])"
        lowered = re.sub(pattern, " ", lowered)
    return lowered


def _is_method_family_phrase(term: str) -> bool:
    normalized = " ".join(term.lower().replace("-", " ").split())
    method_phrases = {" ".join(phrase.lower().replace("-", " ").split()) for phrase in METHOD_FAMILY_PHRASES}
    return normalized in method_phrases


def _configured_domain_terms_in_topic(configured_domains: list[str], topic: str) -> list[str]:
    topic_words = set(
        word
        for word in re.split(r"[^a-z0-9+\-]+", topic.lower())
        if word
    )
    matched: list[str] = []
    for term in configured_domains:
        if _is_method_family_phrase(term):
            continue
        normalized = term.lower()
        tokens = [token for token in re.split(r"[^a-z0-9+\-]+", normalized) if token]
        if not tokens:
            continue
        if normalized in topic.lower() or all(token in topic_words for token in tokens):
            matched.append(term)
    return matched


def _topic_domain_anchor_terms(topic: str, *, limit: int = 4) -> list[str]:
    residual = _remove_method_family_phrases(topic)
    words = [
        word
        for word in re.split(r"[^a-z0-9+\-]+", residual)
        if len(word) > 2 and word not in TOPIC_ANCHOR_STOPWORDS
    ]
    if not words:
        return []
    terms: list[str] = []
    for width in (3, 2):
        for index in range(0, max(0, len(words) - width + 1)):
            terms.append(" ".join(words[index : index + width]))
    if not terms:
        terms.extend(words)
    return unique(terms)[:limit]


def _query_term_candidates(items: list[str], *, limit: int = 4) -> list[str]:
    skipped = {
        "latest",
        "high quality",
        "recent",
        "last 5 years",
        "past 5 years",
        "open source code",
        "source code",
        "reproducible code",
    }
    kept: list[str] = []
    for item in items:
        term = " ".join(str(item).strip().split())
        normalized = term.lower()
        if not term or normalized in skipped:
            continue
        if normalized.startswith("latest ") or normalized.startswith("high quality "):
            continue
        kept.append(term)
    return unique(kept)[:limit]


def _profile_terms(profile: str, domains: list[str] | None, positive_keywords: list[str] | None) -> list[str]:
    profile_text = profile.replace("_", " ").replace("-", " ").strip()
    profile_items = [profile_text] if profile_text and profile_text != "general academic research" else []
    return unique(profile_items + _as_terms(domains) + _as_terms(positive_keywords))


def _quality_evidence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "quality_evidence_terms",
        "benchmark_terms",
        "validation_terms",
        "evidence_terms",
        "quality_signals",
        "reproducibility_terms",
        "code_data_terms",
        "paper_type_rules",
        "paper_types",
    )
    return {key: payload[key] for key in keys if payload.get(key)}


def _term_key(term: object) -> str:
    return " ".join(str(term or "").strip().split())


def _add_provenance_detail(
    detail: dict[str, list[dict[str, str]]],
    terms: list[str],
    *,
    source: str,
    field: str,
    role: str,
) -> None:
    for raw_term in terms:
        term = _term_key(raw_term)
        if not term:
            continue
        entries = detail.setdefault(term, [])
        entry = {"source": source, "field": field, "role": role}
        if entry not in entries:
            entries.append(entry)


def add_term_provenance_detail(
    plan: dict[str, Any],
    terms: list[str],
    *,
    source: str,
    field: str,
    role: str,
) -> None:
    detail = plan.get("term_provenance_detail") if isinstance(plan.get("term_provenance_detail"), dict) else {}
    _add_provenance_detail(detail, terms, source=source, field=field, role=role)
    plan["term_provenance_detail"] = detail


def _term_provenance_sources(detail: dict[str, list[dict[str, str]]]) -> list[str]:
    sources = {
        str(entry.get("source"))
        for entries in detail.values()
        for entry in entries
        if isinstance(entry, dict) and entry.get("source")
    }
    return sorted(sources)


def _query_text_fingerprint(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"(?<![a-z0-9])-(review|survey)(?![a-z0-9])", " ", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _looks_complex_natural_language_request(topic: str) -> bool:
    lowered = topic.lower()
    token_count = len(re.findall(r"[a-z0-9]+", lowered))
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in topic)
    signals = [
        "latest",
        "recent",
        "high quality",
        "public code",
        "code preferred",
        "last five",
        "past five",
        " or ",
        " and ",
        "not review",
        "non-review",
        "综述",
        "公开代码",
        "近",
    ]
    return has_cjk or token_count >= 8 or sum(1 for signal in signals if signal in lowered) >= 2


def build_query_plan_diagnostics(plan: dict[str, Any], topic: str) -> dict[str, Any]:
    variants = [str(query).strip() for query in plan.get("query_variants") or [] if str(query).strip()]
    topic_fingerprint = _query_text_fingerprint(topic)
    raw_query_variant = bool(topic_fingerprint) and any(
        _query_text_fingerprint(variant) == topic_fingerprint for variant in variants
    )
    blocks = plan.get("concept_blocks") if isinstance(plan.get("concept_blocks"), dict) else {}
    hard_anchors = [str(term) for term in blocks.get("hard_domain_anchors") or [] if str(term).strip()]
    soft_recall = [
        str(term)
        for term in (plan.get("soft_recall_terms") or blocks.get("soft_recall_terms") or [])
        if str(term).strip()
    ]
    detail = plan.get("term_provenance_detail") if isinstance(plan.get("term_provenance_detail"), dict) else {}
    complex_request = _looks_complex_natural_language_request(topic)
    warnings: list[str] = []
    if complex_request and len(variants) < 2:
        warnings.append("complex_request_has_too_few_query_variants")
    if complex_request and raw_query_variant and len(variants) <= 1:
        warnings.append("raw_query_used_as_primary_variant")
    if complex_request and not hard_anchors and not soft_recall:
        warnings.append("complex_request_missing_query_anchors")
    if not detail:
        warnings.append("missing_term_provenance_detail")
    return {
        "schema_version": QUERY_PLAN_DIAGNOSTICS_SCHEMA_VERSION,
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "complex_natural_language_request": complex_request,
        "query_variant_count": len(variants),
        "raw_query_variant": raw_query_variant,
        "hard_domain_anchor_count": len(hard_anchors),
        "soft_recall_term_count": len(soft_recall),
        "term_provenance_sources": _term_provenance_sources(detail),
        "policy": "Raw natural-language queries should be intent labels; complex requests should use explicit academic query variants and recorded hard/soft terms.",
    }


def refresh_query_plan_diagnostics(plan: dict[str, Any], topic: str | None = None) -> None:
    plan["diagnostics"] = build_query_plan_diagnostics(plan, topic or str(plan.get("topic") or ""))


def choose_domain(
    topic: str,
    requested: str,
    *,
    profile_terms: list[str] | None = None,
) -> str:
    if requested not in {"auto", "profile"}:
        raise ValueError(f"unknown domain: {requested}")
    if requested == "profile" or profile_terms:
        return "profile-derived"
    return "topic-derived"


def quote(term: str) -> str:
    if " " in term and not term.startswith('"'):
        return f'"{term}"'
    return term


def with_exclusion(query: str, non_review: bool) -> str:
    return f"{query} -review -survey" if non_review else query


def _combine_terms(*terms: str) -> str:
    return " ".join(quote(term) for term in terms if term)


def _fallback_first(items: list[str], fallback: str) -> str:
    return items[0] if items else fallback


def build_queries(blocks: dict[str, list[str]], topic: str, non_review: bool, max_queries: int) -> list[str]:
    domain_terms = _query_term_candidates(blocks["domain_terms"], limit=4)
    method_terms = _query_term_candidates(blocks["method_or_topic_terms"], limit=5)
    problem_terms = _query_term_candidates(blocks["problem_terms"], limit=5)
    context_terms = _query_term_candidates(blocks["context_terms"], limit=3)
    quality_signals = _query_term_candidates(blocks["quality_signals"], limit=5)

    primary_domain = _fallback_first(domain_terms, topic)
    primary_method = _fallback_first(method_terms, topic)
    primary_problem = _fallback_first(problem_terms, topic)
    primary_context = _fallback_first(context_terms, "experiment")
    primary_quality = _fallback_first(quality_signals, "benchmark")
    secondary_domain = domain_terms[1] if len(domain_terms) > 1 else primary_domain
    secondary_method = method_terms[1] if len(method_terms) > 1 else primary_method
    secondary_problem = problem_terms[1] if len(problem_terms) > 1 else primary_problem

    raw = [
        _combine_terms(primary_domain, primary_problem, primary_method),
        _combine_terms(secondary_domain, primary_problem, primary_method),
        _combine_terms(primary_domain, secondary_problem, primary_method),
        _combine_terms(primary_domain, primary_problem, secondary_method),
        _combine_terms(primary_domain, primary_method, primary_quality),
        _combine_terms(primary_domain, primary_problem, primary_context),
        _combine_terms(primary_domain, primary_problem, "benchmark"),
        _combine_terms(primary_domain, primary_problem, "experiment"),
    ]
    return unique([with_exclusion(query, non_review) for query in raw if query.strip()])[:max_queries]


def _term_blocks(
    *,
    topic: str,
    chosen_domain: str,
    profile: str,
    domains: list[str] | None,
    positive_keywords: list[str] | None,
    negative_keywords: list[str] | None,
) -> dict[str, list[str]]:
    topic_terms = _topic_terms(topic)
    profile_seed_terms = _profile_terms(profile, domains, positive_keywords)

    configured_domains = _as_terms(domains)
    topic_domain_terms = _configured_domain_terms_in_topic(configured_domains, topic)
    topic_anchor_terms = _topic_domain_anchor_terms(topic)
    hard_domain_anchors = unique(topic_domain_terms)
    soft_recall_terms = unique(topic_anchor_terms)
    domain_focus_terms = hard_domain_anchors

    domain_terms = unique(hard_domain_anchors + soft_recall_terms + configured_domains)
    if not domain_terms:
        domain_terms = topic_terms[:3]

    method_or_topic_terms = unique(
        _as_terms(positive_keywords)
        + topic_terms
    )
    problem_terms = unique(topic_terms)
    context_terms = unique(GENERIC_CONTEXT_TERMS)
    quality_signals = unique(GENERIC_QUALITY_SIGNALS)
    exclusions = unique(_as_terms(negative_keywords))
    return {
        "profile_terms": profile_seed_terms,
        "domain_terms": domain_terms,
        "domain_focus_terms": domain_focus_terms,
        "hard_domain_anchors": hard_domain_anchors,
        "soft_recall_terms": soft_recall_terms,
        "method_or_topic_terms": method_or_topic_terms,
        "problem_terms": problem_terms,
        "context_terms": context_terms,
        "quality_signals": quality_signals,
        "exclusions": exclusions,
    }


def build_query_plan(
    topic: str,
    domain: str = "auto",
    non_review: bool | None = None,
    max_queries: int = 8,
    profile: str = "general_academic_research",
    domains: list[str] | None = None,
    positive_keywords: list[str] | None = None,
    negative_keywords: list[str] | None = None,
    venue_prior: list[str] | None = None,
) -> dict[str, Any]:
    profile_seed_terms = _profile_terms(profile, domains, positive_keywords)
    chosen = choose_domain(topic, domain, profile_terms=profile_seed_terms)
    exclude_reviews = bool(default_discovery_exclusion_terms(topic)) if non_review is None else non_review
    blocks = _term_blocks(
        topic=topic,
        chosen_domain=chosen,
        profile=profile,
        domains=domains,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
    )
    if exclude_reviews:
        blocks["exclusions"] = unique(blocks["exclusions"] + ["review", "survey"])
    required_concept_groups = derive_required_concept_groups(
        hard_domain_anchors=blocks["hard_domain_anchors"],
        task_terms=_as_terms(positive_keywords),
        topic=topic,
        source="config_and_user_request",
    )
    if required_concept_groups:
        blocks["required_concept_groups"] = required_concept_groups

    configured_venues = _as_terms(venue_prior)
    venue_families = unique(configured_venues)
    if not venue_families:
        venue_families = ["profile-configured venue_prior", "field-specific top venues"]

    provenance_detail: dict[str, list[dict[str, str]]] = {}
    _add_provenance_detail(
        provenance_detail,
        _as_terms(domains),
        source="config",
        field="domains",
        role="profile_domain",
    )
    _add_provenance_detail(
        provenance_detail,
        _as_terms(positive_keywords),
        source="config",
        field="positive_keywords",
        role="profile_positive_keyword",
    )
    _add_provenance_detail(
        provenance_detail,
        _as_terms(negative_keywords),
        source="config",
        field="negative_keywords",
        role="exclusion",
    )
    _add_provenance_detail(
        provenance_detail,
        configured_venues,
        source="config",
        field="venue_prior",
        role="venue_prior",
    )
    _add_provenance_detail(
        provenance_detail,
        blocks["hard_domain_anchors"],
        source="user_request",
        field="topic",
        role="hard_anchor",
    )
    _add_provenance_detail(
        provenance_detail,
        blocks["soft_recall_terms"],
        source="user_request",
        field="topic",
        role="soft_recall",
    )
    _add_provenance_detail(
        provenance_detail,
        _topic_terms(topic),
        source="user_request",
        field="topic",
        role="topic_term",
    )

    plan = {
        "workflow": "paper-source-query-plan",
        "topic": topic,
        "research_mode": infer_research_mode(topic),
        "domain": chosen,
        "profile": {
            "name": profile,
            "domains": _as_terms(domains),
            "positive_keywords": _as_terms(positive_keywords),
            "negative_keywords": _as_terms(negative_keywords),
            "venue_prior": configured_venues,
            "derivation": "config/profile-first; topic terms fill gaps",
        },
        "concept_blocks": blocks,
        "query_variants": build_queries(blocks, topic, exclude_reviews, max(1, max_queries)),
        "source_route": {
            "t1": ["paper_search_mcp", "arxiv", "semantic", "openalex", "crossref"],
            "t2": ["official venue pages", "publisher DOI pages", "field-specific indexes"],
            "t3": ["citation graph", "lab/project pages", "profile-specific curated venue lists"],
        },
        "recall_gap_checks": {
            "venue_families": venue_families,
            "profile_terms": blocks["profile_terms"],
            "citation_graph": ["journal version", "recent cited-by", "references", "related papers"],
            "library_dedup": ["DOI", "arXiv ID", "normalized title", "title+first-author+year"],
        },
        "quality_signals": blocks["quality_signals"],
        "hard_constraints": {
            "domain_anchors": blocks["hard_domain_anchors"],
            "policy": "Only config/Research Brief/user-confirmed anchors are hard filters; topic-derived n-grams are soft recall terms.",
        },
        "soft_recall_terms": blocks["soft_recall_terms"],
        "term_provenance": {
            **{term: "config_domain_matched_in_topic" for term in blocks["hard_domain_anchors"]},
            **{term: "topic_inferred_soft_recall" for term in blocks["soft_recall_terms"]},
            **{term: "config_positive_keyword" for term in _as_terms(positive_keywords)},
            **{term: "config_negative_keyword" for term in _as_terms(negative_keywords)},
            **{term: "config_venue_prior" for term in configured_venues},
        },
        "term_provenance_detail": provenance_detail,
    }
    if required_concept_groups:
        plan["required_concept_groups"] = required_concept_group_contract(required_concept_groups)
        plan["hard_constraints"]["required_concept_groups"] = required_concept_groups
    refresh_query_plan_diagnostics(plan, topic)
    return plan


def build_query_plan_from_research_brief(
    brief: dict[str, Any],
    *,
    max_queries: int = 8,
    profile: str = "general_academic_research",
    domains: list[str] | None = None,
    positive_keywords: list[str] | None = None,
    negative_keywords: list[str] | None = None,
    venue_prior: list[str] | None = None,
) -> dict[str, Any]:
    topic = str(brief.get("task") or "").strip()
    domain_scope = str(brief.get("domain_scope") or "").strip()
    keywords = _as_terms(brief.get("keywords") or [])
    questions = _as_terms(brief.get("specific_questions") or [])
    exclusions = _as_terms(brief.get("exclusions") or [])
    review_policy = brief.get("review_policy") if isinstance(brief.get("review_policy"), dict) else {}
    review_policy_type = str(review_policy.get("type") or "exclude")
    non_review = review_policy_type == "exclude"
    source_scope = brief.get("source_scope") if isinstance(brief.get("source_scope"), dict) else {}
    output_goal = brief.get("output_goal") if isinstance(brief.get("output_goal"), dict) else {}

    plan = build_query_plan(
        topic=topic,
        domain="profile",
        non_review=non_review,
        max_queries=max_queries,
        profile=profile,
        domains=domains,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
        venue_prior=venue_prior,
    )
    blocks = plan["concept_blocks"]
    blocks["domain_terms"] = unique(([domain_scope] if domain_scope else []) + _as_terms(domains) + blocks["domain_terms"])
    blocks["domain_focus_terms"] = unique(([domain_scope] if domain_scope else []) + blocks.get("domain_focus_terms", []))
    blocks["hard_domain_anchors"] = unique(([domain_scope] if domain_scope else []) + blocks.get("hard_domain_anchors", []))
    blocks["method_or_topic_terms"] = unique(keywords + blocks["method_or_topic_terms"])
    blocks["problem_terms"] = unique(questions + blocks["problem_terms"])
    blocks["exclusions"] = unique(exclusions + blocks["exclusions"])
    required_concept_groups = derive_required_concept_groups(
        hard_domain_anchors=blocks["hard_domain_anchors"],
        task_terms=keywords + questions,
        topic=topic,
        source="research_brief",
    )
    if required_concept_groups:
        blocks["required_concept_groups"] = required_concept_groups
    if non_review:
        blocks["exclusions"] = unique(blocks["exclusions"] + ["review", "survey"])
    plan["domain"] = "research-brief"
    plan["query_variants"] = build_queries(blocks, topic, non_review, max(1, max_queries))
    plan["hard_constraints"] = {
        "domain_anchors": blocks["hard_domain_anchors"],
        "policy": "Research Brief domain_scope is a confirmed hard anchor when present.",
    }
    if required_concept_groups:
        plan["required_concept_groups"] = required_concept_group_contract(required_concept_groups)
        plan["hard_constraints"]["required_concept_groups"] = required_concept_groups
    plan["soft_recall_terms"] = blocks.get("soft_recall_terms", [])
    provenance = plan.get("term_provenance") if isinstance(plan.get("term_provenance"), dict) else {}
    if domain_scope:
        provenance[domain_scope] = "research_brief_domain_scope"
    for term in blocks.get("soft_recall_terms", []):
        provenance.setdefault(term, "topic_inferred_soft_recall")
    plan["term_provenance"] = provenance
    add_term_provenance_detail(
        plan,
        [domain_scope] if domain_scope else [],
        source="research_brief",
        field="domain_scope",
        role="hard_anchor",
    )
    add_term_provenance_detail(
        plan,
        keywords,
        source="research_brief",
        field="keywords",
        role="method_or_topic",
    )
    add_term_provenance_detail(
        plan,
        questions,
        source="research_brief",
        field="specific_questions",
        role="problem",
    )
    add_term_provenance_detail(
        plan,
        exclusions,
        source="research_brief",
        field="exclusions",
        role="exclusion",
    )
    quality_evidence = _quality_evidence_payload(brief)
    if quality_evidence:
        plan["quality_evidence_terms"] = quality_evidence
    plan["research_brief"] = {
        "slug": brief.get("slug"),
        "status": brief.get("status"),
        "revision_number": brief.get("revision_number"),
        "review_policy": review_policy_type,
        "source_scope": source_scope.get("type"),
        "output_goal": output_goal.get("type"),
        "precedence": "brief_overrides_profile",
    }
    refresh_query_plan_diagnostics(plan, topic)
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a deterministic Paper Source paper discovery query plan.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--domain", default="auto", choices=["auto", "profile"])
    parser.add_argument("--profile", default="general_academic_research")
    parser.add_argument("--domains", default="", help="Comma-separated user profile domains.")
    parser.add_argument("--positive-keywords", default="", help="Comma-separated profile fit terms.")
    parser.add_argument("--negative-keywords", default="", help="Comma-separated exclusion/demotion terms.")
    parser.add_argument("--venue-prior", default="", help="Comma-separated configured venue priors.")
    review_mode = parser.add_mutually_exclusive_group()
    review_mode.add_argument("--non-review", dest="non_review", action="store_true")
    review_mode.add_argument("--include-reviews", dest="non_review", action="store_false")
    parser.set_defaults(non_review=None)
    parser.add_argument("--max-queries", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_query_plan(
        topic=args.topic,
        domain=args.domain,
        non_review=args.non_review,
        max_queries=args.max_queries,
        profile=args.profile,
        domains=_as_terms(args.domains.split(",")),
        positive_keywords=_as_terms(args.positive_keywords.split(",")),
        negative_keywords=_as_terms(args.negative_keywords.split(",")),
        venue_prior=_as_terms(args.venue_prior.split(",")),
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
