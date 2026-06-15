from __future__ import annotations

import json
from pathlib import Path

from paper_source.artifacts import file_sha256, read_json
from paper_source.frontmatter import dump_frontmatter_value
from paper_source.source_artifacts import canonical_source_first_artifacts, has_nonempty_mineru_tex, source_first_artifacts
from paper_source.wiki_contracts import (
    PAPER_WIKI_CANONICAL_SKILL,
    deposition_skill_compatibility_aliases,
    final_source_review_must_record,
    formal_frontmatter_schema,
    formal_page_family_names,
    formal_page_family_paths,
    formal_page_family_records,
    page_lifecycle_states,
    quality_enhancement_wiki_skills,
    qmd_collection_policy,
    required_wiki_skills,
    research_review_fields,
    optional_wiki_skills,
    verified_page_requirements,
    wiki_deposition_quality_gates,
)
from paper_source.wiki_handoff_contracts import agent_context_policy


FAST_INGEST_MODE = "fast-ingest"
REVIEWED_INGEST_MODE = "reviewed-ingest"
AUDITED_INGEST_MODE = "audited-ingest"
INGEST_MODES = {FAST_INGEST_MODE, REVIEWED_INGEST_MODE, AUDITED_INGEST_MODE}


def _source_first_artifacts(slug: str, paper_root: Path | None = None) -> list[str]:
    if paper_root is not None:
        return source_first_artifacts(paper_root)
    return canonical_source_first_artifacts(slug)


def normalize_ingest_mode(mode: str | None) -> str:
    normalized = str(mode or FAST_INGEST_MODE).strip()
    if normalized not in INGEST_MODES:
        raise ValueError(
            "ingest mode must be one of "
            + ", ".join(sorted(INGEST_MODES))
            + f"; got {normalized or 'empty'}"
        )
    return normalized


def critic_required_for_mode(mode: str | None) -> bool:
    return normalize_ingest_mode(mode) == AUDITED_INGEST_MODE


def reader_required_for_mode(mode: str | None) -> bool:
    return normalize_ingest_mode(mode) in {REVIEWED_INGEST_MODE, AUDITED_INGEST_MODE}


def _source_markdown_artifact(slug: str) -> str:
    return _source_first_artifacts(slug)[2]


