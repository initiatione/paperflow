from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[a-z0-9]+")
DERIVATIONAL_SUFFIXES = {
    "al",
    "ally",
    "ed",
    "er",
    "ers",
    "es",
    "ing",
    "ion",
    "ions",
    "ive",
    "led",
    "ler",
    "lers",
    "ling",
    "ly",
    "ment",
    "ments",
    "or",
    "ors",
    "s",
    "tion",
    "tions",
}


def lexical_tokens(value: object) -> list[str]:
    return TOKEN_RE.findall(str(value or "").lower())


def _token_forms(token: str) -> set[str]:
    forms = {token}
    if len(token) > 3 and token.endswith("ies"):
        forms.add(token[:-3] + "y")
    if len(token) > 3 and token.endswith("s"):
        forms.add(token[:-1])
    return forms


def _token_matches(term_token: str, text_token: str) -> bool:
    if _token_forms(term_token) & _token_forms(text_token):
        return True
    if len(term_token) < 5 or not text_token.startswith(term_token):
        return False
    return text_token[len(term_token) :] in DERIVATIONAL_SUFFIXES


def term_matches_text(term: object, text: object) -> bool:
    term_text = " ".join(str(term or "").strip().lower().split())
    text_value = str(text or "").lower()
    if not term_text or not text_value:
        return False
    term_tokens = lexical_tokens(term_text)
    text_tokens = lexical_tokens(text_value)
    if not term_tokens:
        return term_text in " ".join(text_value.split())
    if not text_tokens:
        return False
    if len(term_tokens) == 1:
        return any(_token_matches(term_tokens[0], token) for token in text_tokens)

    index = 0
    for term_token in term_tokens:
        matched = False
        while index < len(text_tokens):
            if _token_matches(term_token, text_tokens[index]):
                matched = True
                index += 1
                break
            index += 1
        if not matched:
            return False
    return True


def matched_terms(text: object, terms: list[str] | tuple[str, ...]) -> list[str]:
    return [term for term in terms if term_matches_text(term, text)]
