import os
from pathlib import Path

import platformdirs
import pytest

from unical import config as config_mod
from unical.config import (
    Config,
    default_config_dir,
    default_credentials_path,
    load_saved_ical_url,
    resolve_config_path,
    save_ical_url,
    user_config_dir,
)
from unical.profile import CalendarSettings


def test_defaults_without_cwd_files() -> None:
    config = Config.from_env({})
    assert config == Config()
    assert config.source_calendar_name is None
    assert config.target_calendar_name is None
    expected_dir = config_mod.default_config_dir()
    assert config.credentials_path == expected_dir / "credentials.json"
    assert config.token_path == expected_dir / "token.json"
    assert config.legacy_token_path == expected_dir / "token.pickle"
    assert config.profile_path == expected_dir / "profile.json"
    assert config.source_ical_url is None


def test_defaults_with_cwd_files(tmp_path: Path) -> None:
    Path("credentials.json").touch()
    Path("token.json").touch()
    Path("token.pickle").touch()
    Path("profile.json").touch()

    config = Config.from_env({})
    assert config == Config()
    assert config.credentials_path == Path("credentials.json")
    assert config.token_path == Path("token.json")
    assert config.legacy_token_path == Path("token.pickle")
    assert config.profile_path == Path("profile.json")


def test_reads_every_setting_from_env() -> None:
    # Even if files exist in CWD, explicit environment variables must take precedence.
    Path("credentials.json").touch()
    Path("token.json").touch()
    Path("token.pickle").touch()
    Path("profile.json").touch()

    config = Config.from_env(
        {
            "SOURCE_CALENDAR_NAME": "Src",
            "TARGET_CALENDAR_NAME": "Tgt",
            "CREDENTIALS_PATH": "/a/c.json",
            "TOKEN_PATH": "/a/t.json",
            "LEGACY_TOKEN_PATH": "/a/t.pickle",
            "PROFILE_PATH": "/a/p.json",
            "SOURCE_ICAL_URL": "https://ical/1/x",
        }
    )
    assert config == Config(
        source_calendar_name="Src",
        target_calendar_name="Tgt",
        source_ical_url="https://ical/1/x",
        credentials_path=Path("/a/c.json"),
        token_path=Path("/a/t.json"),
        legacy_token_path=Path("/a/t.pickle"),
        profile_path=Path("/a/p.json"),
    )


def test_mixed_resolution_order() -> None:
    # 1. CREDENTIALS_PATH from env
    # 2. profile.json from CWD
    # 3. token.json and token.pickle from default config directory
    Path("profile.json").touch()
    expected_dir = config_mod.default_config_dir()

    config = Config.from_env({"CREDENTIALS_PATH": "/custom/credentials.json"})
    assert config.credentials_path == Path("/custom/credentials.json")
    assert config.profile_path == Path("profile.json")
    assert config.token_path == expected_dir / "token.json"
    assert config.legacy_token_path == expected_dir / "token.pickle"


def test_resolve_config_path_explicit_cwd_and_config_dir(tmp_path: Path) -> None:
    cwd = tmp_path / "work"
    cwd.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()

    # Env set
    assert resolve_config_path(
        "/env/file.json", "file.json", cwd=cwd, config_dir=cfg_dir
    ) == Path("/env/file.json")

    # CWD file exists
    (cwd / "file.json").touch()
    assert (
        resolve_config_path(None, "file.json", cwd=cwd, config_dir=cfg_dir)
        == cwd / "file.json"
    )

    # Fallback to config_dir when not in CWD
    assert (
        resolve_config_path(None, "other.json", cwd=cwd, config_dir=cfg_dir)
        == cfg_dir / "other.json"
    )


def test_default_config_dir_unpatched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    assert default_config_dir() == platformdirs.user_config_path(
        "unical", appauthor=False
    )


def test_blank_values_fall_back_to_defaults() -> None:
    # GitHub Actions passes unset secrets as empty strings.
    config = Config.from_env(
        {"SOURCE_CALENDAR_NAME": "", "TOKEN_PATH": "   ", "SOURCE_ICAL_URL": ""}
    )
    assert config == Config()


def test_values_are_stripped() -> None:
    assert (
        Config.from_env({"TARGET_CALENDAR_NAME": " Tgt "}).target_calendar_name == "Tgt"
    )


def test_calendar_names_override_the_profile() -> None:
    saved = CalendarSettings(source="Uni", target="Uni colored")
    assert Config().calendars(saved) == saved
    assert Config(target_calendar_name="Mine").calendars(saved) == CalendarSettings(
        source="Uni", target="Mine"
    )


def test_falls_back_to_user_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_config_dir = tmp_path / "dotconfig" / "unical"
    fake_config_dir.mkdir(parents=True)
    creds = fake_config_dir / "credentials.json"
    creds.write_text("{}")
    tok = fake_config_dir / "token.json"
    tok.write_text("{}")
    prof = fake_config_dir / "profile.json"
    prof.write_text("{}")

    monkeypatch.setattr("unical.config.default_config_dir", lambda: fake_config_dir)

    config = Config.from_env({})
    assert config.credentials_path == creds
    assert config.token_path == tok
    assert config.profile_path == prof
    assert user_config_dir() == fake_config_dir


def test_default_credentials_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_config_dir = tmp_path / "unical"
    monkeypatch.setattr("unical.config.default_config_dir", lambda: fake_config_dir)
    assert default_credentials_path() == fake_config_dir / "credentials.json"

    # If credentials.json exists in CWD, default_credentials_path prefers it
    cwd_creds = Path("credentials.json")
    cwd_creds.touch()
    assert default_credentials_path() == Path("credentials.json")


def test_saved_ical_url_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "dir" / "ical_url.txt"
    assert load_saved_ical_url(path) is None

    save_ical_url(" https://uni.example/42/secret ", path)
    assert load_saved_ical_url(path) == "https://uni.example/42/secret"
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600

    save_ical_url(None, path)
    assert not path.exists()
    save_ical_url(None, path)  # nothing to forget


def test_saved_ical_url_is_private_even_if_the_file_existed(tmp_path: Path) -> None:
    path = tmp_path / "ical_url.txt"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o644)
    save_ical_url("https://uni.example/new", path)
    assert load_saved_ical_url(path) == "https://uni.example/new"
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_saved_ical_url_has_the_lowest_priority(tmp_path: Path) -> None:
    save_ical_url("https://uni.example/saved", tmp_path / "ical_url.txt")

    config = Config.from_env({}, config_dir=tmp_path)
    assert config.source_ical_url is None
    assert config.saved_ical_url == "https://uni.example/saved"
    assert config.saved_ical_url_path == tmp_path / "ical_url.txt"
    assert config.ical_url == "https://uni.example/saved"

    config = Config.from_env(
        {"SOURCE_ICAL_URL": "https://uni.example/env"}, config_dir=tmp_path
    )
    assert config.ical_url == "https://uni.example/env"


def test_saved_ical_url_in_the_user_config_dir() -> None:
    path = config_mod.default_config_dir() / "ical_url.txt"  # isolated by conftest
    save_ical_url("https://uni.example/saved", path)
    assert Config.from_env({}).ical_url == "https://uni.example/saved"
    assert Config().ical_url is None
