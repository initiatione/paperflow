from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

from paper_source.artifacts import LEGACY_EPI_ROOT_NAME, PAPER_SOURCE_ROOT_NAME
from paper_source.source_artifacts import has_nonempty_mineru_tex


ROLE_LABELS = {
    "nature-sci-editor": "editor",
    "peer-reviewer": "reviewer",
    "senior-domain-researcher": "domain",
}

FORMAL_PAGE_ROOTS = (
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
)

WIKILINK_PATTERN = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)
RAW_PAPER_PATH_PATTERN = re.compile(
    rf"(?:{re.escape(PAPER_SOURCE_ROOT_NAME)}|{re.escape(LEGACY_EPI_ROOT_NAME)})/raw/(?P<slug>[^/\]\|\s)]+)/paper\.pdf",
    re.IGNORECASE,
)

INTERNAL_SOURCE_PREFIXES = (f"{PAPER_SOURCE_ROOT_NAME}/", f"{LEGACY_EPI_ROOT_NAME}/")
RAW_PAPER_URI_PATTERN = re.compile(
    rf"file=(?:{re.escape(PAPER_SOURCE_ROOT_NAME)}|{re.escape(LEGACY_EPI_ROOT_NAME)})%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf",
    re.IGNORECASE,
)


def _manifest_path(vault_path: Path) -> Path:
    return Path(vault_path).resolve() / ".manifest.json"


def _load_manifest(vault_path: Path) -> dict:
    path = _manifest_path(vault_path)
    if not path.exists():
        return {"vault_type": "academic-paper-research", "papers": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"vault_type": "academic-paper-research", "papers": []}
    if not isinstance(payload, dict):
        return {"vault_type": "academic-paper-research", "papers": []}
    payload.setdefault("papers", [])
    return payload


def _relative_path(path: Path, vault_path: Path) -> str:
    return path.relative_to(vault_path).as_posix()


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def _strip_scalar(value: str) -> str:
    return value.strip().strip("'\"")


def _parse_inline_list(value: str) -> list[str]:
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return [_strip_scalar(text)] if text else []
    inner = text[1:-1].strip()
    if not inner:
        return []
    return [_strip_scalar(item) for item in inner.split(",") if _strip_scalar(item)]


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text
    frontmatter_lines = lines[1:end_index]
    body = "\n".join(lines[end_index + 1 :])
    payload: dict[str, object] = {}
    current_key: str | None = None
    for line in frontmatter_lines:
        if not line.strip():
            continue
        list_match = re.match(r"^\s+-\s+(.*)$", line)
        if list_match and current_key:
            payload.setdefault(current_key, [])
            if isinstance(payload[current_key], list):
                payload[current_key].append(_strip_scalar(list_match.group(1)))
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        current_key = key.strip()
        value = value.strip()
        if not value:
            payload[current_key] = []
        elif value.startswith("[") and value.endswith("]"):
            payload[current_key] = _parse_inline_list(value)
        else:
            payload[current_key] = _strip_scalar(value)
    return payload, body


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return _parse_inline_list(text) if text else []


def _wikilink_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if target.endswith(".md"):
        target = target[:-3]
    return target.replace("\\", "/").strip("/")


def _extract_wikilink_targets(text: str) -> list[str]:
    return [_wikilink_target(match.group(1)) for match in WIKILINK_PATTERN.finditer(text)]


def _raw_paper_path_from_source(value: str) -> str | None:
    uri_match = RAW_PAPER_URI_PATTERN.search(value)
    if uri_match:
        slug = unquote(uri_match.group("slug"))
        return f"{PAPER_SOURCE_ROOT_NAME}/raw/{slug}/paper.pdf"
    path_match = RAW_PAPER_PATH_PATTERN.search(value)
    if path_match:
        slug = path_match.group("slug")
        return f"{PAPER_SOURCE_ROOT_NAME}/raw/{slug}/paper.pdf"
    return None


