from nz_open_data_assistant.answer_evaluation import score_answer


def test_answer_score_measures_terms_and_citations() -> None:
    score = score_answer("Auckland bus data from Council [1]", ["bus", "Council"], 1)
    assert score == {"expected_term_coverage": 1.0, "citation_coverage": 1.0}


def test_answer_score_handles_no_sources() -> None:
    score = score_answer("No source found", ["missing"], 0)
    assert score["citation_coverage"] == 1.0
