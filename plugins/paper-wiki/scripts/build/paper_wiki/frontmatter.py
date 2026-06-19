from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


FRONTMATTER = re.compile(r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n?", re.DOTALL)
BODY_METADATA_BLOCK = re.compile(
    r"(?m)^---\s*\n(?=[A-Za-z0-9_-]+:\s*(?:\n|[^\n]))(?P<body>.*?)(?:\n---\s*$|\n---\s*\n)",
    re.DOTALL,
)


@dataclass(frozen=True)
class FrontmatterDocument:
    frontmatter: dict[str, Any]
    body: str
    has_frontmatter: bool
    issues: list[dict[str, Any]] = field(default_factory=list)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _container_for_next(lines: list[str], index: int) -> Any:
    for next_line in lines[index + 1 :]:
        if not next_line.strip() or next_line.lstrip().startswith("#"):
            continue
        return [] if re.match(r"^\s*-\s+", next_line) else {}
    return {}


def parse_frontmatter_block(block: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = block.splitlines()
    for index, raw_line in enumerate(lines):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        list_match = re.match(r"^-\s+(.*)$", line)
        if list_match:
            if not isinstance(parent, list):
                continue
            parent.append(parse_scalar(list_match.group(1)))
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not key_match or not isinstance(parent, dict):
            continue
        key, value = key_match.groups()
        if value == "":
            container = _container_for_next(lines, index)
            parent[key] = container
            stack.append((indent, container))
        else:
            parent[key] = parse_scalar(value)
    return root


def parse_frontmatter(text: str) -> FrontmatterDocument:
    match = FRONTMATTER.match(text)
    issues: list[dict[str, Any]] = []
    if match:
        body = text[match.end() :]
        frontmatter = parse_frontmatter_block(match.group("frontmatter"))
        has_frontmatter = True
    else:
        body = text
        frontmatter = {}
        has_frontmatter = False
    if BODY_METADATA_BLOCK.search(body):
        issues.append(
            {
                "code": "body_frontmatter_block_unsupported",
                "message": "Only the first top frontmatter block is supported for metadata.",
            }
        )
    return FrontmatterDocument(
        frontmatter=frontmatter,
        body=body,
        has_frontmatter=has_frontmatter,
        issues=issues,
    )


def _needs_quotes(value: str) -> bool:
    return (
        value == ""
        or value.strip() != value
        or value.lower() in {"null", "true", "false"}
        or bool(re.search(r"[:#\[\]{}]|^\d+$|^-", value))
    )


def _render_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if _needs_quotes(text):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _render_value(key: str, value: Any, indent: int, lines: list[str]) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for child_key, child_value in value.items():
            _render_value(str(child_key), child_value, indent + 2, lines)
        return
    if isinstance(value, list):
        lines.append(f"{prefix}{key}:")
        for item in value:
            item_prefix = " " * (indent + 2)
            if isinstance(item, dict):
                lines.append(f"{item_prefix}-")
                for child_key, child_value in item.items():
                    _render_value(str(child_key), child_value, indent + 4, lines)
            else:
                lines.append(f"{item_prefix}- {_render_scalar(item)}")
        return
    lines.append(f"{prefix}{key}: {_render_scalar(value)}")


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in frontmatter.items():
        _render_value(str(key), value, 0, lines)
    return "\n".join(lines)


def render_document(frontmatter: dict[str, Any], body: str) -> str:
    rendered = render_frontmatter(frontmatter)
    return f"---\n{rendered}\n---\n{body}"


def replace_frontmatter(text: str, frontmatter: dict[str, Any]) -> str:
    parsed = parse_frontmatter(text)
    return render_document(frontmatter, parsed.body)