def _raw_paper_paths_from_text(text: str) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    seen: set[str] = set()
    for uri_match in RAW_PAPER_URI_PATTERN.finditer(text):
        slug = unquote(uri_match.group("slug"))
        raw_path = f"{PAPER_SOURCE_ROOT_NAME}/raw/{slug}/paper.pdf"
        if raw_path not in seen:
            paths.append((raw_path, uri_match.group(0)))
            seen.add(raw_path)
    for path_match in RAW_PAPER_PATH_PATTERN.finditer(text):
        slug = path_match.group("slug")
        raw_path = f"{PAPER_SOURCE_ROOT_NAME}/raw/{slug}/paper.pdf"
        if raw_path not in seen:
            paths.append((raw_path, path_match.group(0)))
            seen.add(raw_path)
    return paths


def _source_evidence_values(page: dict) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    body = str(page.get("body") or "")
    values.extend(_raw_paper_paths_from_text(body))

    # Legacy compatibility only: old formal pages sometimes stored source PDFs in
    # frontmatter `sources` or as internal wikilinks. New pages must use the body
    # `## 原文与证据入口` Markdown link instead.
    for source in _as_list(page.get("frontmatter", {}).get("sources")):
        raw_path = _raw_paper_path_from_source(source)
        if raw_path:
            values.append((raw_path, source))
    for link in page.get("links", []):
        raw_path = _raw_paper_path_from_source(str(link))
        if raw_path:
            values.append((raw_path, str(link)))
    return values


def _source_evidence_for_page(vault_path: Path, page: dict) -> list[dict]:
    evidence: list[dict] = []
    seen_paths: set[str] = set()
    for raw_path, source in _source_evidence_values(page):
        if raw_path in seen_paths:
            continue
        seen_paths.add(raw_path)
        paper_pdf = vault_path / raw_path
        paper_root = paper_pdf.parent
        mineru_root = paper_root / "mineru"
        mineru_markdowns = sorted(mineru_root.glob("*.md")) if mineru_root.exists() else []
        evidence.append(
            {
                "path": raw_path,
                "slug": paper_root.name,
                "source": source,
                "formal_graph_node": False,
                "exists": paper_pdf.is_file(),
                "artifacts": {
                    "paper.pdf": paper_pdf.is_file(),
                    "metadata.json": (paper_root / "metadata.json").is_file(),
                    "mineru_markdown": bool(mineru_markdowns),
                    "mineru_tex": has_nonempty_mineru_tex(paper_root),
                    "mineru_images": (mineru_root / "images").is_dir(),
                },
            }
        )
    return evidence


def _is_raw_paper_pdf_link(target: str) -> bool:
    return _raw_paper_path_from_source(target) is not None


def _question_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(question):
        token = token.casefold().strip()
        if len(token) < 2:
            continue
        tokens.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            max_width = min(4, len(token))
            for width in range(2, max_width + 1):
                tokens.extend(token[index : index + width] for index in range(0, len(token) - width + 1))
    return list(dict.fromkeys(tokens))


def _formal_markdown_paths(vault_path: Path) -> list[Path]:
    paths: list[Path] = []
    for root in FORMAL_PAGE_ROOTS:
        root_path = vault_path / root
        if root_path.exists():
            paths.extend(sorted(root_path.rglob("*.md")))
    return paths


def _load_formal_pages(vault_path: Path) -> dict[str, dict]:
    vault_path = vault_path.resolve()
    pages: dict[str, dict] = {}
    for path in _formal_markdown_paths(vault_path):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(text)
        relative = _relative_path(path, vault_path)
        title = str(frontmatter.get("title") or path.stem.replace("-", " ")).strip().strip('"')
        aliases = _as_list(frontmatter.get("aliases"))
        tags = _as_list(frontmatter.get("tags"))
        body_links = _extract_wikilink_targets(body)
        pages[relative] = {
            "path": relative,
            "title": title,
            "aliases": aliases,
            "tags": tags,
            "frontmatter": frontmatter,
            "body": body,
            "links": body_links,
            "search_text": "\n".join([relative, title, " ".join(aliases), " ".join(tags), body]).casefold(),
        }
    return pages


def _registry_for_pages(pages: dict[str, dict]) -> dict[str, set[str]]:
    registry: dict[str, set[str]] = defaultdict(set)
    for relative, page in pages.items():
        candidates = [
            relative,
            relative.removesuffix(".md"),
            Path(relative).stem,
            page["title"],
            *page["aliases"],
        ]
        for candidate in candidates:
            key = _normalize_key(str(candidate))
            if key:
                registry[key].add(relative)
    return registry


