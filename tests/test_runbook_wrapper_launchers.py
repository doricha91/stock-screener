from pathlib import Path


WRAPPER_PATH = Path("ops/runbook_wrappers/00_prepare_next_runbook_day.cmd")
DOC_PATH = Path("docs/operations/runbook_wrapper_usage.md")


def _wrapper_text() -> str:
    return WRAPPER_PATH.read_text(encoding="ascii")


def test_prepare_wrapper_has_required_loader_and_environment_contract() -> None:
    text = _wrapper_text()
    lower = text.lower()

    assert lower.startswith("@echo off\nsetlocal\n")
    assert 'call "%~dp0_machine.local.cmd"' in text
    assert 'call "%~dp0_account.local.cmd"' in text
    assert 'call "%~dp0_env.cmd"' not in text
    for variable in (
        "REPO_ROOT",
        "WORKSPACE",
        "CONDA_BAT",
        "CONDA_ENV_NAME",
        "PAUSE_ON_EXIT",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "ACCOUNT_ID",
        "ACCOUNT_MODE",
    ):
        assert variable in text
    assert 'if /I not "%ACCOUNT_MODE%"=="PAPER"' in text
    assert 'call "%CONDA_BAT%" activate "%CONDA_ENV_NAME%"' in text
    assert 'if /I not "%CONDA_DEFAULT_ENV%"=="%CONDA_ENV_NAME%"' in text
    assert 'set "PYTHON_EXE=%CONDA_PREFIX%\\python.exe"' in text
    assert 'cd /d "%REPO_ROOT%"' in text


def test_prepare_wrapper_calls_only_the_existing_prep_cli_with_safe_options() -> None:
    text = _wrapper_text()
    lower = text.lower()

    assert '"%PYTHON_EXE%" scripts\\runbook_day_prep.py ^' in text
    assert '--workspace "%WORKSPACE%"' in text
    assert '--account-id "%ACCOUNT_ID%"' in text
    assert '--account-local "%~dp0_account.local.cmd"' in text
    assert '--runbook-day-local "%~dp0_runbook_day.local.cmd"' in text
    assert "--write-env-local" in text
    assert "--confirm-paper-test" in text
    assert "--force" not in lower
    assert "--replace" not in lower
    assert "--allow-warnings" not in lower
    assert "runbook_stage_runner.py" not in lower
    assert 'call "%~dp001_stage_a_plan_prep.cmd"' not in lower


def test_prepare_wrapper_preserves_exit_codes_and_operator_handoff() -> None:
    text = _wrapper_text()

    assert 'set "EXIT_CODE=%ERRORLEVEL%"' in text
    assert 'if "%EXIT_CODE%"=="0"' in text
    assert 'if "%EXIT_CODE%"=="2"' in text
    assert "Runbook day preparation was BLOCKED." in text
    assert "Runbook day preparation failed." in text
    assert 'type "%~dp0_runbook_day.local.cmd"' in text
    assert "If they are correct, run 01_stage_a_plan_prep.cmd." in text
    assert 'if /I "%PAUSE_ON_EXIT%"=="1" pause' in text
    assert "exit /b %EXIT_CODE%" in text


def test_wrapper_documentation_requires_prepare_review_then_stage_a() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "00_prepare_next_runbook_day.cmd" in text
    assert "Wrapper 00 is environment preparation, not a Stage" in text
    assert "review all four values before separately running `01_stage_a_plan_prep.cmd`" in text
    assert "Wrapper 00 never runs wrapper 01 automatically" in text
    assert "file_changed=false" in text
