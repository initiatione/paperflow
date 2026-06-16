from __future__ import annotations

import json
from pathlib import Path

from paper_source.artifacts import read_json
from paper_source.filter_candidates import default_discovery_exclusion_terms
from paper_source.query_planner import build_query_plan, infer_research_mode, topic_focus_terms

CODE_POLICIES = {"ignore", "prefer", "require"}


def build_dry_run_query_plan(query: str, *, domain: str, max_queries: int, config, non_review: bool | None = None) -> dict:
    return build_query_plan(
        topic=query,
        domain=domain,
        max_queries=max(1, max_queries),
        profile=config.profile,
        domains=config.domains,
        positive_keywords=config.positive_keywords,
        negative_keywords=config.negative_keywords,
        venue_prior=config.venue_prior,
        non_review=non_review,
    )


def unique_nonempty_strings(values: list[str] | None, *, split_commas: bool = False) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        candidates = str(value).split(",") if split_commas else [str(value)]
        for candidate in candidates:
            item = " ".join(candidate.strip().split())
            normalized = item.lower()
            if not item or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(item)
    return kept


def normalize_year_min(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("year_min must be an integer year")
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"year_min must be an integer year: {value}") from exc
    if year < 1000 or year > 9999:
        raise ValueError(f"year_min must be a four-digit year: {value}")
    return year


def normalize_code_policy(value: object) -> str | None:
    if value is None or value == "":
        return None
    policy = str(value).strip().lower()
    if policy not in CODE_POLICIES:
        raise ValueError(f"unknown code_policy: {value}")
    return policy


def request_constraints_payload(year_min: int | None, code_policy: str | None) -> dict:
    payload: dict[str, object] = {}
    if year_min is not None:
        payload["year_min"] = year_min
    if code_policy is not None:
        payload["code_policy"] = code_policy
    return payload


def load_agent_query_plan_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent query plan JSON is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("agent query plan JSON must be an object")
    list_fields = (
        "query_variants",
        "domain_focus_terms",
        "must_have_domain_anchors",
        "hard_domain_anchors",
        "soft_recall_terms",
        "exclusions",
        "ambiguities",
    )
    for key in list_fields:
        value = payload.get(key)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"agent query plan field must be a list: {key}")
    hard_constraints = payload.get("hard_constraints")
    if hard_constraints is not None and not isinstance(hard_constraints, (dict, list)):
        raise ValueError("agent query plan field must be an object or list: hard_constraints")
    for key in ("term_provenance", "confidence"):
        value = payload.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"agent query plan field must be an object: {key}")
    return payload


def agent_plan_strings(payload: dict | None, *keys: str, split_commas: bool = False) -> list[str]:
    if not payload:
        return []
    values: list[str] = []
    for key in keys:
        raw_value = payload.get(key)
        if isinstance(raw_value, str):
            values.append(raw_value)
        elif isinstance(raw_value, list):
            values.extend(str(item) for item in raw_value)
    return unique_nonempty_strings(values, split_commas=split_commas)


def agent_plan_constraint(payload: dict | None, key: str) -> object:
    if not payload:
        return None
    if key in payload:
        return payload.get(key)
    for container_key in ("constraints", "request_constraints"):
        container = payload.get(container_key)
        if isinstance(container, dict) and key in container:
            return container.get(key)
    return None


def _constraint_terms(payload: object, *keys: str, split_commas: bool = True) -> list[str]:
    terms: list[str] = []
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str):
                terms.append(value)
            elif isinstance(value, list):
                terms.extend(str(item) for item in value)
        constraints = payload.get("constraints")
        if isinstance(constraints, dict):
            terms.extend(_constraint_terms(constraints, *keys, split_commas=split_commas))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                terms.append(item)
            elif isinstance(item, dict):
                terms.extend(_constraint_terms(item, *keys, split_commas=split_commas))
    return unique_nonempty_strings(terms, split_commas=split_commas)


def agent_plan_hard_domain_anchors(payload: dict | None) -> list[str]:
    if not payload:
        return []
    return unique_nonempty_strings(
        agent_plan_strings(payload, "hard_domain_anchors", "must_have_domain_anchors", split_commas=True)
        + _constraint_terms(
            payload.get("hard_constraints"),
            "domain_focus_terms",
            "domain_anchors",
            "hard_domain_anchors",
            "must_have_domain_anchors",
            split_commas=True,
        ),
        split_commas=True,
    )


