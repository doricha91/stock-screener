from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


ACCOUNT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
RESERVED_ACCOUNT_IDS = {
    "default",
    "paper_test",
    "front_test",
    "reports",
    "reviews",
    "archive",
    "config",
    "outputs",
}
ACCOUNT_PROFILE_SCHEMA_VERSION = "paper_account_profiles.v1"


class PaperAccountProfileError(RuntimeError):
    pass


def is_valid_account_id(account_id: str) -> bool:
    try:
        validate_account_id(account_id)
    except ValueError:
        return False
    return True


def validate_account_id(account_id: str) -> str:
    value = str(account_id or "").strip()
    if not value:
        raise ValueError("account_id is required.")
    if value in RESERVED_ACCOUNT_IDS:
        raise ValueError(f"account_id '{value}' is reserved.")
    if not ACCOUNT_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"Invalid account_id '{value}'. Use lowercase letters, digits, '_' or '-'."
        )
    return value


@dataclass(frozen=True)
class PaperAccountProfile:
    account_id: str
    display_name: str
    currency: str
    initial_cash: float
    account_type: str
    is_default: bool
    strategy_profile: str | None = None
    universe_profile: str | None = None
    benchmark_profile: str | None = None
    notion_profile: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_id", validate_account_id(self.account_id))

        display_name = str(self.display_name or "").strip()
        if not display_name:
            raise PaperAccountProfileError("display_name is required.")
        object.__setattr__(self, "display_name", display_name)

        currency = str(self.currency or "").strip().upper()
        if not currency:
            raise PaperAccountProfileError("currency is required.")
        object.__setattr__(self, "currency", currency)

        try:
            initial_cash = float(self.initial_cash)
        except Exception as exc:
            raise PaperAccountProfileError("initial_cash must be numeric.") from exc
        if initial_cash <= 0:
            raise PaperAccountProfileError("initial_cash must be > 0.")
        object.__setattr__(self, "initial_cash", initial_cash)

        account_type = str(self.account_type or "").strip().lower()
        if not account_type:
            raise PaperAccountProfileError("account_type is required.")
        object.__setattr__(self, "account_type", account_type)

        object.__setattr__(self, "is_default", bool(self.is_default))
        object.__setattr__(self, "strategy_profile", _normalize_optional(self.strategy_profile))
        object.__setattr__(self, "universe_profile", _normalize_optional(self.universe_profile))
        object.__setattr__(self, "benchmark_profile", _normalize_optional(self.benchmark_profile))
        object.__setattr__(self, "notion_profile", _normalize_optional(self.notion_profile))


@dataclass(frozen=True)
class PaperAccountProfileConfig:
    schema_version: str
    default_account_id: str
    accounts: tuple[PaperAccountProfile, ...]
    path: Path | None = None

    def __post_init__(self) -> None:
        schema_version = str(self.schema_version or "").strip() or ACCOUNT_PROFILE_SCHEMA_VERSION
        object.__setattr__(self, "schema_version", schema_version)

        default_account_id = validate_account_id(self.default_account_id)
        object.__setattr__(self, "default_account_id", default_account_id)

        accounts = tuple(self.accounts)
        if not accounts:
            raise PaperAccountProfileError("accounts must contain at least one profile.")
        object.__setattr__(self, "accounts", accounts)

        account_ids = [profile.account_id for profile in accounts]
        duplicate_ids = sorted({account_id for account_id in account_ids if account_ids.count(account_id) > 1})
        if duplicate_ids:
            raise PaperAccountProfileError(
                f"Duplicate account_id values are not allowed: {', '.join(duplicate_ids)}."
            )

        if default_account_id not in {profile.account_id for profile in accounts}:
            raise PaperAccountProfileError(
                f"default_account_id '{default_account_id}' was not found in accounts."
            )

        default_profiles = [profile for profile in accounts if profile.is_default]
        if len(default_profiles) != 1:
            raise PaperAccountProfileError(
                "Exactly one account must set is_default=true."
            )
        if default_profiles[0].account_id != default_account_id:
            raise PaperAccountProfileError(
                "default_account_id must match the account marked with is_default=true."
            )

    @property
    def accounts_by_id(self) -> dict[str, PaperAccountProfile]:
        return {profile.account_id: profile for profile in self.accounts}


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _default_settings_path() -> Path:
    return Path.cwd() / "config" / "paper_account_profiles.json"


def default_paper_account_profile() -> PaperAccountProfile:
    return PaperAccountProfile(
        account_id="paper_default",
        display_name="Paper Default",
        currency="USD",
        initial_cash=100000.0,
        account_type="paper",
        is_default=True,
        strategy_profile=None,
        universe_profile=None,
        benchmark_profile=None,
        notion_profile=None,
    )


def _default_config(path: Path | None = None) -> PaperAccountProfileConfig:
    profile = default_paper_account_profile()
    return PaperAccountProfileConfig(
        schema_version=ACCOUNT_PROFILE_SCHEMA_VERSION,
        default_account_id=profile.account_id,
        accounts=(profile,),
        path=path,
    )


def load_paper_account_profiles(
    path: Path | None = None,
    *,
    allow_missing: bool = True,
) -> PaperAccountProfileConfig:
    config_path = Path(path) if path is not None else _default_settings_path()
    if not config_path.exists():
        if allow_missing:
            return _default_config(path=config_path)
        raise PaperAccountProfileError(
            f"Missing paper account profiles file: {config_path}. "
            "Create config/paper_account_profiles.json from config/paper_account_profiles.example.json."
        )

    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise PaperAccountProfileError("Invalid paper account profiles config: top-level object required.")

    accounts_payload = payload.get("accounts")
    if not isinstance(accounts_payload, list):
        raise PaperAccountProfileError("Invalid paper account profiles config: accounts must be a list.")

    default_account_id = str(payload.get("default_account_id") or "").strip()
    if not default_account_id:
        raise PaperAccountProfileError("default_account_id is required.")

    profiles = tuple(_build_profile(item) for item in accounts_payload)
    return PaperAccountProfileConfig(
        schema_version=str(payload.get("schema_version") or ACCOUNT_PROFILE_SCHEMA_VERSION).strip(),
        default_account_id=default_account_id,
        accounts=profiles,
        path=config_path,
    )


def resolve_paper_account_profile(
    account_id: str | None = None,
    *,
    config: PaperAccountProfileConfig | None = None,
) -> PaperAccountProfile:
    profile_config = config if config is not None else load_paper_account_profiles(allow_missing=True)
    resolved_account_id = account_id if account_id is not None else profile_config.default_account_id
    normalized_account_id = validate_account_id(resolved_account_id)
    try:
        return profile_config.accounts_by_id[normalized_account_id]
    except KeyError as exc:
        raise PaperAccountProfileError(
            f"Unknown paper account_id '{normalized_account_id}'."
        ) from exc


def _build_profile(payload: object) -> PaperAccountProfile:
    if not isinstance(payload, dict):
        raise PaperAccountProfileError("Each account entry must be an object.")
    return PaperAccountProfile(
        account_id=payload.get("account_id", ""),
        display_name=payload.get("display_name", ""),
        currency=payload.get("currency", ""),
        initial_cash=payload.get("initial_cash", 0.0),
        account_type=payload.get("account_type", ""),
        is_default=payload.get("is_default", False),
        strategy_profile=payload.get("strategy_profile"),
        universe_profile=payload.get("universe_profile"),
        benchmark_profile=payload.get("benchmark_profile"),
        notion_profile=payload.get("notion_profile"),
    )
