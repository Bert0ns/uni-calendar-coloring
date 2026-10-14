"""Read-only diagnostics of the setup: never opens the browser to log in."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from unical.auth import (
    PERSONAL_ACCOUNT_HINT,
    SCOPES,
    WEB_CLIENT_HINT,
    InvalidCredentialsError,
    oauth_client_type,
    validate_client_secrets,
)
from unical.config import Config
from unical.profile import CalendarSettings
from unical.sync.gateway import CalendarGateway

CALENDAR_API_URL = (
    "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"
)
LOGIN_AGAIN = "Run 'unical auth login' to log in with Google."


class Status(Enum):
    """Outcome of one check; any FAIL makes 'unical doctor' exit with 1."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class Check:
    """One diagnostic line: what was checked, the outcome and how to fix it."""

    name: str
    status: Status
    detail: str
    hint: str | None = None


def check_config_dir(path: Path) -> Check:
    if not path.exists():
        return Check(
            "Config directory",
            Status.WARN,
            f"{path} does not exist yet",
            "It is created by 'unical auth import'.",
        )
    if not os.access(path, os.W_OK):
        return Check(
            "Config directory",
            Status.FAIL,
            f"{path} is not writable",
            "Fix its permissions so the login can be saved.",
        )
    return Check("Config directory", Status.PASS, str(path))


def check_credentials(path: Path) -> Check:
    name = "Credentials"
    if not path.exists():
        return Check(
            name,
            Status.FAIL,
            f"Missing ({path})",
            "Run 'unical auth import /path/to/credentials.json'. "
            + PERSONAL_ACCOUNT_HINT,
        )
    try:
        data = validate_client_secrets(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, InvalidCredentialsError) as exc:
        return Check(name, Status.FAIL, f"Invalid ({path}): {exc}")
    client_type = oauth_client_type(data)
    client_id = data[client_type]["client_id"]
    if client_type == "web":
        return Check(
            name,
            Status.WARN,
            f"Web application client {client_id} ({path})",
            WEB_CLIENT_HINT,
        )
    return Check(name, Status.PASS, f"Desktop app client {client_id} ({path})")


def check_profile(path: Path) -> Check:
    if not path.exists():
        return Check(
            "Profile", Status.WARN, f"{path} not found", "The setup guide creates it."
        )
    return Check("Profile", Status.PASS, str(path))


def load_token(path: Path) -> tuple[Check, Credentials | None]:
    """Checks the cached token without network access. Returns the check and,
    if usable, the credentials."""
    name = "Login token"
    if not path.exists():
        return (
            Check(name, Status.FAIL, f"Not logged in ({path} not found)", LOGIN_AGAIN),
            None,
        )
    try:
        creds = Credentials.from_authorized_user_file(str(path))  # type: ignore[no-untyped-call]
    except (OSError, ValueError, KeyError) as exc:
        return (
            Check(name, Status.FAIL, f"Unreadable ({path}): {exc}", LOGIN_AGAIN),
            None,
        )
    # A token saved without scopes is assumed to have the ones it was asked for.
    if creds.scopes and not creds.has_scopes(SCOPES):
        return (
            Check(
                name,
                Status.FAIL,
                f"Missing the Calendar scope (granted: {', '.join(creds.scopes)})",
                LOGIN_AGAIN,
            ),
            None,
        )
    if creds.valid:
        until = f" until {creds.expiry:%Y-%m-%d %H:%M} UTC" if creds.expiry else ""
        return Check(name, Status.PASS, f"Logged in (token valid{until})"), creds
    if not creds.refresh_token:
        return (
            Check(
                name, Status.FAIL, "Token expired and cannot be refreshed", LOGIN_AGAIN
            ),
            None,
        )
    return Check(name, Status.PASS, "Token expired (will refresh on next run)"), creds


def check_refresh(
    creds: Credentials, request_factory: Callable[[], Any] = Request
) -> Check:
    """Refreshes the access token in memory to prove the saved login still works."""
    name = "Token refresh"
    if not creds.refresh_token:
        return Check(
            name,
            Status.WARN,
            "No refresh token saved",
            "You will have to log in again when the access token expires. "
            + LOGIN_AGAIN,
        )
    try:
        creds.refresh(request_factory())  # type: ignore[no-untyped-call]
    except RefreshError as exc:
        return Check(
            name,
            Status.FAIL,
            f"The saved login expired or was revoked: {exc}",
            "Logins of apps in Testing mode expire after 7 days. " + LOGIN_AGAIN,
        )
    except GoogleAuthError as exc:
        return Check(
            name,
            Status.FAIL,
            f"Could not reach Google: {exc}",
            "Check your internet connection.",
        )
    return Check(name, Status.PASS, "The saved login can be refreshed")


def _api_error_hint(exc: Exception) -> str | None:
    text = str(exc).lower()
    if "accessnotconfigured" in text or "has not been used" in text:
        return f"Enable the Google Calendar API: {CALENDAR_API_URL}"
    if "insufficient" in text or "scope" in text:
        return LOGIN_AGAIN
    return None


def check_calendars(
    gateway: CalendarGateway, calendars: CalendarSettings, ical_source: bool
) -> list[Check]:
    """Checks API access, then the source and target calendars."""
    try:
        listed = gateway.list_calendars()
    except Exception as exc:
        return [
            Check("Calendar API", Status.FAIL, str(exc).strip(), _api_error_hint(exc))
        ]
    checks = [Check("Calendar API", Status.PASS, f"{len(listed)} calendars visible")]
    by_name = {calendar.name: calendar for calendar in listed}

    if ical_source:
        checks.append(Check("Source calendar", Status.PASS, "iCal feed"))
    elif calendars.source in by_name:
        checks.append(Check("Source calendar", Status.PASS, f"'{calendars.source}'"))
    else:
        checks.append(
            Check(
                "Source calendar",
                Status.FAIL,
                f"'{calendars.source}' not found",
                "Use the exact name shown in Google Calendar, or sync from an "
                "iCal URL with --ical.",
            )
        )

    target = by_name.get(calendars.target)
    if target is None:
        checks.append(
            Check(
                "Target calendar",
                Status.WARN,
                f"'{calendars.target}' not found",
                "It is created on the first sync.",
            )
        )
    elif not target.writable:
        checks.append(
            Check(
                "Target calendar",
                Status.FAIL,
                f"'{calendars.target}' is read-only",
                "Choose a calendar you own or can edit as the target.",
            )
        )
    else:
        checks.append(
            Check("Target calendar", Status.PASS, f"'{calendars.target}' is writable")
        )
    return checks


def run_checks(
    config: Config,
    calendars: CalendarSettings,
    gateway_factory: Callable[[Any], CalendarGateway],
) -> list[Check]:
    checks = [
        check_config_dir(config.token_path.parent),
        check_credentials(config.credentials_path),
        check_profile(config.profile_path),
    ]
    token_check, creds = load_token(config.token_path)
    checks.append(token_check)
    if creds is not None:
        checks.append(check_refresh(creds))
    if creds is None or not creds.valid:
        checks.append(Check("Calendar API", Status.SKIP, "Needs a working login"))
        return checks
    checks.extend(
        check_calendars(gateway_factory(creds), calendars, bool(config.ical_url))
    )
    return checks
