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
        updated_at="2026-05-20T10:01:00",
    )
    assert compute_paper_config_hash(baseline) == compute_paper_config_hash(regenerated)


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
