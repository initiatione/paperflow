from __future__ import annotations

import argparse
import json
import re
from typing import Any

from epi.filter_candidates import default_discovery_exclusion_terms


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


DOMAIN_HINT_PACKS: dict[str, dict[str, Any]] = {
    "auv-control": {
        "detect": ["auv", "underwater", "marine", "ocean"],
        "domain_terms": [
            "AUV",
            "autonomous underwater vehicle",
            "unmanned underwater vehicle",
            "underwater robot",
        ],
        "method_terms": [
            "reinforcement learning",
            "offline reinforcement learning",
            "model-based reinforcement learning",
            "adaptive control",
            "safety-critical control",
        ],
        "problem_terms": [
            "trajectory tracking",
            "path following",
            "stabilization",
            "station keeping",
        ],
        "context_terms": [
            "ocean current",
            "current disturbance",
            "underwater disturbance",
            "turbulence",
        ],
        "quality_signals": ["sea trial", "field trial", "real AUV", "sim-to-real", "benchmark"],
        "exclude": ["acoustic communication", "underwater sensor network"],
        "venues": [
            "Ocean Engineering",
            "IEEE Journal of Oceanic Engineering",
            "Applied Ocean Research",
            "Control Engineering Practice",
            "OCEANS",
        ],
    },
    "embodied-ai": {
        "detect": ["embodied", "vla", "world model", "foundation model", "diffusion policy"],
        "domain_terms": ["embodied agent", "robot system", "manipulator", "mobile robot"],
        "method_terms": [
            "world model",
            "foundation model",
            "vision language action",
            "diffusion policy",
            "imitation learning",
            "reinforcement learning",
        ],
        "problem_terms": ["manipulation", "navigation", "planning", "long-horizon task"],
        "context_terms": ["sim-to-real", "real robot", "benchmark"],
        "quality_signals": ["real robot", "open-source code", "dataset", "ablation", "benchmark"],
        "exclude": ["position paper", "pure LLM benchmark"],
        "venues": ["CoRL", "RSS", "ICRA", "IROS", "NeurIPS", "ICML", "ICLR", "RA-L"],
    },
    "general-robotics": {
        "detect": ["robot", "robotic", "navigation", "motion control"],
        "domain_terms": ["robot", "robotic system", "autonomous system"],
        "method_terms": [
            "model predictive control",
            "adaptive control",
            "robust control",
            "learning-based control",
            "control barrier function",
        ],
        "problem_terms": ["trajectory tracking", "path planning", "motion planning", "navigation"],
        "context_terms": ["disturbance", "uncertainty", "real-world"],
        "quality_signals": ["hardware experiment", "benchmark", "safety guarantee"],
        "exclude": ["tutorial", "editorial"],
        "venues": ["TRO", "IJRR", "RA-L", "ICRA", "IROS", "RSS", "CoRL"],
    },
}


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
                "schema_version": "epi-research-mode-v1",
                "mode": rule["mode"],
                "spectrum": rule["spectrum"],
                "oversight": rule["oversight"],
                "signals": signals,
                "reason": rule["reason"],
            }
    return {
        "schema_version": "epi-research-mode-v1",
        "mode": "targeted-discovery",
        "spectrum": "balanced",
        "oversight": "medium",
        "signals": [],
        "reason": "Default EPI mode for profile-driven paper discovery and ranking.",
    }


def _remove_method_family_phrases(topic: str) -> str:
    lowered = f" {topic.lower()} "
    for phrase in sorted(METHOD_FAMILY_PHRASES, key=len, reverse=True):
        pattern = r"(?<![a-z0-9])" + re.escape(phrase).replace(r"\ ", r"[\s\-]+") + r"(?![a-z0-9])"
        lowered = re.sub(pattern, " ", lowered)
    return lowered


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


def _profile_terms(profile: str, domains: list[str] | None, positive_keywords: list[str] | None) -> list[str]:
    profile_text = profile.replace("_", " ").replace("-", " ").strip()
    profile_items = [profile_text] if profile_text and profile_text != "general academic research" else []
    return unique(profile_items + _as_terms(domains) + _as_terms(positive_keywords))


