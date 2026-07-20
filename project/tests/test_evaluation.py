import pytest

from nz_open_data_assistant.evaluation import ndcg_at_k, reciprocal_rank


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["wrong", "right"], {"right"}) == 0.5
    assert reciprocal_rank(["wrong"], {"right"}) == 0.0


def test_ndcg() -> None:
    assert ndcg_at_k(["a", "b"], {"a"}) == pytest.approx(1.0)
    assert 0 < ndcg_at_k(["x", "a"], {"a"}) < 1