def _serial_join(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _required_wiki_skill_loading_clause(load_prefix: str) -> str:
    remaining_skills = [
        skill
        for skill in required_wiki_skills()
        if skill != PAPER_WIKI_CANONICAL_SKILL
    ]
    remaining_clause = f", then load {_serial_join(remaining_skills)}" if remaining_skills else ""
    return (
        f"{load_prefix} {PAPER_WIKI_CANONICAL_SKILL} first as the canonical paper wiki layer"
        f"{remaining_clause}"
    )


def _role_verdict_key(lens: str) -> str:
    return "paper_source_" + lens.replace("-", "_") + "_verdict"


def _decision_frontmatter_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    role_verdicts = decision.get("role_verdicts") or {}
    lines = [
        f"paper_source_recommendation: {dump_frontmatter_value(decision.get('recommendation', ''))}",
        f"paper_source_next_action: {dump_frontmatter_value(decision.get('next_action', ''))}",
        f"paper_source_panel_consensus: {dump_frontmatter_value(panel.get('consensus', ''))}",
        f"paper_source_blocking_lenses: {dump_frontmatter_value(panel.get('blocking_lenses') or [])}",
        f"paper_source_warning_reviewers: {dump_frontmatter_value(panel.get('warning_reviewers') or [])}",
    ]
    for lens, verdict in role_verdicts.items():
        lines.append(f"{_role_verdict_key(str(lens))}: {dump_frontmatter_value(verdict)}")
    return lines


def _sidecar_status(paper_root: Path, artifact_name: str) -> dict:
    path = paper_root / artifact_name
    status = {"path": artifact_name, "status": "missing", "sha256": None, "warnings": []}
    if not path.exists():
        return status
    try:
        payload = read_json(path)
    except (json.JSONDecodeError, OSError) as exc:
        return {**status, "status": "unreadable", "warnings": [str(exc)]}
    warnings = payload.get("warnings") if isinstance(payload, dict) else []
    return {
        "path": artifact_name,
        "status": "present",
        "sha256": file_sha256(path),
        "warnings": warnings if isinstance(warnings, list) else [],
    }


def _missing_sidecar_status(artifact_name: str) -> dict:
    return {"path": artifact_name, "status": "missing", "sha256": None, "warnings": []}


def _research_decision_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    lines = [
        "## Research Decision",
        "",
        f"- Recommendation: {decision.get('recommendation', '')}",
        f"- Next action: {decision.get('next_action', '')}",
        f"- Consensus: {panel.get('consensus', '')}",
        f"- Blocking lenses: {', '.join(panel.get('blocking_lenses') or []) or 'None'}",
        f"- Warning reviewers: {', '.join(panel.get('warning_reviewers') or []) or 'None'}",
        "",
        "## Role Assessment Matrix",
    ]
    for assessment in decision.get("role_assessments") or []:
        lines.append(f"- {assessment.get('lens')}: {assessment.get('verdict')} -> {assessment.get('action')}")
        if assessment.get("artifact"):
            lines.append(f"  - Artifact: {assessment['artifact']}")
        if assessment.get("responsibility"):
            lines.append(f"  - Responsibility: {assessment['responsibility']}")
        if assessment.get("promotion_blocking"):
            lines.append("  - Promotion blocking: true")
        if assessment.get("primary_evidence"):
            lines.append(f"  - Evidence: {assessment['primary_evidence']}")
    return lines


def _promotion_review_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    lines = [
        "## Promotion Review Inputs",
        "",
        f"- Recommendation: {decision.get('recommendation', '')}",
        f"- Consensus: {panel.get('consensus', '')}",
    ]
    for assessment in decision.get("role_assessments") or []:
        lines.append(
            f"- {assessment.get('lens')}: {assessment.get('action')} "
            f"({assessment.get('artifact')})"
        )
    return lines


def _first_bullet_after_heading(text: str, heading: str) -> str:
    in_section = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped == heading
            continue
        if in_section and stripped.startswith("- "):
            return stripped.removeprefix("- ").strip()
    return ""


def _compact_text(text: object, *, limit: int = 360) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _metadata_abstract(metadata: dict) -> str:
    if metadata.get("abstract"):
        return str(metadata["abstract"])
    for record in metadata.get("raw_records") or []:
        if isinstance(record, dict) and record.get("abstract"):
            return str(record["abstract"])
    return ""


def _reader_take_or_note(text: str, note: str, *, limit: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    lowered = cleaned.lower()
    if (
        not cleaned
        or lowered.startswith("inference:")
        or " inference:" in lowered
        or "enableocean" in lowered
        or len(cleaned) > limit
    ):
        return note
    return cleaned


def _metadata_metric(metadata: dict, *keys: str) -> object | None:
    for key in keys:
        if metadata.get(key) not in (None, ""):
            return metadata[key]
    for record in metadata.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        for key in keys:
            if record.get(key) not in (None, ""):
                return record[key]
        raw_record = record.get("raw_record")
        if isinstance(raw_record, dict):
            for key in keys:
                if raw_record.get(key) not in (None, ""):
                    return raw_record[key]
    return None


def _metadata_authors(metadata: dict) -> str:
    authors = metadata.get("authors") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.replace(";", ",").split(",") if part.strip()]
    if not authors:
        for record in metadata.get("raw_records") or []:
            if isinstance(record, dict) and record.get("authors"):
                raw_authors = record["authors"]
                if isinstance(raw_authors, str):
                    authors = [part.strip() for part in raw_authors.replace(";", ",").split(",") if part.strip()]
                elif isinstance(raw_authors, list):
                    authors = raw_authors
                break
    if not authors:
        return "未记录"
    shown = ", ".join(str(author) for author in authors[:3])
    if len(authors) > 3:
        return f"{shown} 等 {len(authors)} 人"
    return shown


def _identity_lines(metadata: dict) -> list[str]:
    year = metadata.get("year") or _metadata_metric(metadata, "year") or "未记录"
    venue = metadata.get("venue") or _metadata_metric(metadata, "venue") or "未记录"
    doi = metadata.get("doi") or _metadata_metric(metadata, "doi") or "未记录"
    arxiv_id = metadata.get("arxiv_id") or _metadata_metric(metadata, "arxiv_id") or "未记录"
    pdf_url = metadata.get("pdf_url") or _metadata_metric(metadata, "pdf_url") or "未记录"
    citations = _metadata_metric(metadata, "citation_count", "citations", "cited_by_count")
    citation_text = str(citations) if citations not in (None, "") else "未记录"
    score = metadata.get("score")
    score_text = f"{score:.4f}" if isinstance(score, float) else str(score or "未记录")
    sources = metadata.get("sources") or []
    if isinstance(sources, list):
        source_text = ", ".join(str(source) for source in sources) or "未记录"
    else:
        source_text = str(sources)
    impact_factor = "未自动获取"
    if str(venue).lower() in {"arxiv", "未记录", ""} or arxiv_id != "未记录":
        impact_factor = "不适用或未记录"
    return [
        f"- 作者：{_metadata_authors(metadata)}",
        f"- 年份/来源：{year}；venue：{venue}；source：{source_text}",
        f"- DOI/arXiv：{doi} / {arxiv_id}",
        f"- PDF：{pdf_url}",
        f"- 质量指标：Paper Source 元数据引用数（Citation Count）={citation_text}；影响因子（Impact Factor, IF）={impact_factor}；Paper Source score={score_text}",
    ]


def _term_pairs_for_text(text: str) -> list[str]:
    lowered = text.lower()
    glossary = [
        (("economic model predictive control", "empc"), "经济模型预测控制（Economic Model Predictive Control, EMPC）"),
        (("lyapunov-constrained", "lmpc"), "李雅普诺夫约束模型预测控制（Lyapunov-constrained Model Predictive Control, LMPC）"),
        (("model predictive control", "mpc"), "模型预测控制（Model Predictive Control, MPC）"),
        (("autonomous underwater vehicle", "auv"), "自主水下航行器（Autonomous Underwater Vehicle, AUV）"),
        (("reinforcement learning",), "强化学习（Reinforcement Learning, RL）"),
        (("deterministic policy gradient", "policy gradient"), "确定性策略梯度（Deterministic Policy Gradient, DPG）"),
        (("q-learning", "q learning"), "Q 学习（Q-learning）"),
        (("trajectory tracking",), "轨迹跟踪（Trajectory Tracking）"),
        (("fault-tolerant", "fault tolerant"), "容错控制（Fault-tolerant Control）"),
        (("docking",), "对接控制（Docking Control）"),
        (("thruster",), "推进器（Thruster）"),
        (("middleware", "ros-desert"), "中间件（Middleware）"),
        (("sea trial", "sea-trial"), "海试验证（Sea Trial Validation）"),
        (("mobile robot", "mobile robots"), "移动机器人（Mobile Robot）"),
        (("feedback control",), "反馈控制（Feedback Control）"),
        (("navigation control", "control"), "控制（Control）"),
    ]
    pairs: list[str] = []
    for needles, label in glossary:
        if any(needle in lowered for needle in needles) and label not in pairs:
            pairs.append(label)
    return pairs[:8] or ["源论文术语需在正式 wiki 写入时从原文复核（Source Terms To Be Reviewed）"]


def _method_idea(metadata: dict, title: str) -> str:
    abstract = _metadata_abstract(metadata)
    text = f"{title} {abstract}".lower()
    if "ros-desert" in text or ("middleware" in text and "sea trial" in text):
        return "论文重点不是提出单一控制律，而是验证 ROS-DESERT 中间件（Middleware）在 AUV 海试验证（Sea Trial Validation）中的任务组织、通信和实验链路价值。"
    if "economic model predictive control" in text or "empc" in text:
        return "论文把能耗、任务收益和约束统一到经济模型预测控制（Economic Model Predictive Control, EMPC）框架中，用滚动优化支持 AUV 能源管理。"
    if ("lyapunov" in text or "lmpc" in text) and "fault" in text:
        return "论文围绕推进器故障下的 AUV 轨迹跟踪，结合在线故障识别与李雅普诺夫约束模型预测控制（Lyapunov-constrained MPC, LMPC）来降低模式切换时的不稳定波动。"
    if "reinforcement learning" in text and ("docking" in text or "dock onto" in text):
        return "论文使用强化学习（Reinforcement Learning, RL）学习 AUV 对接控制（Docking Control）策略，关注接近、姿态调整和终端对接行为。"
    if "q-learning" in text or "deterministic policy gradient" in text:
        return "论文把 Q 学习（Q-learning）信号和确定性策略梯度（Deterministic Policy Gradient, DPG）结合，用强化学习（Reinforcement Learning, RL）处理 AUV 跟踪控制策略学习。"
    if "model predictive control" in text or "mpc" in text:
        return "论文采用模型预测控制（Model Predictive Control, MPC）把动态约束、优化目标和滚动控制动作合在同一个控制框架内。"
    if "mobile robot" in text and "control" in text:
        return "论文围绕移动机器人（Mobile Robot）的导航控制（Navigation Control）组织方法，将规划、感知或反馈控制（Feedback Control）作为主要技术线索。"
    if abstract:
        return f"根据摘要，论文主题是：{_compact_text(abstract, limit=300)}"
    return "当前 metadata 未给出足够摘要；正式沉淀前需要回到 canonical MinerU Markdown 复核核心方法，并在存在 paper.tex 时补充核对公式。"


def _validation_setup(metadata: dict) -> str:
    abstract = _metadata_abstract(metadata)
    text = abstract.lower()
    if "sea trial" in text or "field trial" in text or "real-world" in text:
        return "摘要显示包含海试/现场验证，证据强度通常高于纯仿真；仍需检查原文任务、平台、海况和失败案例。"
    if "numerical simulation" in text or "simulation" in text or "simulations" in text:
        return "摘要显示以数值仿真/模拟实验为主，适合沉淀控制思路和对比指标，但工程可复现性需要谨慎标注。"
    if "experiment" in text or "validation" in text or "validate" in text:
        return "摘要显示包含实验或验证环节；正式写入时需从图表、实验配置和指标定义复核证据。"
    return "未在 metadata 摘要中自动识别清晰实验设置；需要从原文实验章节、图表和 MinerU 图片中补证据。"


def _caveat_lines(metadata: dict, research_decision: dict, reproduction_plan: dict) -> list[str]:
    panel = research_decision.get("panel_summary") or {}
    warnings = [str(item) for item in panel.get("warning_reviewers") or []]
    warnings.extend(str(item) for item in reproduction_plan.get("source_warnings") or [])
    venue = metadata.get("venue") or _metadata_metric(metadata, "venue")
    citations = _metadata_metric(metadata, "citation_count", "citations", "cited_by_count")
    if not venue:
        warnings.append("venue 未记录，论文质量需要依赖原文与引用/来源进一步判断。")
    if citations in (None, "", 0, "0"):
        warnings.append("引用数为 0 或未记录，不能把影响力当作主要沉淀理由。")
    if not warnings:
        return ["未发现阻断性 caveat；仍需在正式 wiki 写入时回到原文公式、图表和实验设置复核。"]
    return warnings[:5]


def _deposition_value(metadata: dict, title: str, evidence_map: dict) -> str:
    text = f"{title} {_metadata_abstract(metadata)}".lower()
    claim_count = len(evidence_map.get("claims") or [])
    if "ros-desert" in text or "middleware" in text:
        route = "AUV 实验软件栈、海试验证流程、ROS-DESERT 中间件经验"
    elif "economic model predictive control" in text or "empc" in text:
        route = "AUV 能源管理、经济 MPC、任务收益-能耗权衡"
    elif "lyapunov" in text and "fault" in text:
        route = "AUV 容错控制、LMPC、推进器故障与稳定性约束"
    elif "reinforcement learning" in text and ("docking" in text or "dock onto" in text):
        route = "AUV 对接控制、RL 控制策略、仿真到实机风险"
    elif "q-learning" in text or "deterministic policy gradient" in text:
        route = "AUV 强化学习跟踪控制、Q-learning/DPG 方法对比"
    else:
        route = "控制方法、实验设置、可复现实验 caveat"
    return f"适合交给 wiki skill 批量沉淀到主题节点：{route}。当前 evidence map 跟踪 {claim_count} 条 claim，正式页必须从原论文、公式和图片重读后写入。"


def _deposition_recommendation(research_decision: dict, reproduction_plan: dict) -> str:
    trust = _reading_trust_payload(research_decision, reproduction_plan)
    if trust["status"] == "blocked-by-critic":
        return "暂不沉淀"
    if trust["status"] == "accepted-with-caveats":
        return "谨慎沉淀"
    return "建议沉淀"


def _reading_trust_payload(research_decision: dict, reproduction_plan: dict) -> dict:
    if not research_decision and not reproduction_plan:
        return {
            "status": "source-ready",
            "read_mode": (
                "默认 fast-ingest：本报告只用于候选批准；未运行 reader/critic，正式 Wiki 必须从原论文、"
                "MinerU Markdown 主证据重读后写入；只有 Markdown 缺失、错误或歧义时才回退 PDF、figure/formula indexes 或图片证据。"
            ),
            "blocking_lenses": [],
            "warning_reviewers": [],
            "reproducibility_caveat_count": 0,
        }
    panel = research_decision.get("panel_summary") or {}
    blocking_lenses = panel.get("blocking_lenses") or []
    warning_reviewers = panel.get("warning_reviewers") or []
    source_warnings = reproduction_plan.get("source_warnings") or []
    if blocking_lenses:
        status = "blocked-by-critic"
        read_mode = "存在阻断性 critic lens，修复前不要推进正式沉淀或复用关键 claim。"
    elif warning_reviewers or source_warnings or reproduction_plan.get("human_gate_required"):
        status = "accepted-with-caveats"
        read_mode = "可以先读本报告，但复用 claim 前必须检查 evidence map、caveat 和原文证据。"
    else:
        status = "accepted"
        read_mode = "本报告可作为低阅读负担入口；需要公式、图表或实验细节时再打开完整 reader 与原文。"
    return {
        "status": status,
        "read_mode": read_mode,
        "blocking_lenses": blocking_lenses,
        "warning_reviewers": warning_reviewers,
        "reproducibility_caveat_count": len(source_warnings),
    }


def _reading_trust_lines(research_decision: dict, reproduction_plan: dict) -> list[str]:
    trust = _reading_trust_payload(research_decision, reproduction_plan)
    return [
        "## Reading Trust Status",
        "",
        f"- Status: {trust['status']}",
        f"- Read mode: {trust['read_mode']}",
        f"- Blocking lenses: {', '.join(trust['blocking_lenses']) or 'None'}",
        f"- Warning reviewers: {', '.join(trust['warning_reviewers']) or 'None'}",
        f"- Reproducibility caveats: {trust['reproducibility_caveat_count']}",
    ]


def _wiki_handoff_records(
    *,
    source_reader_target: str,
    reading_report_target: str,
    workflow_mode: str,
    reader_artifacts: list[str],
    critic_artifacts: list[str],
) -> list[dict]:
    records = [
        {
            "artifact_type": "source_reader",
            "target": source_reader_target,
            "route_status": "internal-evidence-only",
            "purpose": "Paper Source source-first navigator for the wiki skill to inspect before opening the source artifacts.",
            "primary_reader": "all",
            "workflow_mode": workflow_mode,
        },
        {
            "artifact_type": "reading_report",
            "target": reading_report_target,
            "route_status": "internal-evidence-only",
            "purpose": "Low-reading-burden entrypoint for human review before wiki skill deposition.",
            "primary_reader": "peer-reviewer",
            "workflow_mode": workflow_mode,
        },
    ]
    if reader_artifacts:
        records.append(
            {
                "artifact_type": "optional_reader_aids",
                "targets": reader_artifacts,
                "route_status": "internal-evidence-only",
                "purpose": "Optional navigation aids; never a substitute for source paper reading.",
                "workflow_mode": workflow_mode,
            }
        )
    if critic_artifacts:
        records.append(
            {
                "artifact_type": "optional_critic_aids",
                "targets": critic_artifacts,
                "route_status": "internal-evidence-only",
                "purpose": "Optional audit aids for important, reproducibility, or dispute-sensitive papers.",
                "workflow_mode": workflow_mode,
            }
        )
    return records


def _final_source_review_contract(slug: str, paper_root: Path | None = None) -> dict:
    return {
        "schema_version": "paper-source-final-source-review-contract-v1",
        "required": True,
        "suggested_output_path": "final-source-review.json",
        "required_artifacts": _source_first_artifacts(slug, paper_root),
        "must_record": final_source_review_must_record(),
        "required_wiki_skills": required_wiki_skills(),
        "formal_page_families": formal_page_family_names(),
        "research_review_fields": research_review_fields(),
        "page_lifecycle_states": page_lifecycle_states(),
        "verified_page_requirements": verified_page_requirements(),
        "record_command_flag": "--source-review <final-source-review.json>",
        "record_schema_version": "paper-source-final-source-review-v1",
    }


def _primary_source_reading_order(source_markdown: str, paper_root: Path | None) -> list[str]:
    return [
        "metadata.json",
        source_markdown,
        "mineru/images/*",
        "mineru/mineru-manifest.json",
        "figure-index.json",
        "formula-index.json",
        "asset-normalization-record.json",
    ]


def _build_wiki_ingest_brief(
    *,
    slug: str,
    title: str,
    source_reader_target: str,
    reading_report_target: str,
    editorial_summary_text: str,
    technical_reading_text: str,
    research_notes_text: str,
    evidence_map: dict,
    research_decision: dict,
    reproduction_plan: dict,
    workflow_mode: str = FAST_INGEST_MODE,
    reader_artifacts: list[str] | None = None,
    critic_artifacts: list[str] | None = None,
    wiki_deposition_task_path: str | None = None,
    full_text_evidence_index: dict | None = None,
    paper_root: Path | None = None,
) -> dict:
    workflow_mode = normalize_ingest_mode(workflow_mode)
    reader_artifacts = reader_artifacts or []
    critic_artifacts = critic_artifacts or []
    full_text_evidence_index = full_text_evidence_index or {}
    figure_index = _sidecar_status(paper_root, "figure-index.json") if paper_root else _missing_sidecar_status("figure-index.json")
    formula_index = _sidecar_status(paper_root, "formula-index.json") if paper_root else _missing_sidecar_status("formula-index.json")
    asset_normalization = (
        _sidecar_status(paper_root, "asset-normalization-record.json")
        if paper_root
        else _missing_sidecar_status("asset-normalization-record.json")
    )
    source_first_artifacts = _source_first_artifacts(slug, paper_root)
    source_markdown = _source_markdown_artifact(slug)
    optional_evidence_aids = [
        "figure-index.json",
        "formula-index.json",
        "asset-normalization-record.json",
    ]
    if paper_root is not None and has_nonempty_mineru_tex(paper_root):
        optional_evidence_aids.append("mineru/paper.tex")
    optional_evidence_aids.extend([*reader_artifacts, *critic_artifacts])
    claims = evidence_map.get("claims") if isinstance(evidence_map.get("claims"), list) else []
    roles = evidence_map.get("reader_roles") if isinstance(evidence_map.get("reader_roles"), list) else []
    quick_take = (
        _first_bullet_after_heading(editorial_summary_text, "## Central Claim")
        or "Start from the Chinese approval report, then open the source paper artifacts."
    )
    peer_note = (
        _first_bullet_after_heading(technical_reading_text, "## Method Decomposition")
        or "Inspect the source method, formulas, benchmark, and evidence grounding before reusing claims."
    )
    domain_note = (
        _first_bullet_after_heading(research_notes_text, "## Fit To Research Direction")
        or "Identify reusable concepts and cross-paper synthesis targets from the source paper before final wiki writing."
    )
    experiment_note = (
        _first_bullet_after_heading(research_notes_text, "## Follow-up Experiments")
        or "Treat reproduction as a compact caveat and keep theory/experiment ideas central."
    )
    entrypoints = {
        "reading_report": reading_report_target,
        "source_reader": source_reader_target,
        "wiki_ingest_brief": "wiki-ingest-brief.json",
    }
    if wiki_deposition_task_path:
        entrypoints["legacy_wiki_deposition_task"] = "wiki_deposition_task.json"
    if "reader/evidence-map.json" in reader_artifacts:
        entrypoints["evidence_map"] = "reader/evidence-map.json"
    if "reader/claim-support.json" in reader_artifacts:
        entrypoints["claim_support"] = "reader/claim-support.json"
    candidate_topic_source = "reader/research-notes.md" if "reader/research-notes.md" in reader_artifacts else source_markdown
    reading_path = [
        reading_report_target,
        *[
            artifact
            for artifact in [
                "reader/editorial-summary.md",
                "reader/technical-reading.md",
                "reader/research-notes.md",
                "reader/evidence-map.json",
                "reader/claim-support.json",
            ]
            if artifact in reader_artifacts
        ],
    ]
    return {
        "schema_version": "paper-source-wiki-ingest-brief-v1",
        "handoff_type": "agent-mediated-wiki-ingest",
        "paper_slug": slug,
        "title": title,
        "workflow_mode": workflow_mode,
        "trust_status": _reading_trust_payload(research_decision, reproduction_plan),
        "formal_page_families": formal_page_family_names(),
        "formal_page_family_records": formal_page_family_records(),
        "formal_frontmatter_schema": formal_frontmatter_schema(),
        "wiki_deposition_quality_gates": wiki_deposition_quality_gates(),
        "research_review_fields": research_review_fields(),
        "page_lifecycle_states": page_lifecycle_states(),
        "legacy_wiki_deposition_task": {
            "schema_version": "paper-source-wiki-deposition-task-v1",
            "status": "emitted" if wiki_deposition_task_path else "not-emitted",
            "task_path": str(wiki_deposition_task_path) if wiki_deposition_task_path else None,
            "canonical_handoff": "wiki-ingest-brief.json",
            "reason": "wiki-ingest-brief.json is the canonical Paper Source-to-Paper Wiki handoff",
            "compatibility_aliases": deposition_skill_compatibility_aliases(),
        },
        "agent_context_policy": agent_context_policy(),
        "wiki_framework_references": [
            {
                "name": "Ar9av/obsidian-wiki",
                "url": "https://github.com/Ar9av/obsidian-wiki",
                "role": "general agent-mediated Obsidian wiki framework",
            },
            {
                "name": "kepano/obsidian-skills",
                "url": "https://github.com/kepano/obsidian-skills",
                "role": "Obsidian syntax and companion skill conventions",
            },
            {
                "name": "initiatione/obsidian-wiki-dev",
                "url": "https://github.com/initiatione/obsidian-wiki-dev/tree/liuchf/wiki-skills",
                "role": "personalized vault-contract and wiki-skill rules",
            },
        ],
        "final_source_review_contract": _final_source_review_contract(slug, paper_root),
        "wiki_rule_source_model": wiki_rule_source_model(),
        "qmd_collection_policy": qmd_collection_policy(),
        "ingest_policy": {
            "authority": "Resolve the target vault contract first; local skills are helpers, not sole authority.",
            "workflow_mode": workflow_mode,
            "final_page_authority": "Final wiki pages are created by wiki skill batch distillation, not by Paper Source staging.",
            "write_model": "Wiki-skill batch distillation and merge from multiple Paper Source evidence bundles.",
            "paper_source_write_scope": "internal-underscore-artifacts-only",
            "formal_routes_suggested": False,
            "wiki_batch_handoff_required": True,
            "required_wiki_skills": required_wiki_skills(),
            "executor_policy": "Claude, Codex, or any other wiki-capable agent may perform the final write if they respect the same contract.",
            "merge_policy": "Search existing pages first; update or merge before creating duplicates.",
            "staged_writes_policy": "Respect the target vault staged-write convention when present.",
            "provenance_policy": "Keep extracted, inferred, and ambiguous claims distinguishable; use wiki-provenance and tag-taxonomy together.",
            "formal_page_policy": (
                "Use the seven Paper Wiki research page families as appropriate: "
                + ", ".join(formal_page_family_paths())
            ),
            "research_field_policy": (
                "final-source-review must record theory/formula/figure evidence, novelty, "
                "implementability, reproducibility risk, research gaps, and cost."
            ),
            "source_of_truth": "Markdown vault plus Paper Source source bundle; QMD/search indexes are retrieval aids only.",
            "qmd_collection_policy": qmd_collection_policy(),
            "source_first_policy": (
                f"Use MinerU Markdown ({source_markdown}) as the primary source for formulas, notation, "
                "method context, and prose before final wiki writing. Use paper.pdf, figure-index.json, "
                "formula-index.json, mineru/images/*, mineru/mineru-manifest.json, and "
                "asset-normalization-record.json as fallback or visual-evidence checks only when Markdown "
                "is missing, wrong, ambiguous, or insufficient. If non-empty native mineru/paper.tex exists, "
                "treat it as an optional cross-check, not a required or primary source. Missing native TeX "
                "is normal and must not block writing or recording. Reader and critic "
                "outputs, when present, are navigation and quality signals, not substitutes for the source paper."
            ),
            "reader_critic_policy": (
                "fast-ingest does not run reader/critic; reviewed-ingest adds reader for navigation; "
                "audited-ingest adds critic for key, reproducibility, contradiction, or explicit-review cases."
            ),
            "suggested_routes_only": False,
        },
        "vault_contract_resolution": [
            "target vault AGENTS.md",
            "_meta/agent-operating-contract.md",
            "_meta/schema.md",
            "_meta/taxonomy.md",
            "_meta/directory-structure.md",
            "vault-local staged-write and link-format settings",
            "generic wiki skill guidance",
        ],
        "obsidian_format_hints": {
            "frontmatter": (
                "Use formal page properties title, category, page_family, tags, aliases, sources, "
                "summary, provenance, base_confidence, lifecycle, lifecycle_changed, tier, created, and updated."
            ),
            "links": "Prefer vault-configured wikilinks for internal notes; use Markdown links for external URLs.",
            "tags": "Respect the vault taxonomy and aliases before inventing new tags.",
            "callouts": "Use callouts only when they improve reading, not as a fixed page template.",
        },
        "entrypoints": entrypoints,
        "formal_routes_suggested": False,
        "suggested_routes": [],
        "handoff_artifacts": _wiki_handoff_records(
            source_reader_target=source_reader_target,
            reading_report_target=reading_report_target,
            workflow_mode=workflow_mode,
            reader_artifacts=reader_artifacts,
            critic_artifacts=critic_artifacts,
        ),
        "candidate_topics": [
            {
                "source": candidate_topic_source,
                "hint": domain_note,
                "routing_policy": "wiki skill decides reusable concept pages after comparing multiple papers",
            }
        ],
        "candidate_clusters": [
            {
                "cluster_basis": "method, task, benchmark, limitation, contradiction, or formula family",
                "routing_policy": "create or update synthesis pages only after batch-level comparison",
            }
        ],
        "wiki_skill_handoff": {
            "required": True,
            "batch_required": True,
            "minimum_role": (
                _required_wiki_skill_loading_clause("The current agent must load")
                + " before writing or staging final pages."
            ),
            "required_skills": required_wiki_skills(),
            "compatibility_aliases": deposition_skill_compatibility_aliases(),
            "formal_page_families": formal_page_family_names(),
            "formal_frontmatter_schema": formal_frontmatter_schema(),
            "quality_gates": wiki_deposition_quality_gates(),
            "qmd_collection_policy": qmd_collection_policy(),
            "research_review_fields": research_review_fields(),
            "page_lifecycle_states": page_lifecycle_states(),
            "agent_context_policy": agent_context_policy(),
            "formal_page_rule": (
                "Do not promote Paper Source audit artifacts or per-paper pseudo concept/synthesis/report pages. "
                "Final pages are readable wiki pages produced by the wiki skill from source papers, formulas, "
                "figures, images, and compact Paper Source evidence aids across references/, concepts/, derivations/, "
                "experiments/, synthesis/, reports/, and opportunities/."
            ),
        },
        "role_lenses": {
            "nature_sci_editor": quick_take,
            "peer_reviewer": peer_note,
            "senior_domain_researcher": domain_note,
            "theory_and_experiment": experiment_note,
        },
        "source_bundle": {
            "raw_artifacts": source_first_artifacts,
            "primary_source_reading_order": _primary_source_reading_order(source_markdown, paper_root),
            "optional_evidence_aids": optional_evidence_aids,
            "formula_figure_review": {
                "formulas": (
                    f"Review central formulas, notation, and surrounding derivation context in MinerU Markdown ({source_markdown}) first. "
                    "Only fall back to paper.pdf, formula-index.json, figure-index.json, or image evidence when "
                    "Markdown is missing, wrong, ambiguous, or insufficient. If optional mineru/paper.tex exists, "
                    "use it only as a cross-check. Preserve important definitions, assumptions, derivation steps, "
                    "and notation rather than reducing them to prose."
                ),
                "figures_tables_images": (
                    "Interpret figures/tables/images from mineru/images/* with figure-index.json as the "
                    "label/path map; use reader/figures.md only when reviewed-ingest or audited-ingest produced "
                    "it. Preserve what each visual shows, the task/metric/baseline context, and any uncertainty "
                    "from the parse."
                ),
                "parse_uncertainty": (
                    "If formulas, tables, or figures appear missing, ambiguous, or parse-limited, inspect paper.pdf "
                    "before treating the content as absent."
                ),
            },
            "reader_artifacts": reader_artifacts,
            "critic_artifacts": critic_artifacts,
            "evidence": {
                "claim_count": len(claims),
                "reader_roles": roles,
                "exact_evidence_artifact": "reader/evidence-map.json" if "reader/evidence-map.json" in reader_artifacts else None,
                "claim_support_artifact": "reader/claim-support.json" if "reader/claim-support.json" in reader_artifacts else None,
                "full_text_evidence_index": full_text_evidence_index.get("path"),
                "full_text_evidence_index_status": full_text_evidence_index.get("status", "missing"),
                "full_text_chunk_count": full_text_evidence_index.get("chunk_count", 0),
                "full_text_input_hashes": full_text_evidence_index.get("input_hashes", {}),
                "full_text_warnings": full_text_evidence_index.get("warnings", []),
                "figure_index": figure_index,
                "formula_index": formula_index,
                "asset_normalization_record": asset_normalization,
                "vault_evidence_index": "_paper_source/meta/evidence-index.json",
            },
        },
        "reading_path": reading_path,
    }


def _wiki_ingest_brief_report_lines(wiki_ingest_brief: dict) -> list[str]:
    trust = wiki_ingest_brief.get("trust_status") or {}
    source_bundle = wiki_ingest_brief.get("source_bundle") or {}
    evidence = source_bundle.get("evidence") or {}
    optional_aids = source_bundle.get("optional_evidence_aids") or []
    handoff_artifacts = wiki_ingest_brief.get("handoff_artifacts") or []
    artifact_summary = ", ".join(str(item.get("artifact_type")) for item in handoff_artifacts) or "None"
    aid_text = ", ".join(str(item) for item in optional_aids) if optional_aids else "无；本次为 source-only fast-ingest"
    return [
        "## Wiki 沉淀价值",
        "",
        "- Paper Source 只写 `_paper_source/` 内部材料；正式图谱页由 wiki skill 批量沉淀生成。",
        "- `wiki-ingest-brief.json` 是证据交接文件，不是正式 wiki 页面路线。",
        f"- 可信状态：{trust.get('status', '')}；内部 handoff artifacts：{artifact_summary}",
        f"- 已跟踪证据 claim：{evidence.get('claim_count', 0)}",
        f"- 可选 reader/critic 辅助证据：{aid_text}",
        "- 正式路径、frontmatter、标签、链接、合并策略和 staged writes 均由目标 vault contract 与 wiki skill 决定。",
        "- 进入正式写入前以 MinerU Markdown 为主重读原文、公式、符号和上下文；只有 Markdown 缺失、错误或歧义时才回退 PDF、figure/formula indexes 或图片证据；reader/critic 只有在本次模式实际生成时才作为辅助。",
    ]


def _reading_report_lines(
    *,
    slug: str,
    title: str,
    workflow_mode: str,
    source_reader_target: str,
    reader_text: str,
    editorial_summary_text: str,
    technical_reading_text: str,
    research_notes_text: str,
    figures_text: str,
    reproducibility_text: str,
    evidence_map: dict,
    research_decision: dict,
    reproduction_plan: dict,
    wiki_ingest_brief: dict,
    metadata: dict,
    decision_frontmatter_lines: list[str] | None = None,
) -> list[str]:
    panel = research_decision.get("panel_summary") or {}
    method_take = _first_bullet_after_heading(technical_reading_text, "## Method Decomposition")
    fit_take = _first_bullet_after_heading(research_notes_text, "## Fit To Research Direction")
    experiment_take = _first_bullet_after_heading(research_notes_text, "## Follow-up Experiments")
    figure_take = _first_bullet_after_heading(figures_text, "## Figure Inventory")
    reproducibility_take = _first_bullet_after_heading(reproducibility_text, "## Reproducibility Signals")
    source_warnings = reproduction_plan.get("source_warnings") or []
    claims = evidence_map.get("claims") if isinstance(evidence_map.get("claims"), list) else []
    roles = evidence_map.get("reader_roles") if isinstance(evidence_map.get("reader_roles"), list) else []
    abstract = _metadata_abstract(metadata)
    term_text = " ".join([title, abstract, reader_text, technical_reading_text])
    terms = _term_pairs_for_text(term_text)
    trust = _reading_trust_payload(research_decision, reproduction_plan)
    recommendation = _deposition_recommendation(research_decision, reproduction_plan)
    reader_available = bool(reader_text.strip())
    reader_method_line = (
        f"- reader 技术线索：{_reader_take_or_note(method_take, 'reader 技术摘要未达到审批报告可读标准；正式写入时请回到原文方法章节和 evidence map。')}"
        if reader_available
        else "- source-first 复核重点：正式写入时以 MinerU Markdown 回读方法、公式、符号和实验设置；只有 Markdown 缺失、错误或歧义时才回退 PDF、figure/formula indexes 或图片证据。"
    )
    fit_line = (
        f"- 研究方向贴合度：{_reader_take_or_note(fit_take, '需要由 wiki skill 在批量沉淀时结合目标 vault taxonomy 判断。')}"
        if reader_available
        else "- 研究方向贴合度：本报告只给候选判断；正式沉淀时由 wiki skill 结合目标 vault taxonomy 和多篇论文批量判断。"
    )
    evidence_lines = [
        f"- 可信状态：{trust['status']}",
        f"- 阅读模式：{trust['read_mode']}",
        f"- 阻断 lens：{', '.join(trust['blocking_lenses']) or 'None'}",
        f"- 警告审稿器：{', '.join(trust['warning_reviewers']) or 'None'}",
        f"- 复现 caveat：{trust['reproducibility_caveat_count']}",
    ]
    if reader_available:
        evidence_lines.extend(
            [
                f"- 已跟踪证据 claim：{len(claims)}；reader roles：{', '.join(str(role) for role in roles) or 'None recorded'}",
                "- 精确证据地址以 `reader/evidence-map.json` 和 `reader/claim-support.json` 为准。",
            ]
        )
    else:
        evidence_lines.append("- 默认快路径未生成 reader evidence map；正式页证据以 MinerU Markdown 为主，PDF、figure/formula indexes 和图片证据只在 Markdown 缺失、错误或歧义时用于复核。")
    if research_decision:
        quality_lines = [
            f"- critic 共识：{panel.get('consensus', research_decision.get('recommendation', ''))}",
            f"- 阻断 lenses：{', '.join(panel.get('blocking_lenses') or []) or 'None'}",
            f"- 警告 reviewers：{', '.join(panel.get('warning_reviewers') or []) or 'None'}",
        ]
    else:
        quality_lines = [
            f"- workflow mode：{workflow_mode}",
            "- reader/critic：本次未作为默认必经步骤运行；只有解析质量差、关键复现/综述/决策、或用户显式要求时再补 reviewed/audited ingest。",
        ]
    lines = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"workflow_mode: {workflow_mode}",
        "stage: staging",
        "page_type: reading_report",
        "formal_page: false",
        f"source_reader: {source_reader_target}",
        *(decision_frontmatter_lines or []),
        "---",
        "",
        f"# {title} 阅读报告",
        "",
        f"Source handoff：`{source_reader_target}`",
        "",
        "## 快速判断",
        "",
        f"- 这是一份供人工 gate 决策的轻量审批报告；正式 wiki 页不得直接复制本报告，必须由 wiki skill 依据原论文、公式和图片批量沉淀。",
        f"- 方法概览：{_method_idea(metadata, title)}",
        f"- 沉淀建议：{recommendation}",
        "",
        "## 论文身份",
        "",
        *_identity_lines(metadata),
        "",
        "## 术语中英对照",
        "",
        *(f"- {term}" for term in terms),
        "",
        "## 理论与方法",
        "",
        f"- {_method_idea(metadata, title)}",
        reader_method_line,
        fit_line,
        "",
        "## 实验/验证方式",
        "",
        f"- {_validation_setup(metadata)}",
        f"- 可继续检查：{_reader_take_or_note(experiment_take, '原文实验章节、指标定义、消融/对比、图表和失败案例。')}",
        "",
        "## 证据强度与可信状态",
        "",
        *evidence_lines,
        "",
        "## 主要 Caveat",
        "",
        *[f"- {warning}" for warning in _caveat_lines(metadata, research_decision, reproduction_plan)],
        "",
        *_wiki_ingest_brief_report_lines(wiki_ingest_brief),
        "",
        "- " + _deposition_value(metadata, title, evidence_map),
        "",
        "## 质量门禁",
        "",
        *quality_lines,
        "",
        "## 沉淀建议",
        "",
        f"- {recommendation}",
    ]
    if figure_take:
        lines.extend(["", "## 图表速读", "", f"- {figure_take}"])
    lines.extend(["", "## 复现 Caveat", ""])
    if reproducibility_take:
        lines.append(f"- {reproducibility_take}")
    if source_warnings:
        lines.extend(f"- {warning}" for warning in source_warnings)
    if not reproducibility_take and not source_warnings:
        lines.append("- 当前轻量报告未提升阻断性复现 caveat；正式写入仍需检查原文实验配置和资源可得性。")
    lines.append("")
    return lines


