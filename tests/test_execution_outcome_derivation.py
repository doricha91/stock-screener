from __future__ import annotations

import copy

import pytest

from core.execution_reconciliation import (
    BLOCKED,
    EXECUTED,
    NO_ACTION,
    NOT_EXECUTED,
    PARTIAL,
    PASS,
    WAIT,
    build_manual_execution_key,
    derive_execution_outcomes,
)


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"
CONTRACT_VERSION = "execution_outcome.v2"


def _context(**overrides: object) -> dict[str, object]:
    context: dict[str, object] = {
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "contract_version": CONTRACT_VERSION,
    }
    context.update(overrides)
    return context


def _key(symbol: str, side: str, sequence: int = 1) -> str:
    return build_manual_execution_key(ACCOUNT_ID, TRADE_DATE, symbol, side, sequence)


def _plan(symbol: str, side: str, quantity: object, sequence: int = 1) -> dict[str, object]:
    return {
        "plan_external_key": _key(symbol, side, sequence),
        "account_id": ACCOUNT_ID,
        "trade_date": TRADE_DATE,
        "symbol": symbol,
        "side": side,
        "planned_quantity": quantity,
    }


def _execution(
    symbol: str,
    side: str,
    quantity: object,
    sequence: int = 1,
) -> dict[str, object]:
    return {
        "manual_execution_external_key": _key(symbol, side, sequence),
        "account_id": ACCOUNT_ID,
        "trade_date": TRADE_DATE,
        "symbol": symbol,
        "side": side,
        "actual_quantity": quantity,
    }


def _derive(
    plans: list[dict[str, object]],
    executions: list[dict[str, object]],
    *,
    finalized: bool = True,
    plan_context: dict[str, object] | None = None,
    execution_context: dict[str, object] | None = None,
) -> dict[str, object]:
    return derive_execution_outcomes(
        plans,
        executions,
        input_finalized=finalized,
        plan_context=plan_context or _context(),
        execution_context=execution_context or _context(),
    )


def test_full_execution_is_executed() -> None:
    result = _derive([_plan("CCI", "SELL", 84)], [_execution("CCI", "SELL", 84)])

    assert result["runner_result"] == PASS
    assert result["rows"][0]["outcome"] == EXECUTED
    assert result["executed_count"] == 1
    assert result["count_invariant_satisfied"] is True


def test_partial_execution_is_partial() -> None:
    result = _derive([_plan("CCI", "SELL", 84)], [_execution("CCI", "SELL", 40)])

    assert result["runner_result"] == PASS
    assert result["rows"][0]["outcome"] == PARTIAL
    assert result["partial_count"] == 1


def test_blank_actual_before_finalize_waits() -> None:
    result = _derive(
        [_plan("CCI", "SELL", 84)],
        [_execution("CCI", "SELL", None)],
        finalized=False,
    )

    assert result["runner_result"] == WAIT
    assert result["rows"][0]["outcome"] is None
    assert result["waiting_count"] == 1
    assert result["count_invariant_satisfied"] is False


def test_blank_actual_after_finalize_is_not_executed() -> None:
    result = _derive([_plan("CCI", "SELL", 84)], [_execution("CCI", "SELL", None)])

    assert result["runner_result"] == PASS
    assert result["rows"][0]["outcome"] == NOT_EXECUTED
    assert result["not_executed_count"] == 1
    assert result["count_invariant_satisfied"] is True


def test_actual_quantity_over_plan_blocks() -> None:
    result = _derive([_plan("CCI", "SELL", 84)], [_execution("CCI", "SELL", 85)])

    assert result["runner_result"] == BLOCKED
    assert result["rows"][0]["outcome"] is None
    assert result["errors"][0]["candidate_key"] == _key("CCI", "SELL")
    assert result["errors"][0]["reason_code"] == "actual_quantity_exceeds_planned"


@pytest.mark.parametrize("source", ["plan", "execution"])
def test_duplicate_key_blocks(source: str) -> None:
    plans = [_plan("CCI", "SELL", 84)]
    executions = [_execution("CCI", "SELL", 84)]
    if source == "plan":
        plans.append(copy.deepcopy(plans[0]))
    else:
        executions.append(copy.deepcopy(executions[0]))

    result = _derive(plans, executions)

    assert result["runner_result"] == BLOCKED
    assert result["duplicate_count"] == 1
    assert any(error["reason_code"] == "duplicate_candidate_key" for error in result["errors"])