def agent_plan_soft_recall_terms(payload: dict | None) -> list[str]:
    if not payload:
        return []
    return unique_nonempty_strings(
        agent_plan_strings(payload, "soft_recall_terms", "recall_terms", "expanded_terms", split_commas=True)
        + agent_plan_strings(payload, "domain_focus_terms", split_commas=True),
        split_commas=True,
    )


def _merge_term_provenance(plan: dict, terms: list[str], source: str) -> None:
    if not terms:
        return
    provenance = plan.get("term_provenance") if isinstance(plan.get("term_provenance"), dict) else {}
    for term in terms:
        provenance.setdefault(term, source)
    plan["term_provenance"] = provenance


def _minimal_agent_supplied_query_plan(query: str, *, config) -> dict:
    focus_terms = topic_focus_terms(query)
    profile_terms = unique_nonempty_strings(
        [config.profile.replace("_", " ").replace("-", " ")] + list(config.domains) + list(config.positive_keywords)
    )
    domain_terms = unique_nonempty_strings(list(config.domains))
    method_terms = unique_nonempty_strings(list(config.positive_keywords) + focus_terms)
    exclusions = default_discovery_exclusion_terms(query)
    return {
        "workflow": "paper-source-query-plan",
        "topic": query,
        "research_mode": infer_research_mode(query),
        "domain": "agent-supplied",
        "profile": {
            "name": config.profile,
            "domains": list(config.domains),
            "positive_keywords": list(config.positive_keywords),
            "negative_keywords": list(config.negative_keywords),
            "venue_prior": list(config.venue_prior),
            "derivation": "agent-supplied query plan; script records and executes explicit terms",
        },
        "concept_blocks": {
            "profile_terms": profile_terms,
            "domain_terms": domain_terms,
            "domain_focus_terms": [],
            "hard_domain_anchors": [],
            "soft_recall_terms": [],
            "method_or_topic_terms": method_terms,
            "problem_terms": focus_terms,
            "context_terms": [],
            "quality_signals": [],
            "exclusions": exclusions,
        },
        "query_variants": [query],
        "source_route": {
            "t1": ["paper_search_mcp", "arxiv", "semantic", "openalex", "crossref", "unpaywall"],
            "t2": ["official venue pages", "publisher DOI pages", "field-specific indexes"],
            "t3": ["citation graph", "lab/project pages", "profile-specific curated venue lists"],
        },
        "recall_gap_checks": {
            "venue_families": list(config.venue_prior) or ["profile-configured venue_prior", "field-specific top venues"],
            "profile_terms": profile_terms,
            "citation_graph": ["journal version", "recent cited-by", "references", "related papers"],
            "library_dedup": ["DOI", "arXiv ID", "normalized title", "title+first-author+year"],
        },
        "quality_signals": [],
    }


