import pytest

from paper_source.lexical_match import term_matches_text


@pytest.mark.parametrize(
    ("term", "text"),
    [
        ("control", "controls"),
        ("control", "controlled"),
        ("control", "controller"),
        ("method", "methods"),
        ("attitude", "attitudes"),
        ("model", "modeling"),
    ],
)
def test_lexical_match_keeps_supported_inflections(term, text):
    assert term_matches_text(term, text)


@pytest.mark.parametrize(
    ("term", "text"),
    [
        ("learning", "learningly"),
        ("algorithm", "algorithmically"),
        ("robot", "robotic"),
        ("method", "methodology"),
        ("safety", "safely"),
    ],
)
def test_lexical_match_rejects_overbroad_derivational_matches(term, text):
    assert not term_matches_text(term, text)