def _resolve_target(target: str, registry: dict[str, set[str]]) -> str | None:
    key = _normalize_key(target)
    if not key:
        return None
    matches = sorted(registry.get(key) or [])
    return matches[0] if len(matches) == 1 else None


def _build_graph(pages: dict[str, dict], registry: dict[str, set[str]]) -> tuple[dict[str, set[str]], dict[str, set[str]], list[dict]]:
    outlinks: dict[str, set[str]] = {relative: set() for relative in pages}
    backlinks: dict[str, set[str]] = {relative: set() for relative in pages}
    corrections: list[dict] = []
    seen_corrections: set[tuple[str, str, str]] = set()
    for relative, page in pages.items():
        for target in page["links"]:
            if target.startswith(INTERNAL_SOURCE_PREFIXES):
                key = ("forbidden_internal_graph_link", relative, target)
                if key not in seen_corrections:
                    message = (
                        "Formal page uses an internal wikilink for source PDF; use a Markdown "
                        "`obsidian://` link in `## 原文与证据入口` instead."
                        if _is_raw_paper_pdf_link(target)
                        else "Formal page body links a Paper Source internal artifact as graph content."
                    )
                    corrections.append(
                        {
                            "kind": "forbidden_internal_graph_link",
                            "source": relative,
                            "target": target,
                            "message": message,
                        }
                    )
                    seen_corrections.add(key)
                continue
            resolved = _resolve_target(target, registry)
            if resolved is None:
                key = ("broken_wikilink", relative, target)
                if key not in seen_corrections:
                    corrections.append(
                        {
                            "kind": "broken_wikilink",
                            "source": relative,
                            "target": target,
                            "message": "Wikilink target does not resolve to a formal page.",
                        }
                    )
                    seen_corrections.add(key)
                continue
            if resolved != relative:
                outlinks[relative].add(resolved)
                backlinks[resolved].add(relative)
    return outlinks, backlinks, corrections


def _seed_matches(question: str, pages: dict[str, dict]) -> dict[str, dict]:
    tokens = _question_tokens(question)
    matches: dict[str, dict] = {}
    for relative, page in pages.items():
        score = 0
        reasons: set[str] = set()
        title_blob = " ".join([page["title"], relative]).casefold()
        alias_blob = " ".join(page["aliases"]).casefold()
        tag_blob = " ".join(page["tags"]).casefold()
        text = page["search_text"]
        for token in tokens:
            if token in title_blob:
                score += 4
                reasons.add("direct")
            elif token in alias_blob:
                score += 4
                reasons.add("alias")
            elif token in tag_blob:
                score += 3
                reasons.add("tag")
            elif token in text:
                score += 1
                reasons.add("direct")
        if score:
            matches[relative] = {"score": score, "reasons": sorted(reasons)}
    return matches


def _snippet(body: str, question: str, *, max_length: int = 220) -> str:
    compact = re.sub(r"\s+", " ", body).strip()
    if len(compact) <= max_length:
        return compact
    tokens = _question_tokens(question)
    lowered = compact.casefold()
    first_hit = min((lowered.find(token) for token in tokens if lowered.find(token) >= 0), default=0)
    start = max(0, first_hit - 60)
    return compact[start : start + max_length].strip() + "..."


def _add_reason(selected: dict[str, dict], pages: dict[str, dict], relative: str, reason: str, score: int = 0) -> None:
    if relative not in pages:
        return
    entry = selected.setdefault(
        relative,
        {
            "path": relative,
            "title": pages[relative]["title"],
            "aliases": pages[relative]["aliases"],
            "tags": pages[relative]["tags"],
            "score": 0,
            "reasons": [],
        },
    )
    entry["score"] += score
    if reason not in entry["reasons"]:
        entry["reasons"].append(reason)