def apply_agent_supplied_query_inputs(
    query_plan: dict | None,
    *,
    query: str,
    config,
    query_variants: list[str],
    domain_focus_terms: list[str],
    agent_query_plan: dict | None = None,
    agent_query_plan_path: Path | None = None,
    year_min: int | None = None,
    code_policy: str | None = None,
) -> dict:
    plan = query_plan or _minimal_agent_supplied_query_plan(query, config=config)
    blocks = plan.setdefault("concept_blocks", {})
    plan_blocks = agent_query_plan.get("concept_blocks") if isinstance(agent_query_plan, dict) else None
    if isinstance(plan_blocks, dict):
        for key, value in plan_blocks.items():
            if isinstance(value, list):
                target_key = "soft_recall_terms" if key == "domain_focus_terms" else key
                blocks[target_key] = unique_nonempty_strings(
                    [str(item) for item in value] + list(blocks.get(target_key) or [])
                )
    hard_domain_anchors = unique_nonempty_strings(
        domain_focus_terms + agent_plan_hard_domain_anchors(agent_query_plan),
        split_commas=True,
    )
    soft_recall_terms = agent_plan_soft_recall_terms(agent_query_plan)
    if hard_domain_anchors:
        blocks["hard_domain_anchors"] = hard_domain_anchors
        blocks["domain_focus_terms"] = unique_nonempty_strings(
            hard_domain_anchors + list(blocks.get("domain_focus_terms") or []),
            split_commas=True,
        )
        blocks["domain_terms"] = unique_nonempty_strings(hard_domain_anchors + list(blocks.get("domain_terms") or []))
    if soft_recall_terms:
        blocks["soft_recall_terms"] = unique_nonempty_strings(
            soft_recall_terms + list(blocks.get("soft_recall_terms") or []),
            split_commas=True,
        )
    _merge_term_provenance(plan, domain_focus_terms, "cli_explicit_hard_anchor")
    _merge_term_provenance(plan, agent_plan_hard_domain_anchors(agent_query_plan), "agent_explicit_hard_anchor")
    _merge_term_provenance(plan, list(blocks.get("soft_recall_terms") or []), "agent_or_topic_soft_recall")
    if query_variants:
        plan["query_variants"] = query_variants
        plan["query_variants_source"] = "agent_supplied"
    if hard_domain_anchors:
        plan["domain_focus_terms_source"] = "explicit_hard_anchor"
    request_constraints = request_constraints_payload(year_min, code_policy)
    if request_constraints:
        plan["request_constraints"] = {
            **request_constraints,
            "source": "agent_supplied" if agent_query_plan or query_variants or domain_focus_terms else "cli",
        }
    plan["hard_constraints"] = {
        "domain_anchors": hard_domain_anchors,
        "policy": "Only user/config/Research Brief/confirmed anchors should be passed here; inferred terms stay soft.",
    }
    plan["soft_recall_terms"] = list(blocks.get("soft_recall_terms") or [])
    if isinstance(agent_query_plan, dict):
        if isinstance(agent_query_plan.get("ambiguities"), list):
            plan["ambiguities"] = [str(item) for item in agent_query_plan.get("ambiguities") or []]
        if isinstance(agent_query_plan.get("confidence"), dict):
            plan["confidence"] = agent_query_plan["confidence"]
        if isinstance(agent_query_plan.get("term_provenance"), dict):
            provenance = plan.get("term_provenance") if isinstance(plan.get("term_provenance"), dict) else {}
            provenance = {**agent_query_plan["term_provenance"], **provenance}
            plan["term_provenance"] = provenance
    plan["agent_supplied"] = {
        "query_variants": query_variants,
        "domain_focus_terms": domain_focus_terms,
        "hard_domain_anchors": hard_domain_anchors,
        "agent_hard_domain_anchors": agent_plan_hard_domain_anchors(agent_query_plan),
        "soft_recall_terms": list(blocks.get("soft_recall_terms") or []),
        "agent_query_plan_path": str(agent_query_plan_path) if agent_query_plan_path else None,
        "agent_query_plan": agent_query_plan or {},
        "request_constraints": request_constraints,
        "contract": "agent_plans_natural_language; script_validates_records_executes; inferred_terms_do_not_become_hard_filters",
    }
    return plan


def exact_lookup_query(source_routing: dict | None, fallback_query: str) -> str:
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if isinstance(exact_lookup, dict) and exact_lookup.get("value"):
        return str(exact_lookup["value"])
    return fallback_query


def apply_exact_lookup_query_plan(query_plan: dict, source_routing: dict | None) -> None:
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if not isinstance(exact_lookup, dict):
        return
    query_plan["research_mode"] = {
        "schema_version": "paper-source-research-mode-v1",
        "mode": "exact-lookup",
        "spectrum": "fidelity",
        "oversight": "low",
        "signals": [exact_lookup.get("kind")],
        "reason": "The user supplied a DOI, arXiv ID, or explicit title lookup; preserve the identifier instead of expanding the query.",
    }
    query_plan["query_variants"] = [exact_lookup_query(source_routing, str(query_plan.get("topic") or ""))]


def query_strategy_for_dry_run(query_plan: dict | None, fixture_path: Path | None, source_routing: dict | None) -> str:
    if fixture_path is not None or not query_plan:
        return "single_query"
    if isinstance(source_routing, dict) and isinstance(source_routing.get("exact_lookup"), dict):
        return "exact_lookup_single_query"
    return "query_plan_multi_query"
