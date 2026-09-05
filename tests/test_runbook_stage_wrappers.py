from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPERS = ROOT / "ops" / "runbook_wrappers"


def test_gate1_execution_wrapper_uses_integrated_finalize_then_gate_entrypoint() -> None:
    text = (WRAPPERS / "02_gate1_execution_input.cmd").read_text(encoding="utf-8")

    assert "runbook_gate_checker.py gate1-execution-input" in text
    assert "runbook_state.py finalize-execution-input" not in text
    assert "03_stage_b_execution_sync.cmd" not in text
    assert '--workspace "%WORKSPACE%"' in text
    assert '--account-id "%ACCOUNT_ID%"' in text
    assert '--data-date "%DATA_DATE%"' in text
    assert '--trade-date "%TRADE_DATE%"' in text
    assert 'set "EXIT_CODE=%ERRORLEVEL%"' in text
    assert "exit /b %EXIT_CODE%" in text


def test_official_stage_e_wrapper_calls_stage_f_only_after_zero_exit() -> None:
    text = (WRAPPERS / "09_stage_e_eod_close.cmd").read_text(encoding="utf-8")

    stage_e_index = text.index("runbook_stage_runner.py stage-e")
    exit_capture_index = text.index('set "STAGE_E_EXIT_CODE=%ERRORLEVEL%"')
    failure_guard_index = text.index('if not "%STAGE_E_EXIT_CODE%"=="0"')
    stage_f_index = text.index("10_stage_f_benchmark_notion_sync.cmd")
    assert stage_e_index < exit_capture_index < failure_guard_index < stage_f_index
    assert "exit /b %STAGE_E_EXIT_CODE%" in text


def test_stage_f_wrapper_passes_frozen_context_and_runner_exit_code() -> None:
    text = (WRAPPERS / "10_stage_f_benchmark_notion_sync.cmd").read_text(encoding="utf-8")

    assert "runbook_stage_runner.py stage-f" in text
    assert '--account-id "%ACCOUNT_ID%"' in text
    assert '--data-date "%DATA_DATE%"' in text
    assert '--trade-date "%TRADE_DATE%"' in text
    assert 'set "EXIT_CODE=%ERRORLEVEL%"' in text
    assert "exit /b %EXIT_CODE%" in text