def _graph_select(question: str, pages: dict[str, dict], outlinks: dict[str, set[str]], backlinks: dict[str, set[str]], *, limit: int, max_hops: int) -> dict[str, dict]:
    seed_matches = _seed_matches(question, pages)
    selected: dict[str, dict] = {}
    seed_paths = [
        relative
        for relative, match in sorted(seed_matches.items(), key=lambda item: (-item[1]["score"], item[0]))
    ]
    for relative in seed_paths:
        match = seed_matches[relative]
        for index, reason in enumerate(match["reasons"]):
            _add_reason(selected, pages, relative, reason, match["score"] if index == 0 else 0)

    frontier = set(seed_paths)
    visited = set(seed_paths)
    for _hop in range(max(0, max_hops)):
        next_frontier: set[str] = set()
        for relative in sorted(frontier):
            for target in sorted(outlinks.get(relative, set())):
                _add_reason(selected, pages, target, "outlink", 2)
                if relative in outlinks.get(target, set()):
                    _add_reason(selected, pages, target, "reciprocal", 2)
                if target not in visited:
                    next_frontier.add(target)
            for source in sorted(backlinks.get(relative, set())):
                _add_reason(selected, pages, source, "backlink", 2)
                if source not in visited:
                    next_frontier.add(source)
        visited.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break

    co_link_counts = Counter(
        target
        for relative in seed_paths
        for target in outlinks.get(relative, set())
    )
    for target, count in co_link_counts.items():
        if count >= 2:
            _add_reason(selected, pages, target, "co-linked", count * 2)

    ranked = dict(
        sorted(
            selected.items(),
            key=lambda item: (-item[1]["score"], item[0]),
        )[:limit]
    )
    for relative, entry in ranked.items():
        entry["snippet"] = _snippet(pages[relative]["body"], question)
        entry["outlinks"] = sorted(outlinks.get(relative, set()))
        entry["backlinks"] = sorted(backlinks.get(relative, set()))
    return ranked


def _tracking_link_corrections(vault_path: Path, registry: dict[str, set[str]]) -> list[dict]:
    corrections: list[dict] = []
    for name in ("index.md", "hot.md"):
        path = vault_path / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for target in _extract_wikilink_targets(text):
            if target.startswith(INTERNAL_SOURCE_PREFIXES):
                continue
            if _resolve_target(target, registry) is None:
                corrections.append(
                    {
                        "kind": "stale_tracking_link",
                        "source": name,
                        "target": target,
                        "message": f"{name} links a page that is not present in the formal graph.",
                    }
                )
    return corrections


def _duplicate_alias_corrections(registry: dict[str, set[str]]) -> list[dict]:
    corrections: list[dict] = []
    for key, matches in sorted(registry.items()):
        if len(matches) > 1:
            corrections.append(
                {
                    "kind": "duplicate_alias",
                    "target": key,
                    "sources": sorted(matches),
                    "message": "Multiple formal pages share the same title, alias, or slug key.",
                }
            )
    return corrections


def _source_frontmatter_corrections(vault_path: Path, pages: dict[str, dict], selected_paths: set[str]) -> list[dict]:
    corrections: list[dict] = []
    for relative in sorted(selected_paths):
        page = pages.get(relative)
        if not page:
            continue
        body_source_paths = [raw_path for raw_path, _source in _raw_paper_paths_from_text(str(page.get("body") or ""))]
        sources = _as_list(page.get("frontmatter", {}).get("sources"))
        if relative.startswith("references/") and not body_source_paths:
            corrections.append(
                {
                    "kind": "source_pdf_body_link_missing",
                    "source": relative,
                    "target": "## 原文与证据入口",
                    "message": "Reference page has no body source PDF link in `## 原文与证据入口`.",
                }
            )
        for source in sources:
            raw_path = _raw_paper_path_from_source(source)
            if raw_path is None:
                if source.startswith("[[") or source.startswith("obsidian://") or source.startswith("_paper_source/") or source.startswith("_epi/"):
                    corrections.append(
                        {
                            "kind": "source_frontmatter_mismatch",
                            "source": relative,
                            "target": source,
                            "message": "Frontmatter `sources` must be scan-friendly short labels; put source PDF links in `## 原文与证据入口`.",
                        }
                    )
                continue
            corrections.append(
                {
                    "kind": "source_frontmatter_mismatch",
                    "source": relative,
                    "target": source,
                    "message": "Frontmatter `sources` contains a source PDF link; use a short source label and move the PDF URI to `## 原文与证据入口`.",
                }
            )
            if not (vault_path / raw_path).is_file():
                corrections.append(
                    {
                        "kind": "source_frontmatter_mismatch",
                        "source": relative,
                        "target": raw_path,
                        "message": "Source PDF link points to a missing source artifact.",
                    }
                )
        for raw_path in body_source_paths:
            if not (vault_path / raw_path).is_file():
                corrections.append(
                    {
                        "kind": "source_pdf_body_link_missing",
                        "source": relative,
                        "target": raw_path,
                        "message": "Body source PDF link points to a missing source artifact.",
                    }
                )
    return corrections


