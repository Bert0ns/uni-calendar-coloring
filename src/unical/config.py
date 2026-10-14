from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from unical.profile import CalendarSettings

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
LEGACY_TOKEN_FILE = "token.pickle"
PROFILE_FILE = "profile.json"
ICAL_URL_FILE = "ical_url.txt"
"""The iCal feed URL chosen in the setup guide. Not in the profile: the URL
holds a secret token, and the profile is meant to be shared."""


def default_config_dir() -> Path:
    """Standard platform-specific user configuration directory for unical."""
    return platformdirs.user_config_path("unical", appauthor=False)


def resolve_config_path(
    env_value: str | None,
    filename: str,
    *,
    cwd: Path | None = None,
    config_dir: Path | None = None,
) -> Path:
    """Resolve a configuration file path according to the resolution order:

    1. Explicit environment variable (if non-empty).
    2. Current working directory if the file exists.
    3. Platform standard user config directory.
    """
    if env_value:
        return Path(env_value)
    target_cwd = cwd if cwd is not None else Path.cwd()
    candidate = target_cwd / filename
    if candidate.is_file():
        return Path(filename) if cwd is None else candidate
    base_dir = config_dir if config_dir is not None else default_config_dir()
    return base_dir / filename


def user_config_dir() -> Path:
    """The standard platform user configuration directory for unical."""
    return default_config_dir()


def default_credentials_path() -> Path:
    """Default path where credentials are saved or resolved."""
    return resolve_config_path(None, CREDENTIALS_FILE)


def default_ical_url_path(config_dir: Path | None = None) -> Path:
    """Where the iCal feed URL chosen in the setup guide is saved."""
    return (config_dir or default_config_dir()) / ICAL_URL_FILE


def load_saved_ical_url(path: Path) -> str | None:
    """The saved iCal feed URL, or ``None`` if there is none (or it can't be read)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return text.strip() or None


def save_ical_url(url: str | None, path: Path) -> None:
    """Saves the iCal feed URL, readable by the user only like the token;
    ``None`` forgets it."""
    if url is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    # The file may have existed with other permissions: tighten them before
    # writing the secret. No fchmod on older Windows Pythons.
    with contextlib.suppress(OSError, AttributeError):
        os.fchmod(fd, 0o600)
    with open(fd, "w", encoding="utf-8") as f:
        f.write(url.strip() + "\n")


@dataclass(frozen=True)
class Config:
    """Runtime configuration.

    Configuration paths (credentials, token, profile) are resolved in order:
    1. Explicit environment variables (CREDENTIALS_PATH, TOKEN_PATH, etc.).
    2. Current working directory if the file exists.
    3. Platform standard user config directory (e.g. ~/.config/unical on Linux).

    Everything about the calendar itself lives in the profile; the calendar
    names here only override it (e.g. from GitHub Actions secrets).

    The iCal feed URL comes, in order, from ``--ical``, ``SOURCE_ICAL_URL``
    (environment or ``.env``), then the file saved by the setup guide.
    """

    source_calendar_name: str | None = None
    target_calendar_name: str | None = None
    source_ical_url: str | None = None
    """When set, events are read from this iCal feed instead of a Google calendar."""
    saved_ical_url: str | None = None
    """The iCal feed URL saved by the setup guide, used if none is given."""
    saved_ical_url_path: Path = field(default_factory=default_ical_url_path)
    credentials_path: Path = field(
        default_factory=lambda: resolve_config_path(None, CREDENTIALS_FILE)
    )
    token_path: Path = field(
        default_factory=lambda: resolve_config_path(None, TOKEN_FILE)
    )
    legacy_token_path: Path = field(
        default_factory=lambda: resolve_config_path(None, LEGACY_TOKEN_FILE)
    )
    profile_path: Path = field(
        default_factory=lambda: resolve_config_path(None, PROFILE_FILE)
    )

    @property
    def ical_url(self) -> str | None:
        """The iCal feed to read the events from, if any."""
        return self.source_ical_url or self.saved_ical_url

    def calendars(self, saved: CalendarSettings) -> CalendarSettings:
        """The calendars to sync: the profile's, unless overridden."""
        return CalendarSettings(
            source=self.source_calendar_name or saved.source,
            target=self.target_calendar_name or saved.target,
            time_zone=saved.time_zone,
        )

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str],
        *,
        cwd: Path | None = None,
        config_dir: Path | None = None,
    ) -> Config:
        def get(key: str) -> str | None:
            value = env.get(key, "").strip()
            return value or None

        ical_url_path = default_ical_url_path(config_dir)
        return cls(
            source_calendar_name=get("SOURCE_CALENDAR_NAME"),
            target_calendar_name=get("TARGET_CALENDAR_NAME"),
            source_ical_url=get("SOURCE_ICAL_URL"),
            saved_ical_url=load_saved_ical_url(ical_url_path),
            saved_ical_url_path=ical_url_path,
            credentials_path=resolve_config_path(
                get("CREDENTIALS_PATH"),
                CREDENTIALS_FILE,
                cwd=cwd,
                config_dir=config_dir,
            ),
            token_path=resolve_config_path(
                get("TOKEN_PATH"),
                TOKEN_FILE,
                cwd=cwd,
                config_dir=config_dir,
            ),
            legacy_token_path=resolve_config_path(
                get("LEGACY_TOKEN_PATH"),
                LEGACY_TOKEN_FILE,
                cwd=cwd,
                config_dir=config_dir,
            ),
            profile_path=resolve_config_path(
                get("PROFILE_PATH"),
                PROFILE_FILE,
                cwd=cwd,
                config_dir=config_dir,
            ),
        )