def choose_domain(
    topic: str,
    requested: str,
    *,
    profile_terms: list[str] | None = None,
) -> str:
    if requested not in {"auto", "profile", *DOMAIN_HINT_PACKS.keys()}:
        raise ValueError(f"unknown domain: {requested}")
    if requested == "profile":
        return "profile-derived"
    if requested != "auto":
        return requested
    if profile_terms:
        return "profile-derived"

    lowered = topic.lower()
    for name, pack in DOMAIN_HINT_PACKS.items():
        if any(marker in lowered for marker in pack["detect"]):
            return name
    return "topic-derived"


def topic_hint_pack_name(topic: str) -> str | None:
    lowered = topic.lower()
    for name, pack in DOMAIN_HINT_PACKS.items():
        if any(marker in lowered for marker in pack["detect"]):
            return name
    return None


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
    domain_terms = blocks["domain_terms"]
    method_terms = blocks["method_or_topic_terms"]
    problem_terms = blocks["problem_terms"]
    context_terms = blocks["context_terms"]
    quality_signals = blocks["quality_signals"]

    primary_domain = _fallback_first(domain_terms, topic)
    primary_method = _fallback_first(method_terms, topic)
    primary_problem = _fallback_first(problem_terms, topic)
    primary_context = _fallback_first(context_terms, "evaluation")
    primary_quality = _fallback_first(quality_signals, "benchmark")

    raw = [
        topic,
        _combine_terms(primary_domain, primary_method, primary_problem),
        _combine_terms(primary_domain, primary_method, primary_quality),
        _combine_terms(topic, primary_quality),
        _combine_terms(primary_method, primary_problem, primary_context),
        _combine_terms(primary_domain, primary_problem, "dataset"),
        _combine_terms(topic, "DOI"),
        _combine_terms(topic, "code", "benchmark"),
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
    hint_pack = DOMAIN_HINT_PACKS.get(chosen_domain, {})
    topic_hint_pack = DOMAIN_HINT_PACKS.get(topic_hint_pack_name(topic) or "", {})

    configured_domains = _as_terms(domains)
    topic_domain_terms = [
        term
        for term in configured_domains
        if any(marker in term.lower() for marker in topic_hint_pack.get("detect", []))
    ]
    topic_anchor_terms = [] if topic_hint_pack else _topic_domain_anchor_terms(topic)
    domain_focus_terms = unique(
        topic_domain_terms
        + topic_anchor_terms
        + topic_hint_pack.get("domain_terms", [])
    )

    domain_terms = unique(domain_focus_terms + configured_domains + hint_pack.get("domain_terms", []))
    if not domain_terms:
        domain_terms = topic_terms[:3]

    method_or_topic_terms = unique(
        topic_hint_pack.get("method_terms", [])
        + _as_terms(positive_keywords)
        + hint_pack.get("method_terms", [])
        + topic_terms
    )
    problem_terms = unique(topic_hint_pack.get("problem_terms", []) + hint_pack.get("problem_terms", []) + topic_terms)
    context_terms = unique(topic_hint_pack.get("context_terms", []) + hint_pack.get("context_terms", []) + GENERIC_CONTEXT_TERMS)
    quality_signals = unique(topic_hint_pack.get("quality_signals", []) + hint_pack.get("quality_signals", []) + GENERIC_QUALITY_SIGNALS)
    exclusions = unique(_as_terms(negative_keywords) + topic_hint_pack.get("exclude", []) + hint_pack.get("exclude", []))
    return {
        "profile_terms": profile_seed_terms,
        "domain_terms": domain_terms,
        "domain_focus_terms": domain_focus_terms,
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

    hint_pack = DOMAIN_HINT_PACKS.get(chosen, {})
    topic_hint_pack = DOMAIN_HINT_PACKS.get(topic_hint_pack_name(topic) or "", {})
    configured_venues = _as_terms(venue_prior)
    venue_families = unique(configured_venues + topic_hint_pack.get("venues", []) + hint_pack.get("venues", []))
    if not venue_families:
        venue_families = ["profile-configured venue_prior", "field-specific top venues"]

    return {
        "workflow": "epi-query-plan",
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
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a deterministic EPI paper discovery query plan.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--domain", default="auto", choices=["auto", "profile", *DOMAIN_HINT_PACKS.keys()])
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