def _page_title_list(pages: list[dict], *, limit: int = 3) -> str:
    titles = [str(page.get("title") or page.get("path")) for page in pages[:limit]]
    return "、".join(titles)


def _source_evidence_phrase(page: dict) -> str:
    evidence = page.get("source_evidence") or []
    if not evidence:
        return "未发现可解析的 _paper_source/raw source evidence"
    available = [item for item in evidence if item.get("exists")]
    if available:
        return "已解析 source evidence: " + ", ".join(str(item.get("path")) for item in available[:2])
    return "source evidence 已声明但源 PDF 当前缺失: " + ", ".join(str(item.get("path")) for item in evidence[:2])


def _build_answer_sections(question: str, pages: list[dict], corrections: list[dict]) -> dict[str, list[str]]:
    if not pages:
        return {
            "wiki_evidence": ["formal graph 中没有返回足以直接回答该问题的正式页面。"],
            "synthesis": ["当前 wiki 证据不足，不能把任何研究路线标成 wiki-grounded 综合结论。"],
            "inference": ["可推断的下一步是先沉淀或补全与该问题直接相关的 reference/concept/synthesis 页面，再重新提问。"],
            "uncertainty": ["缺少 formal pages、source evidence 或明确图谱关系时，本次回答只能作为检索缺口报告。"],
        }

    top_page = pages[0]
    related_titles = _page_title_list(pages)
    evidence_lines = []
    for page in pages[:5]:
        reasons = ", ".join(page.get("reasons") or [])
        snippet = page.get("snippet") or "no snippet"
        evidence_lines.append(
            f"{page.get('title')} ({page.get('path')}; reasons: {reasons}) 支持的上下文是：{snippet}"
        )

    synthesis = [
        f"针对“{question}”，formal graph 的主要锚点是 {related_titles}；回答应优先围绕这些页面的共同问题边界和相互链接展开。",
    ]
    linked = sorted({*(top_page.get("outlinks") or []), *(top_page.get("backlinks") or [])})
    if linked:
        synthesis.append(
            f"最强命中页 {top_page.get('title')} 还连接到 {', '.join(linked[:4])}，这些页面应作为交叉检查路径。"
        )

    inference = [
        f"基于当前图谱，可把第一步收敛为：先阅读并复核 {top_page.get('title')}，再沿 {related_titles} 做方法/证据边界对比；这是从图谱结构推出的行动建议。"
    ]
    if len(pages) > 1:
        inference.append(
            f"若要形成更强研究判断，应把 {related_titles} 的结论、实验指标和未覆盖问题整理成一个 synthesis 或 opportunity 页面。"
        )

    uncertainty = []
    missing_source_pages = [page for page in pages if not any(item.get("exists") for item in page.get("source_evidence") or [])]
    if missing_source_pages:
        uncertainty.append(
            "部分命中页缺少可确认存在的 _paper_source/raw source PDF，因此 source-grounded 强度不足。"
        )
    if corrections:
        uncertainty.append(f"检索时发现 {len(corrections)} 个纠错候选，修复前相关结论需要保留不确定性。")
    if not uncertainty:
        uncertainty.append("本次只读检索未发现会阻断回答的纠错候选，但仍需人工判断推断部分是否适合进入正式页。")

    return {
        "wiki_evidence": evidence_lines,
        "synthesis": synthesis,
        "inference": inference,
        "uncertainty": uncertainty,
    }


