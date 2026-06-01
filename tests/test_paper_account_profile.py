from __future__ import annotations

from pathlib import Path

import pytest

from core.paper_account_profile import (
    PaperAccountProfileError,
    default_paper_account_profile,
    is_valid_account_id,
    load_paper_account_profiles,
    resolve_paper_account_profile,
    validate_account_id,
)


def test_default_paper_account_profile():
    profile = default_paper_account_profile()
    assert profile.account_id == "paper_default"
    assert profile.display_name == "Paper Default"
    assert profile.currency == "USD"
    assert profile.initial_cash == 100000.0
    assert profile.account_type == "paper"
    assert profile.is_default is True


@pytest.mark.parametrize(
    "account_id",
    ["paper_default", "paper-growth", "acct_01"],
)
def test_validate_account_id_accepts_valid_values(account_id: str):
    assert validate_account_id(account_id) == account_id
    assert is_valid_account_id(account_id) is True


@pytest.mark.parametrize(
    "account_id",
    ["", "AAPL", "paper default", "ab", "../paper", "paper/default"],
)
def test_validate_account_id_rejects_invalid_values(account_id: str):
    with pytest.raises(ValueError):
        validate_account_id(account_id)
    assert is_valid_account_id(account_id) is False


@pytest.mark.parametrize("account_id", ["default", "paper_test", "outputs", "reviews"])
def test_validate_account_id_rejects_reserved_values(account_id: str):
    with pytest.raises(ValueError, match="reserved"):
        validate_account_id(account_id)


def test_load_profiles_missing_file_falls_back_to_default_when_allowed(tmp_path: Path):
    config = load_paper_account_profiles(tmp_path / "missing.json", allow_missing=True)
    assert config.default_account_id == "paper_default"
    assert len(config.accounts) == 1
    assert config.accounts[0].account_id == "paper_default"


def test_resolve_profile_by_account_id_from_config(tmp_path: Path):
    path = tmp_path / "paper_account_profiles.json"
    path.write_text(
        """
        {
          "schema_version": "paper_account_profiles.v1",
          "default_account_id": "paper_default",
          "accounts": [
            {
              "account_id": "paper_default",
              "display_name": "Paper Default",
              "currency": "USD",
              "initial_cash": 100000.0,
              "account_type": "paper",
              "is_default": true
            },
            {
              "account_id": "paper_growth",
              "display_name": "Paper Growth",
              "currency": "USD",
              "initial_cash": 250000.0,
              "account_type": "paper",
              "is_default": false
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    config = load_paper_account_profiles(path, allow_missing=False)
    profile = resolve_paper_account_profile("paper_growth", config=config)
    assert profile.account_id == "paper_growth"
    assert profile.display_name == "Paper Growth"


def test_resolve_profile_uses_default_account_when_account_id_is_none(tmp_path: Path):
    path = tmp_path / "paper_account_profiles.json"
    path.write_text(
        """
        {
          "schema_version": "paper_account_profiles.v1",
          "default_account_id": "paper_default",
          "accounts": [
            {
              "account_id": "paper_default",
              "display_name": "Paper Default",
              "currency": "USD",
              "initial_cash": 100000.0,
              "account_type": "paper",
              "is_default": true
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    config = load_paper_account_profiles(path, allow_missing=False)
    profile = resolve_paper_account_profile(None, config=config)
    assert profile.account_id == "paper_default"


def test_default_account_id_must_exist_in_accounts(tmp_path: Path):
    path = tmp_path / "paper_account_profiles.json"
    path.write_text(
        """
        {
          "schema_version": "paper_account_profiles.v1",
          "default_account_id": "paper_default",
          "accounts": [
            {
              "account_id": "paper_growth",
              "display_name": "Paper Growth",
              "currency": "USD",
              "initial_cash": 250000.0,
              "account_type": "paper",
              "is_default": true
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(PaperAccountProfileError, match="default_account_id"):
        load_paper_account_profiles(path, allow_missing=False)


def test_duplicate_account_id_fails(tmp_path: Path):
    path = tmp_path / "paper_account_profiles.json"
    path.write_text(
        """
        {
          "schema_version": "paper_account_profiles.v1",
          "default_account_id": "paper_default",
          "accounts": [
            {
              "account_id": "paper_default",
              "display_name": "Paper Default A",
              "currency": "USD",
              "initial_cash": 100000.0,
              "account_type": "paper",
              "is_default": true
            },
            {
              "account_id": "paper_default",
              "display_name": "Paper Default B",
              "currency": "USD",
              "initial_cash": 150000.0,
              "account_type": "paper",
              "is_default": false
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(PaperAccountProfileError, match="Duplicate account_id"):
        load_paper_account_profiles(path, allow_missing=False)


def test_multiple_default_accounts_fail(tmp_path: Path):
    path = tmp_path / "paper_account_profiles.json"
    path.write_text(
        """
        {
          "schema_version": "paper_account_profiles.v1",
          "default_account_id": "paper_default",
          "accounts": [
            {
              "account_id": "paper_default",
              "display_name": "Paper Default",
              "currency": "USD",
              "initial_cash": 100000.0,
              "account_type": "paper",
              "is_default": true
            },
            {
              "account_id": "paper_growth",
              "display_name": "Paper Growth",
              "currency": "USD",
              "initial_cash": 200000.0,
              "account_type": "paper",
              "is_default": true
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(PaperAccountProfileError, match="Exactly one account"):
        load_paper_account_profiles(path, allow_missing=False)
