import pytest

from dartsanalytics.experiments.comparison import ExperimentComparison, ExperimentMetricResult
from dartsanalytics.experiments.decision import Decision, decide


def _comparison(metrics, *, baseline_count=40, test_count=40) -> ExperimentComparison:
    return ExperimentComparison(baseline_throw_count=baseline_count, test_throw_count=test_count, metrics=metrics)


def _metric(name, baseline, test, *, higher_is_better) -> ExperimentMetricResult:
    delta = (test - baseline) if (baseline is not None and test is not None) else None
    return ExperimentMetricResult(
        metric_name=name, baseline_value=baseline, test_value=test, delta=delta, higher_is_better=higher_is_better
    )


def test_insufficient_throws_returns_retest():
    comparison = _comparison(
        [_metric("bull_rate", 0.1, 0.5, higher_is_better=True)], baseline_count=10, test_count=10
    )
    result = decide(comparison)
    assert result.decision == Decision.RETEST
    assert result.evaluated_count == 0


def test_majority_improved_returns_continue():
    metrics = [
        _metric("bull_rate", 0.1, 0.3, higher_is_better=True),  # improved
        _metric("mean_center_distance", 0.2, 0.1, higher_is_better=False),  # improved (lower is better)
        _metric("countup_average", 10.0, 10.2, higher_is_better=True),  # within margin (noise)
    ]
    result = decide(_comparison(metrics))
    assert result.decision == Decision.CONTINUE
    assert result.improved_count == 2
    assert result.worsened_count == 0


def test_majority_worsened_returns_revert():
    metrics = [
        _metric("bull_rate", 0.3, 0.1, higher_is_better=True),  # worsened
        _metric("mean_center_distance", 0.1, 0.3, higher_is_better=False),  # worsened
        _metric("countup_average", 10.0, 10.2, higher_is_better=True),  # noise
    ]
    result = decide(_comparison(metrics))
    assert result.decision == Decision.REVERT
    assert result.worsened_count == 2


def test_all_within_margin_returns_retest():
    metrics = [
        _metric("bull_rate", 0.30, 0.31, higher_is_better=True),
        _metric("countup_average", 10.0, 10.3, higher_is_better=True),
    ]
    result = decide(_comparison(metrics))
    assert result.decision == Decision.RETEST


def test_tied_improved_and_worsened_returns_retest():
    metrics = [
        _metric("bull_rate", 0.1, 0.3, higher_is_better=True),  # improved
        _metric("mean_center_distance", 0.1, 0.3, higher_is_better=False),  # worsened
    ]
    result = decide(_comparison(metrics))
    assert result.decision == Decision.RETEST
    assert result.improved_count == 1
    assert result.worsened_count == 1


def test_missing_data_metrics_are_not_evaluated():
    metrics = [
        _metric("bull_rate", None, 0.3, higher_is_better=True),
        _metric("countup_average", 10.0, 15.0, higher_is_better=True),
    ]
    result = decide(_comparison(metrics))
    assert result.evaluated_count == 1
    assert result.decision == Decision.CONTINUE


def test_no_evaluable_metrics_returns_retest():
    metrics = [_metric("bull_rate", None, None, higher_is_better=True)]
    result = decide(_comparison(metrics))
    assert result.decision == Decision.RETEST
    assert result.evaluated_count == 0


def test_reasoning_is_populated_and_never_asserts_certainty():
    metrics = [_metric("bull_rate", 0.1, 0.3, higher_is_better=True)]
    result = decide(_comparison(metrics))
    assert len(result.reasoning) >= 1
    assert all(isinstance(r, str) for r in result.reasoning)


def test_to_dict_is_json_serializable():
    import json

    metrics = [_metric("bull_rate", 0.1, 0.3, higher_is_better=True)]
    result = decide(_comparison(metrics))
    json.dumps(result.to_dict(), ensure_ascii=False)