def ask_wiki(
    vault_path: Path,
    *,
    question: str,
    limit: int = 8,
    max_hops: int = 1,
) -> dict:
    vault_path = Path(vault_path).resolve()
    pages = _load_formal_pages(vault_path)
    registry = _registry_for_pages(pages)
    outlinks, backlinks, graph_corrections = _build_graph(pages, registry)
    selected = _graph_select(question, pages, outlinks, backlinks, limit=limit, max_hops=max_hops)
    result_pages = list(selected.values())
    for page in result_pages:
        source_evidence = _source_evidence_for_page(vault_path, pages[page["path"]])
        if source_evidence:
            page["source_evidence"] = source_evidence
    correction_candidates = [
        *graph_corrections,
        *_tracking_link_corrections(vault_path, registry),
        *_duplicate_alias_corrections(registry),
        *_source_frontmatter_corrections(vault_path, pages, set(selected)),
    ]
    answer = _build_answer_sections(question, result_pages, correction_candidates)
    return {
        "title": "Paper Wiki Ask",
        "mode": "read-only",
        "question": question,
        "write_performed": False,
        "retrieval": {
            "primary": "formal_graph",
            "formal_roots": [f"{root}/" for root in FORMAL_PAGE_ROOTS],
            "graph_signals": ["direct", "alias", "tag", "outlink", "backlink", "reciprocal", "co-linked"],
            "source_evidence": {
                "role": "source_confirmation",
                "root": f"{PAPER_SOURCE_ROOT_NAME}/raw",
                "formal_graph_node": False,
            },
            "qmd": {
                "role": "optional_accelerator",
                "used": False,
                "source_of_truth": "Markdown formal graph and linked source evidence, not QMD.",
            },
            "fallbacks": ["frontmatter", "index.md", "hot.md", "direct Markdown search"],
            "max_hops": max_hops,
            "limit": limit,
        },
        "summary": {
            "formal_page_count": len(pages),
            "returned_page_count": len(result_pages),
            "correction_candidate_count": len(correction_candidates),
            "source_evidence_count": sum(len(page.get("source_evidence") or []) for page in result_pages),
        },
        "pages": result_pages,
        "answer": answer,
        "answer_guidance": {
            "wiki_evidence": "Use the returned formal pages as the grounded answer context.",
            "synthesis": "Compare converging pages before recommending a research direction.",
            "inference": "Mark cross-page or method-selection reasoning as inference when no page states it directly.",
            "uncertainty": "Call out missing benchmarks, weak provenance, and unresolved correction candidates.",
        },
        "correction_candidates": correction_candidates,
        "next_actions": [
            "Answer the user from the formal graph without writing wiki files.",
            "Ask before routing correction candidates into Paper Wiki repair/update workflows.",
        ],
    }


def _decision(paper: dict) -> dict:
    decision = paper.get("research_decision")
    return decision if isinstance(decision, dict) else {}


def _role_verdicts(paper: dict) -> dict:
    verdicts = _decision(paper).get("role_verdicts")
    return verdicts if isinstance(verdicts, dict) else {}


def _matches(
    paper: dict,
    *,
    consensus: str | None,
    role: str | None,
    verdict: str | None,
    warning_reviewer: str | None,
    blocking_lens: str | None,
) -> bool:
    decision = _decision(paper)
    if paper.get("promotion_status") != "promoted":
        return False
    if consensus and decision.get("panel_consensus") != consensus:
        return False
    if role and verdict and _role_verdicts(paper).get(role) != verdict:
        return False
    if warning_reviewer and warning_reviewer not in (decision.get("warning_reviewers") or []):
        return False
    if blocking_lens and blocking_lens not in (decision.get("blocking_lenses") or []):
        return False
    return True


def _normalize_paper(paper: dict) -> dict:
    decision = _decision(paper)
    return {
        "slug": paper.get("slug"),
        "title": paper.get("title") or paper.get("slug"),
        "compiled_reference": paper.get("compiled_reference"),
        "decision": decision,
        "role_verdicts": _role_verdicts(paper),
        "role_assessments": paper.get("role_assessments") or [],
    }


