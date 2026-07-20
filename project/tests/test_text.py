import pytest

from nz_open_data_assistant.text import clean_html, cosine, hash_embedding, rewrite_query


def test_clean_html_removes_markup_and_decodes_entities() -> None:
    assert clean_html("<p>Auckland &amp; transport</p>") == "Auckland & transport"


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    first = hash_embedding("Auckland population data")
    second = hash_embedding("Auckland population data")
    assert first == second
    assert cosine(first, second) == pytest.approx(1.0)


def test_rewrite_query_adds_domain_synonyms() -> None:
    rewritten = rewrite_query("Auckland bus data")
    assert "public transport" in rewritten
    assert "local board" in rewritten
