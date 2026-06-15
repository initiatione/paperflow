from __future__ import annotations

import json
from typing import Any


def frontmatter_block(text: str) -> tuple[dict[str, Any], str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None
    frontmatter: dict[str, Any] = {}
    current_map_key: str | None = None
    current_nested_key: str | None = None
    for raw_line in lines[1:end_index]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  ") and current_map_key:
            nested = raw_line.strip()
            if raw_line.startswith("    ") and current_nested_key:
                if nested.startswith("- "):
                    nested_map = frontmatter.get(current_map_key)
                    if not isinstance(nested_map, dict):
                        nested_map = {}
                        frontmatter[current_map_key] = nested_map
                    current_value = nested_map.get(current_nested_key)
                    if not isinstance(current_value, list):
                        current_value = []
                        nested_map[current_nested_key] = current_value
                    current_value.append(strip_frontmatter_scalar(nested[2:].strip()))
                    continue
            if nested.startswith("- "):
                value = strip_frontmatter_scalar(nested[2:].strip())
                current_value = frontmatter.get(current_map_key)
                if not isinstance(current_value, list):
                    current_value = []
                    frontmatter[current_map_key] = current_value
                current_value.append(value)
                continue
            if ":" in nested:
                key, value = nested.split(":", 1)
                nested_map = frontmatter.get(current_map_key)
                if not isinstance(nested_map, dict):
                    nested_map = {}
                    frontmatter[current_map_key] = nested_map
                if isinstance(nested_map, dict):
                    nested_key = key.strip()
                    nested_value = value.strip()
                    nested_map[nested_key] = nested_value
                    current_nested_key = nested_key if not nested_value else None
            continue
        if ":" not in raw_line or raw_line[0].isspace():
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        frontmatter[key] = value
        current_map_key = key if not value else None
        current_nested_key = None
    body = "\n".join(lines[end_index + 1 :])
    return frontmatter, body


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    parsed = frontmatter_block(text)
    if parsed is None:
        return {}, text
    return parsed


def strip_frontmatter(text: str) -> str:
    return parse_frontmatter(text)[1]


def dump_frontmatter_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def frontmatter_value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return False
    text = str(value).strip()
    return text in {"", "[]", "{}", "null", "None"}


def strip_frontmatter_scalar(value: str) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def split_inline_frontmatter_list(value: str) -> list[str]:
    text = str(value).strip()
    if not (text.startswith("[") and text.endswith("]")):
        return [strip_frontmatter_scalar(text)] if text else []
    if text.startswith("[[") and text.endswith("]]"):
        return [strip_frontmatter_scalar(text)]

    inner = text[1:-1].strip()
    if not inner:
        return []
    entries: list[str] = []
    token: list[str] = []
    quote: str | None = None
    escaped = False
    for char in inner:
        if quote:
            if escaped:
                token.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
                continue
            token.append(char)
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == ",":
            entry = strip_frontmatter_scalar("".join(token))
            if entry:
                entries.append(entry)
            token = []
            continue
        token.append(char)
    entry = strip_frontmatter_scalar("".join(token))
    if entry:
        entries.append(entry)
    return entries


def frontmatter_source_entries(value: Any) -> list[str]:
    if isinstance(value, list):
        return [strip_frontmatter_scalar(str(item)) for item in value if strip_frontmatter_scalar(str(item))]
    return split_inline_frontmatter_list(str(value))
