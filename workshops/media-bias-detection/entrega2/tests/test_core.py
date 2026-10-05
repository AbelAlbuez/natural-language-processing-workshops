import re

import pytest

from core import counter_metrics, keyword_pattern, msttr, ngrams, normalize, tokenize, ttr, yules_k


def test_normalization_and_missing_values():
    assert normalize("Corrupcion: BOGOTÁ, fraude!") == "corrupcion bogota fraude"
    assert normalize(None) == ""
    assert normalize(float("nan")) == ""


def test_stopwords_use_same_normalization():
    assert tokenize("Señaló la reforma en Bogotá", {"senalo", "la", "en"}) == ["reforma", "bogota"]


def test_keyword_boundaries_and_accents():
    pattern = keyword_pattern(["corrupción", "reforma tributaria", "eln"])
    assert re.search(pattern, normalize("Una reforma tributaria"))
    assert re.search(pattern, normalize("Corrupcion"))
    assert not re.search(pattern, "capacidad reformada elnino")


def test_empty_keyword_list_is_rejected():
    with pytest.raises(ValueError):
        keyword_pattern([])


def test_single_token_and_empty_diversity():
    assert yules_k([]) == yules_k(["reforma"]) == 0
    assert ttr([]) == 0
    assert ttr(["reforma"]) == 1


def test_yule_k_is_not_simpson():
    assert yules_k(["reforma", "reforma"]) == 5000
    assert yules_k(["reforma", "impuesto"]) == 0


def test_msttr_discards_incomplete_tail():
    assert msttr(["reforma", "reforma", "impuesto"], window=2) == 0.5
    with pytest.raises(ValueError):
        msttr([], window=0)


def test_ngrams_do_not_cross_documents():
    assert ngrams(["reforma", "tributaria", "colombia"], 2) == ["reforma tributaria", "tributaria colombia"]
    assert ngrams([], 3) == []


def test_aggregated_metrics():
    metrics = counter_metrics({"reforma": 2, "impuesto": 1})
    assert metrics["tokens"] == 3
    assert metrics["vocabulario"] == 2
    assert metrics["yule_k_agregado"] == pytest.approx(20000 / 9)


def test_holm_returns_original_order():
    from research_stats import holm_adjust
    assert holm_adjust([0.04, 0.001, 0.03]).tolist() == pytest.approx([0.06, 0.003, 0.06])


def test_chi_square_requires_counts():
    from research_stats import chi_square_counts
    with pytest.raises(ValueError):
        chi_square_counts([[1.5, 2], [3, 4]])
    with pytest.raises(ValueError):
        chi_square_counts([[0, 0], [3, 4]])


def test_chi_square_effect_and_expected_counts():
    from research_stats import chi_square_counts
    result = chi_square_counts([[50, 50], [50, 50]])
    assert result["p"] == 1
    assert result["cramers_v"] == 0
    assert result["asymptotic_cells_ok"]


def test_zero_success_does_not_imply_zero_rate():
    from research_stats import wilson_interval
    low, high = wilson_interval(0, 98)
    assert low == pytest.approx(0)
    assert 0.03 < high < 0.04


def test_block_bootstrap_constant_series():
    from research_stats import block_bootstrap_mean
    result = block_bootstrap_mean([2, 2, 2, 2], repetitions=30)
    assert result["low"] == result["high"] == result["mean"] == 2