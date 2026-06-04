from __future__ import annotations

from core.paper_config_hash import (
    PAPER_CONFIG_HASH_POLICY,
    compute_paper_config_hash,
    normalize_paper_config_for_hash,
)


def _config(**overrides):
    payload = {
        "schema_version": 1,
        "plan_date": "2026-05-20",
        "generated_at": "2026-05-20T09:00:00",
        "run_id": "run-a",
        "report_path": "C:/tmp/report-a.json",
        "api_token": "secret-a",
        "final_config": {
            "max_positions": 10,
            "score_threshold": 70,
            "target_cash_ratio": 0.2,
            "strategy_weights": {"rs": 1.0, "turtle": 1.0},
        },
        "market_status_summary": {"regime": "BULL"},
    }
    payload.update(overrides)
    return payload


def test_hash_output_uses_policy_sha256_prefix() -> None:
    digest = compute_paper_config_hash(_config())
    assert PAPER_CONFIG_HASH_POLICY == "paper_config_hash.v1"
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_key_order_does_not_change_hash() -> None:
    first = _config(final_config={"max_positions": 10, "score_threshold": 70})
    second = {
        "market_status_summary": {"regime": "BULL"},
        "final_config": {"score_threshold": 70, "max_positions": 10},
        "schema_version": 1,
        "plan_date": "2026-05-20",
    }
    assert compute_paper_config_hash(first) == compute_paper_config_hash(second)


def test_volatile_runtime_fields_do_not_change_hash() -> None:
    baseline = _config()
    regenerated = _config(
        generated_at="2026-05-20T10:00:00",
        run_id="run-b",
        report_path="D:/other/report-b.json",
        local_path="D:/tmp/local.json",
        source="capture_daily_plan_baseline",
        producer_source="replay_daily_plan_diff",
        updated_at="2026-05-20T10:01:00",
    )
    assert compute_paper_config_hash(baseline) == compute_paper_config_hash(regenerated)


def test_provenance_source_fields_do_not_change_hash() -> None:
    source_only = _config(source="capture_daily_plan_baseline")
    producer_source_only = _config(producer_source="capture_daily_plan_baseline")
    different_source = _config(source="replay_daily_plan_diff")
    different_producer_source = _config(producer_source="replay_daily_plan_diff")

    baseline_hash = compute_paper_config_hash(source_only)
    assert baseline_hash == compute_paper_config_hash(producer_source_only)
    assert baseline_hash == compute_paper_config_hash(different_source)
    assert baseline_hash == compute_paper_config_hash(different_producer_source)


def test_secret_like_fields_are_excluded_from_hash_input() -> None:
    normalized = normalize_paper_config_for_hash(
        _config(api_token="secret-b", notion_secret="secret-c", env_value="prod")
    )
    assert "api_token" not in normalized
    assert "notion_secret" not in normalized
    assert "env_value" not in normalized
    assert compute_paper_config_hash(_config(api_token="secret-a")) == compute_paper_config_hash(
        _config(api_token="secret-b")
    )


def test_semantic_field_change_changes_hash() -> None:
    baseline = _config()
    changed = _config(
        final_config={
            "max_positions": 11,
            "score_threshold": 70,
            "target_cash_ratio": 0.2,
            "strategy_weights": {"rs": 1.0, "turtle": 1.0},
        }
    )
    assert compute_paper_config_hash(baseline) != compute_paper_config_hash(changed)


def test_semantic_source_fields_remain_hash_inputs() -> None:
    baseline = _config(
        strategy_source="strategy-a",
        universe_source="universe-a",
        market_data_source="market-a",
    )

    assert compute_paper_config_hash(baseline) != compute_paper_config_hash(
        _config(strategy_source="strategy-b", universe_source="universe-a", market_data_source="market-a")
    )
    assert compute_paper_config_hash(baseline) != compute_paper_config_hash(
        _config(strategy_source="strategy-a", universe_source="universe-b", market_data_source="market-a")
    )
    assert compute_paper_config_hash(baseline) != compute_paper_config_hash(
        _config(strategy_source="strategy-a", universe_source="universe-a", market_data_source="market-b")
    )