def query_wiki(
    vault_path: Path,
    *,
    consensus: str | None = None,
    role: str | None = None,
    verdict: str | None = None,
    warning_reviewer: str | None = None,
    blocking_lens: str | None = None,
    limit: int = 20,
) -> dict:
    manifest = _load_manifest(vault_path)
    promoted = [
        paper
        for paper in manifest.get("papers", [])
        if isinstance(paper, dict) and paper.get("promotion_status") == "promoted"
    ]
    matches = [
        _normalize_paper(paper)
        for paper in promoted
        if _matches(
            paper,
            consensus=consensus,
            role=role,
            verdict=verdict,
            warning_reviewer=warning_reviewer,
            blocking_lens=blocking_lens,
        )
    ][:limit]
    return {
        "title": "Paper Source Wiki Query",
        "filters": {
            "consensus": consensus,
            "role": role,
            "verdict": verdict,
            "warning_reviewer": warning_reviewer,
            "blocking_lens": blocking_lens,
            "limit": limit,
        },
        "summary": {
            "matched_count": len(matches),
            "total_promoted_count": len(promoted),
        },
        "papers": matches,
    }


def _roles_line(role_verdicts: dict) -> str:
    parts = [
        f"{label}={role_verdicts.get(role, '-')}"
        for role, label in ROLE_LABELS.items()
    ]
    return "roles: " + ", ".join(parts)


def render_wiki_query(result: dict) -> str:
    lines = [
        result.get("title", "Paper Source Wiki Query"),
        "",
        f"matched: {result.get('summary', {}).get('matched_count', 0)} / promoted: {result.get('summary', {}).get('total_promoted_count', 0)}",
        "",
    ]
    papers = result.get("papers") or []
    if not papers:
        lines.extend(["No matching promoted papers.", ""])
        return "\n".join(lines)
    for paper in papers:
        decision = paper.get("decision") or {}
        lines.append(f"- {paper.get('slug')} | {paper.get('title')}")
        if paper.get("compiled_reference"):
            lines.append(f"  reference: {paper['compiled_reference']}")
        lines.append(f"  decision: {decision.get('panel_consensus') or decision.get('recommendation') or '-'}")
        lines.append(f"  {_roles_line(paper.get('role_verdicts') or {})}")
        if decision.get("blocking_lenses"):
            lines.append("  blocking: " + ", ".join(str(item) for item in decision["blocking_lenses"]))
        if decision.get("warning_reviewers"):
            lines.append("  warnings: " + ", ".join(str(item) for item in decision["warning_reviewers"]))
    lines.append("")
    return "\n".join(lines)


def render_wiki_ask(result: dict) -> str:
    pages = result.get("pages") or []
    corrections = result.get("correction_candidates") or []
    answer = result.get("answer") or {}
    lines = [
        result.get("title", "Paper Wiki Ask"),
        "",
        f"question: {result.get('question', '')}",
        f"mode: {result.get('mode', 'read-only')} | write_performed={str(result.get('write_performed', False)).lower()}",
        "",
        "## 使用的 Wiki 图谱",
    ]
    if not pages:
        lines.append("- formal graph 未返回直接相关页面。")
    for page in pages:
        reasons = ", ".join(page.get("reasons") or [])
        lines.append(f"- {page.get('path')} | {page.get('title')} | reasons: {reasons}")
        if page.get("source_evidence"):
            lines.append(f"  {_source_evidence_phrase(page)}")
    lines.extend(
        [
            "",
            "## 回答",
            "",
            "【Wiki 证据】",
        ]
    )
    for item in answer.get("wiki_evidence") or []:
        lines.append(f"- {item}")
    if not answer.get("wiki_evidence"):
        lines.append("- 未在 formal graph 中找到直接相关页面。")
    lines.extend(["", "【综合判断】"])
    for item in answer.get("synthesis") or []:
        lines.append(f"- {item}")
    lines.extend(["", "【推断】"])
    for item in answer.get("inference") or []:
        lines.append(f"- {item}")
    lines.extend(["", "【边界/不确定】"])
    for item in answer.get("uncertainty") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 发现的 Wiki 问题 / 纠错候选"])
    if not corrections:
        lines.append("- 暂未发现需要立即处理的纠错候选。")
    for candidate in corrections:
        source = candidate.get("source") or ", ".join(candidate.get("sources") or [])
        lines.append(
            f"- {candidate.get('kind')}: {candidate.get('target', '-')} "
            f"(source: {source or '-'}) - {candidate.get('message', '')}"
        )
    lines.extend(
        [
            "",
            "是否需要我根据这些纠错候选继续修复？确认前我不会修改 formal pages、log.md、QMD 或 Paper Source artifacts。",
            "",
        ]
    )
    return "\n".join(lines)