@pytest.mark.parametrize(
    ("plans", "executions", "count_field", "reason_code"),
    [
        (
            [_plan("CCI", "SELL", 84), _plan("TDY", "BUY", 9)],
            [_execution("CCI", "SELL", 84)],
            "missing_count",
            "missing_execution_record",
        ),
        (
            [_plan("CCI", "SELL", 84)],
            [_execution("CCI", "SELL", 84), _execution("TDY", "BUY", 9)],
            "extra_count",
            "extra_execution_record",
        ),
    ],
)
def test_missing_or_extra_candidate_blocks(
    plans: list[dict[str, object]],
    executions: list[dict[str, object]],
    count_field: str,
    reason_code: str,
) -> None:
    result = _derive(plans, executions)

    assert result["runner_result"] == BLOCKED
    assert result[count_field] == 1
    assert any(error["reason_code"] == reason_code for error in result["errors"])


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("context", "account_id", "paper_other"),
        ("context", "data_date", "2026-06-29"),
        ("context", "trade_date", "2026-07-02"),
        ("context", "contract_version", "execution_outcome.v1"),
        ("row", "account_id", "paper_other"),
        ("row", "trade_date", "2026-07-02"),
    ],
)
def test_context_or_row_identity_mismatch_blocks(target: str, field: str, value: str) -> None:
    plan = _plan("CCI", "SELL", 84)
    execution = _execution("CCI", "SELL", 84)
    execution_context = _context()
    if target == "context":
        execution_context[field] = value
    else:
        execution[field] = value

    result = _derive(
        [plan],
        [execution],
        execution_context=execution_context,
    )

    assert result["runner_result"] == BLOCKED
    assert result["invalid_count"] >= 1


def test_non_dict_plan_context_blocks_without_exception() -> None:
    result = derive_execution_outcomes(
        [_plan("CCI", "SELL", 84)],
        [_execution("CCI", "SELL", 84)],
        input_finalized=True,
        plan_context="invalid",  # type: ignore[arg-type]
        execution_context=_context(),
    )

    assert result["runner_result"] == BLOCKED
    assert any(error["reason_code"] == "context_invalid" for error in result["errors"])


def test_non_dict_execution_context_blocks_without_exception() -> None:
    result = derive_execution_outcomes(
        [_plan("CCI", "SELL", 84)],
        [_execution("CCI", "SELL", 84)],
        input_finalized=True,
        plan_context=_context(),
        execution_context="invalid",  # type: ignore[arg-type]
    )

    assert result["runner_result"] == BLOCKED
    assert any(error["reason_code"] == "context_invalid" for error in result["errors"])


def test_zero_candidates_preserves_no_action_mode() -> None:
    result = _derive([], [])

    assert result["runner_result"] == PASS
    assert result["action_mode"] == NO_ACTION
    assert result["planned_count"] == 0
    assert result["count_invariant_satisfied"] is True


def test_input_order_does_not_change_result() -> None:
    plans = [_plan("CCI", "SELL", 84), _plan("TDY", "BUY", 9)]
    executions = [_execution("CCI", "SELL", 40), _execution("TDY", "BUY", 9)]

    forward = _derive(plans, executions)
    reversed_result = _derive(list(reversed(plans)), list(reversed(executions)))

    assert reversed_result == forward
    assert [row["candidate_key"] for row in forward["rows"]] == sorted(
        row["candidate_key"] for row in forward["rows"]
    )


def test_finalized_mixed_outcomes_satisfy_count_invariant() -> None:
    plans = [
        _plan("CCI", "SELL", 84),
        _plan("TDY", "BUY", 9),
        _plan("PLD", "BUY", 20),
    ]
    executions = [
        _execution("CCI", "SELL", 84),
        _execution("TDY", "BUY", 4),
        _execution("PLD", "BUY", None),
    ]

    result = _derive(plans, executions)

    assert result["runner_result"] == PASS
    assert result["planned_count"] == 3
    assert result["executed_count"] == 1
    assert result["partial_count"] == 1
    assert result["not_executed_count"] == 1
    assert result["count_invariant_satisfied"] is True


@pytest.mark.parametrize("quantity", [0, -1, "not-a-number", float("nan"), float("inf")])
def test_explicit_zero_or_invalid_actual_quantity_blocks(quantity: object) -> None:
    result = _derive([_plan("CCI", "SELL", 84)], [_execution("CCI", "SELL", quantity)])

    assert result["runner_result"] == BLOCKED
    assert result["rows"][0]["outcome"] is None
    assert result["errors"][0]["reason_code"] == "actual_quantity_invalid"