def wiki_rule_source_model() -> dict:
    return {
        "principle": (
            "Obsidian/LLM Wiki construction and write rules are resolved from the target vault "
            "contract and framework references; local installed skills are execution helpers. "
            "Keep Obsidian syntax, Paper Wiki paper-evidence semantics, and vault-local governance "
            "as separate layers. "
            "The paper-research-wiki skill is the canonical paper wiki layer. "
            "The final wiki executor is agent-neutral and may be Claude, Codex, or any other "
            "wiki-capable agent that follows the same contract."
        ),
        "governance_layers": [
            {
                "layer": "obsidian_syntax",
                "source": "kepano/obsidian-skills",
                "owns": [
                    "YAML properties/frontmatter",
                    "tags and aliases",
                    "wikilinks",
                    "Markdown links",
                    "embeds",
                    "callouts",
                    "Obsidian math delimiters",
                    "bases and canvas syntax",
                ],
            },
            {
                "layer": "paper_wiki_evidence",
                "source": PAPER_WIKI_CANONICAL_SKILL,
                "owns": [
                    "source-grounded paper claims",
                    "formal page families",
                    "formula reasoning chains",
                    "figure/table evidence cards",
                    "formal page relationships",
                    "evidence tiers",
                    "final-source-review.json readiness",
                ],
            },
            {
                "layer": "local_vault_governance",
                "source": "target vault AGENTS.md and _meta/*",
                "owns": [
                    "local taxonomy",
                    "page ownership",
                    "staged writes",
                    "QMD scope",
                    "migration and retirement policy",
                ],
            },
        ],
        "execution_agent_policy": {
            "allowed_executors": [
                "Claude",
                "Codex",
                "other wiki-capable agents",
            ],
            "brand_neutrality": (
                "Any wiki-capable agent may execute final writes if it follows the target vault "
                "contract, source-first review, human approval, and final-source-review gates."
            ),
            "local_skills_role": "helpers, not authority",
        },
        "resolution_order": [
            {
                "priority": 1,
                "source": "current user instruction",
                "role": "Session-specific goal, language, and safety override.",
            },
            {
                "priority": 2,
                "source": "target vault AGENTS.md",
                "role": "Owner-specific conventions, domain vocabulary, writing style, and safety boundaries.",
            },
            {
                "priority": 3,
                "source": "target vault _meta/agent-operating-contract.md",
                "role": "Agent operating rules for this vault when present.",
            },
            {
                "priority": 4,
                "source": "target vault _meta/schema.md, _meta/taxonomy.md, _meta/directory-structure.md",
                "role": "Final routing, page classes, tag vocabulary, link policy, staged writes, and merge rules.",
            },
            {
                "priority": 5,
                "source": f"{PAPER_WIKI_CANONICAL_SKILL} (Paper Wiki canonical paper wiki layer)",
                "role": "canonical paper wiki workflow layer for Paper Source bundles",
            },
            {
                "priority": 6,
                "source": "initiatione/obsidian-wiki-dev liuchf/wiki-skills",
                "role": "Personalized multi-vault contract model and QMD/source-of-truth policy.",
            },
            {
                "priority": 7,
                "source": "Ar9av/obsidian-wiki",
                "role": "General agent-mediated LLM Wiki architecture, manifest/index/log, provenance, and merge pattern.",
            },
            {
                "priority": 8,
                "source": "kepano/obsidian-skills",
                "role": "Obsidian syntax authority: properties/frontmatter, tags, wikilinks, Markdown links, embeds, callouts, math, bases, and canvas conventions.",
            },
            {
                "priority": 9,
                "source": "local llm-wiki / wiki-ingest / obsidian-markdown skills",
                "role": "Installed execution adapters; they do not replace the target vault contract or framework repos.",
            },
        ],
        "must_read_before_final_write": [
            "target vault AGENTS.md",
            "_meta/agent-operating-contract.md",
            "_meta/schema.md",
            "_meta/taxonomy.md",
            "_meta/directory-structure.md",
            "index.md",
            "log.md",
            ".manifest.json",
        ],
        "qmd_collection_policy": qmd_collection_policy(),
        "write_contract_requirements": [
            "Search existing pages with index/frontmatter, QMD when configured, and grep before creating a new page.",
            "Use QMD only with the paper-research-wiki qmd collection boundary: formal page families plus AGENTS.md, index.md, hot.md, log.md, and _meta/ contract pages may be indexed; _paper_source/**, legacy _epi/**, .obsidian/**, and .claude/** must be ignored.",
            "Merge or update existing notes before creating duplicates.",
            "Keep Markdown vault files as the source of truth; QMD and search indexes are retrieval aids.",
            "Preserve source provenance and distinguish extracted, inferred, and ambiguous claims.",
            "Final wiki pages must be grounded in the source paper artifacts, not reader summaries alone.",
            "Use MinerU Markdown as the primary source for formulas, notation, method context, and prose; missing native TeX is normal and must not block writing or recording.",
            "Use paper.pdf, formula-index.json, figure-index.json, and image evidence only when MinerU Markdown is missing, wrong, ambiguous, or insufficient.",
            "Review central formulas, figures, tables, and image evidence before distilling reusable wiki claims.",
            "Respect vault-local staged writes, link format, language policy, taxonomy, and frontmatter schema.",
        ],
    }
