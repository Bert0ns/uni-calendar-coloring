import json
import re
import runpy
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conftest import FakeCalendarGateway, save_profile, saved
from google.auth.exceptions import RefreshError, TransportError

from unical import config as config_mod
from unical import doctor
from unical.auth import (
    CredentialsFileNotFoundError,
    InvalidCredentialsError,
    LoginFailedError,
    LoginRequiredError,
)
from unical.cli import main as cli
from unical.config import Config
from unical.ical_source import IcalFeedSource, mask_url
from unical.profile import CalendarSettings
from unical.reporting import NullReporter
from unical.suggestions import suggest_color
from unical.sync.source import GoogleCalendarSource
from unical.targets import SyncTarget
from unical.workflow import SyncOptions

SOURCE = [
    {
        "id": "lec00001",
        "summary": "Lezione: Didattica - CS",
        "start": {"date": "2026-09-20"},
        "end": {"date": "2026-09-21"},
    }
]


# -- argument parsing --------------------------------------------------------


def default_opts(*args, **kwargs) -> SyncOptions:
    return SyncOptions.with_semester_default(*args, **kwargs)


def test_parse_args_defaults() -> None:
    assert cli.parse_args([]) == cli.CliArgs(options=default_opts())


def test_parse_args_all_options() -> None:
    args = cli.parse_args(
        [
            "deadlines",
            "-v",
            "-i",
            "--ical",
            "https://example.com/feed.ics",
            "--dry-run",
            "--prune-before",
            "2025-01-01",
        ]
    )
    assert args == cli.CliArgs(
        options=default_opts(
            target=SyncTarget.DEADLINES,
            interactive=True,
            dry_run=True,
            prune_before=date(2025, 1, 1),
        ),
        verbose=True,
        ical_url="https://example.com/feed.ics",
    )


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["exams"], default_opts(target=SyncTarget.EXAMS)),
        (["lectures", "-i"], default_opts(SyncTarget.LECTURES, interactive=True)),
        (["-n"], default_opts(dry_run=True)),
    ],
)
def test_parse_args_options(argv, expected) -> None:
    assert cli.parse_args(argv).options == expected


def test_parse_args_quiet_and_source_url_alias() -> None:
    args = cli.parse_args(["-q", "--source-ical-url", "https://x/y"])
    assert args.quiet
    assert args.ical_url == "https://x/y"


@pytest.mark.parametrize(
    "argv",
    [["unknown"], ["--prune-before", "yesterday"], ["-v", "-q"]],
)
def test_parse_args_rejects_invalid_input(argv, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.parse_args(argv)
    assert exc_info.value.code == 2


def test_bad_prune_date_message(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.parse_args(["--prune-before", "yesterday"])
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_mask_url_hides_token() -> None:
    masked = mask_url("https://ical.example.com/12345/secret-token-abc")
    assert masked == "https://ical.example.com/<redacted>"


@pytest.mark.parametrize("url", ["not a url", "", "http://[::1"])
def test_mask_url_handles_garbage(url: str) -> None:
    assert mask_url(url) == "<redacted>"


# -- run() -------------------------------------------------------------------


def test_run_returns_zero_on_success(config: Config) -> None:
    gateway = FakeCalendarGateway({"Src": SOURCE})
    assert cli.run(SyncOptions(), config, gateway, NullReporter()) == cli.EXIT_OK
    assert saved(config, "courses") == {"CS": "3"}


def test_run_reports_missing_source(config: Config) -> None:
    reporter = MagicMock()
    code = cli.run(SyncOptions(), config, FakeCalendarGateway(), reporter)
    assert code == cli.EXIT_FAILURE
    reporter.error.assert_called_once_with("Source calendar 'Src' not found.")


def test_run_reports_ical_failure_without_touching_calendar(config: Config) -> None:
    from unical.ical_source import ICalError

    def broken_fetch(url: str) -> str:
        raise ICalError("Could not download iCal feed.")

    gateway = FakeCalendarGateway({"Tgt": []})
    reporter = MagicMock()
    source = IcalFeedSource("https://x/y", fetch=broken_fetch)

    code = cli.run(SyncOptions(), config, gateway, reporter, source=source)

    assert code == cli.EXIT_FAILURE
    reporter.error.assert_called_once_with("Could not download iCal feed.")
    assert gateway.batches == []


def test_run_fails_when_a_mutation_fails(config: Config) -> None:
    gateway = FakeCalendarGateway({"Src": SOURCE})
    gateway.fail_event_ids = {"lec00001"}
    assert cli.run(SyncOptions(), config, gateway, NullReporter()) == cli.EXIT_FAILURE


def test_run_routes_preference_warnings_to_reporter(config: Config) -> None:
    config.profile_path.write_text("{oops")
    reporter = MagicMock()
    cli.run(SyncOptions(), config, FakeCalendarGateway({"Src": SOURCE}), reporter)
    reporter.warning.assert_called_once()
    assert "corrupted" in reporter.warning.call_args.args[0]


def test_run_describes_configuration_without_leaking_ical_token(config) -> None:
    config = replace(config, source_ical_url="https://ical.example/42/secret")
    reporter = MagicMock()
    cli.describe_run(
        SyncOptions(dry_run=True, prune_before=date(2025, 1, 1)),
        config,
        CalendarSettings(source="Src", target="Tgt"),
        reporter,
    )
    details = [c.args[0] for c in reporter.detail.call_args_list]
    assert details == [
        f"Profile: {config.profile_path}",
        "Source: iCal feed at https://ical.example/<redacted>",
        "Target: Google Calendar 'Tgt'",
        "Options: dry-run, prune-before=2025-01-01",
    ]


def test_build_source(config: Config) -> None:
    gateway = FakeCalendarGateway()
    calendars = CalendarSettings(source="Src", target="Tgt")
    google = cli.build_source(config, calendars, gateway, NullReporter())
    ical = cli.build_source(
        replace(config, source_ical_url="https://x/y"),
        calendars,
        gateway,
        NullReporter(),
    )
    assert isinstance(google, GoogleCalendarSource)
    assert google.name == "Src"
    assert isinstance(ical, IcalFeedSource)
    assert ical.url == "https://x/y"


# -- main() ------------------------------------------------------------------


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    for key in (
        "SOURCE_CALENDAR_NAME",
        "TARGET_CALENDAR_NAME",
        "CREDENTIALS_PATH",
        "SOURCE_ICAL_URL",
        "PROFILE_PATH",
        "CI",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    return tmp_path


@pytest.fixture
def fake_auth(monkeypatch) -> MagicMock:
    authenticator = MagicMock()
    monkeypatch.setattr(cli, "Authenticator", authenticator)
    return authenticator


def install_gateway(monkeypatch, gateway) -> None:
    monkeypatch.setattr(
        cli.GoogleCalendarClient,
        "from_credentials",
        classmethod(lambda cls, c: gateway),
    )


def test_main_wires_everything(isolated_env, fake_auth, monkeypatch) -> None:
    gateway = FakeCalendarGateway({"Calendar": SOURCE})
    install_gateway(monkeypatch, gateway)

    assert cli.main(["lectures"]) == cli.EXIT_OK

    kwargs = fake_auth.call_args.kwargs
    assert kwargs["token_path"] == config_mod.default_config_dir() / "token.json"
    assert (
        kwargs["legacy_token_path"] == config_mod.default_config_dir() / "token.pickle"
    )
    assert gateway.created == ["Calendar Colored"]
    assert saved(
        Config(profile_path=config_mod.default_config_dir() / "profile.json"), "courses"
    ) == {"CS": suggest_color("CS").color_id}


def test_main_wires_everything_preserves_cwd_files(
    isolated_env, fake_auth, monkeypatch
) -> None:
    (isolated_env / "token.json").touch()
    (isolated_env / "token.pickle").touch()
    (isolated_env / "profile.json").touch()
    gateway = FakeCalendarGateway({"Calendar": SOURCE})
    install_gateway(monkeypatch, gateway)

    assert cli.main(["lectures"]) == cli.EXIT_OK

    kwargs = fake_auth.call_args.kwargs
    assert kwargs["token_path"] == Path("token.json")
    assert kwargs["legacy_token_path"] == Path("token.pickle")
    assert gateway.created == ["Calendar Colored"]


def test_main_reads_the_calendars_from_the_profile(
    isolated_env, fake_auth, monkeypatch
) -> None:
    save_profile(
        Config(profile_path=isolated_env / "profile.json"),
        calendars={"source": "Uni", "target": "Uni colored"},
    )
    gateway = FakeCalendarGateway({"Uni": SOURCE})
    install_gateway(monkeypatch, gateway)

    assert cli.main(["--no-tui"]) == cli.EXIT_OK
    assert gateway.created == ["Uni colored"]


def test_env_overrides_the_profile_calendars(
    isolated_env, fake_auth, monkeypatch
) -> None:
    save_profile(
        Config(profile_path=isolated_env / "profile.json"),
        calendars={"source": "Uni", "target": "Uni colored"},
    )
    monkeypatch.setenv("SOURCE_CALENDAR_NAME", "Other")
    monkeypatch.setenv("TARGET_CALENDAR_NAME", "Other colored")
    gateway = FakeCalendarGateway({"Other": SOURCE})
    install_gateway(monkeypatch, gateway)

    assert cli.main(["--no-tui"]) == cli.EXIT_OK
    assert gateway.created == ["Other colored"]
    # Overrides are not written back into the profile.
    assert saved(Config(profile_path=isolated_env / "profile.json"), "calendars") == {
        "source": "Uni",
        "target": "Uni colored",
        "time_zone": None,
    }


def test_main_ical_flag_overrides_env(
    isolated_env, fake_auth, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SOURCE_ICAL_URL", "https://env/feed")
    gateway = FakeCalendarGateway()
    install_gateway(monkeypatch, gateway)
    fetched: list[str] = []

    def fake_urlopen(request, timeout):
        fetched.append(request.full_url)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b"BEGIN:VCALENDAR\nEND:VCALENDAR\n"
        )
        return response

    monkeypatch.setattr("unical.ical_source.urllib.request.urlopen", fake_urlopen)

    assert cli.main(["--ical", "https://cli/feed", "-v"]) == cli.EXIT_OK
    assert fetched == ["https://cli/feed"]
    out = capsys.readouterr().out
    assert "Source: iCal feed at https://cli/<redacted>" in out
    assert "feed" not in out.split("Source: iCal feed at")[1].splitlines()[0]


def test_main_reports_missing_credentials(isolated_env, fake_auth, capsys) -> None:
    fake_auth.return_value.get_credentials.side_effect = CredentialsFileNotFoundError(
        isolated_env / "credentials.json"
    )
    assert cli.main([]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "credentials.json' not found" in out
    # ...and how to get it.
    assert "enable the Google Calendar API" in out
    assert "Desktop app" in out


def test_main_reports_login_required_without_credentials_help(
    isolated_env, fake_auth, capsys
) -> None:
    fake_auth.return_value.get_credentials.side_effect = LoginRequiredError()
    assert cli.main([]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Google login required" in out
    assert "Desktop app" not in out


@pytest.mark.parametrize(
    ("tty", "ci", "allowed"),
    [(True, None, True), (False, None, False), (True, "true", False)],
)
def test_main_allows_browser_login_only_when_interactive(
    isolated_env, fake_auth, monkeypatch, tty, ci, allowed
) -> None:
    monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: tty))
    if ci:
        monkeypatch.setenv("CI", ci)
    fake_auth.return_value.get_credentials.side_effect = LoginRequiredError()

    assert cli.main([]) == cli.EXIT_FAILURE
    assert fake_auth.call_args.kwargs["allow_browser_login"] is allowed


def test_main_reports_login_required(isolated_env, fake_auth, capsys) -> None:
    fake_auth.return_value.get_credentials.side_effect = LoginRequiredError()
    assert cli.main([]) == cli.EXIT_FAILURE
    assert "Google login required" in capsys.readouterr().out


def test_main_reports_invalid_credentials_error(
    isolated_env, fake_auth, capsys
) -> None:
    fake_auth.return_value.get_credentials.side_effect = InvalidCredentialsError(
        "OAuth client file is missing 'client_id'."
    )
    assert cli.main([]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: OAuth client file is missing 'client_id'." in out
    assert "unical auth login" in out


def test_main_reports_refresh_error(isolated_env, fake_auth, capsys) -> None:
    fake_auth.return_value.get_credentials.side_effect = RefreshError(
        "Token has been expired or revoked."
    )
    assert cli.main([]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: Token has been expired or revoked." in out
    assert "unical auth login" in out


def test_main_reports_transport_error(isolated_env, fake_auth, capsys) -> None:
    fake_auth.return_value.get_credentials.side_effect = TransportError(
        "Failed to establish a new connection."
    )
    assert cli.main([]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: Failed to establish a new connection." in out
    assert "internet connection" in out


def test_main_reports_auth_error_with_tui_enabled(
    isolated_env, fake_auth, capsys
) -> None:
    fake_auth.return_value.get_credentials.side_effect = RefreshError(
        "Token has been revoked."
    )
    assert cli.main(["--tui"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: Token has been revoked." in out
    assert "unical auth login" in out


def test_main_quiet_prints_nothing_on_success(
    isolated_env, fake_auth, monkeypatch, capsys
) -> None:
    install_gateway(monkeypatch, FakeCalendarGateway({"Calendar": SOURCE}))
    assert cli.main(["-q"]) == cli.EXIT_OK
    assert capsys.readouterr().out == ""


def test_module_entry_point_shows_help(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["unical", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("unical", run_name="__main__")
    assert exc_info.value.code == 0
    assert "--prune-before" in capsys.readouterr().out


def test_ical_mode_never_reads_the_google_source_calendar(config: Config) -> None:
    ical = (
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:1172587-polimi.it\n"
        "DTSTART:20260917T101500\nDTEND:20260917T121500\n"
        "SUMMARY:Lezione: Didattica - CS\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    gateway = FakeCalendarGateway({"Src": SOURCE, "Tgt": []})
    source = IcalFeedSource("https://x/y", fetch=lambda url: ical)

    assert cli.run(SyncOptions(), config, gateway, NullReporter(), source=source) == 0

    assert gateway.listings == [("id::Tgt", False)]  # target only
    [event] = gateway.events_of("Tgt")
    assert event["id"] == "1172587polimiit284d64df"
    assert event["summary"] == "CS"


# -- terminal UI -------------------------------------------------------------


def test_parse_args_tui() -> None:
    args = cli.parse_args(["exams", "--tui", "--prune-before", "2025-01-01"])
    assert args.tui
    assert args.options == default_opts(
        target=SyncTarget.EXAMS, prune_before=date(2025, 1, 1)
    )


@pytest.mark.parametrize("argv", [["--tui", "-i"], ["--tui", "--dry-run"]])
def test_parse_args_rejects_tui_with_other_modes(argv, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.parse_args(argv)
    assert exc_info.value.code == 2


def test_main_tui_without_textual_fails_before_login(
    isolated_env, fake_auth, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "tui_available", lambda: False)
    assert cli.main(["--tui"]) == cli.EXIT_FAILURE
    assert "pip install 'uni-calendar-coloring'" in capsys.readouterr().out
    fake_auth.assert_not_called()


def test_main_tui_runs_the_app(isolated_env, fake_auth, monkeypatch) -> None:
    pytest.importorskip("textual")
    from unical.tui.app import UnicalApp

    gateway = FakeCalendarGateway({"Calendar": SOURCE})
    install_gateway(monkeypatch, gateway)
    launched: list[UnicalApp] = []
    monkeypatch.setattr(UnicalApp, "run", lambda app: launched.append(app))

    assert cli.main(["lectures", "--tui"]) == cli.EXIT_OK

    [app] = launched
    assert app.options == default_opts(target=SyncTarget.LECTURES)
    assert app.calendars.target == "Calendar Colored"
    assert isinstance(app.source, GoogleCalendarSource)
    assert gateway.batches == []


def test_tui_available_matches_installed_textual() -> None:
    import importlib.util

    assert cli.tui_available() is (importlib.util.find_spec("textual") is not None)


@pytest.mark.parametrize(
    ("argv", "interactive_shell", "expected"),
    [
        ([], True, True),
        (["exams"], True, True),
        ([], False, False),  # cron, CI, pipes
        (["--no-tui"], True, False),
        (["-i"], True, False),
        (["--dry-run"], True, False),
        (["--tui"], False, True),  # explicit request wins over the shell check
    ],
)
def test_tui_is_the_default_in_a_terminal(
    argv, interactive_shell, expected, monkeypatch
) -> None:
    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: interactive_shell)
    assert cli.parse_args(argv).tui is expected


def test_parse_args_rejects_tui_with_no_tui() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.parse_args(["--tui", "--no-tui"])
    assert exc_info.value.code == 2


def test_default_tui_without_textual_falls_back_to_plain_sync(
    isolated_env, fake_auth, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: True)
    monkeypatch.setattr(cli, "tui_available", lambda: False)
    gateway = FakeCalendarGateway({"Calendar": SOURCE})
    install_gateway(monkeypatch, gateway)

    assert cli.main([]) == cli.EXIT_OK

    assert "Running a plain sync instead" in capsys.readouterr().out
    assert gateway.created == ["Calendar Colored"]


def test_run_tui_builds_the_calendar_setup(config: Config, monkeypatch) -> None:
    pytest.importorskip("textual")
    from unical.tui.app import UnicalApp
    from unical.tui.setup import Role

    apps: list[UnicalApp] = []
    monkeypatch.setattr(UnicalApp, "run", lambda self: apps.append(self))
    save_profile(config, calendars={"source": "Uni", "target": "Mine"})
    gateway = FakeCalendarGateway()

    overridden = replace(config, source_calendar_name=None)
    assert cli.run_tui(SyncOptions(), overridden, gateway) == cli.EXIT_OK
    setup = apps[-1].setup
    assert setup.calendars == CalendarSettings(source="Uni", target="Tgt")
    assert setup.overrides == {Role.TARGET: "TARGET_CALENDAR_NAME"}
    assert setup.fixed_source is None
    assert not setup.first_run
    source = setup.source_for("Other")
    assert isinstance(source, GoogleCalendarSource)
    assert source.name == "Other"

    ical = replace(config, source_ical_url="https://ical.example/42/secret")
    cli.run_tui(SyncOptions(), ical, gateway)
    setup = apps[-1].setup
    assert setup.fixed_source == "iCal feed at https://ical.example/<redacted>"
    assert isinstance(setup.source_for("Other"), IcalFeedSource)


def test_run_tui_starts_the_guide_without_a_profile(
    config: Config, monkeypatch
) -> None:
    pytest.importorskip("textual")
    from unical.tui.app import UnicalApp

    apps: list[UnicalApp] = []
    monkeypatch.setattr(UnicalApp, "run", lambda self: apps.append(self))

    cli.run_tui(SyncOptions(), config, FakeCalendarGateway())

    assert apps[-1].setup.first_run


# -- auth subcommands & onboarding -------------------------------------------


def test_auth_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["auth", "--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "import" in out
    assert "status" in out
    assert "login" in out


def test_auth_import_file_default_destination(tmp_path: Path, capsys) -> None:
    src_file = tmp_path / "my_creds.json"
    src_file.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    dest = tmp_path / "config" / "credentials.json"

    ret = cli.main(["auth", "import", str(src_file), "--destination", str(dest)])
    assert ret == cli.EXIT_OK
    assert dest.exists()
    assert src_file.exists()
    assert "Successfully imported credentials" in capsys.readouterr().out


def test_auth_import_file_move(tmp_path: Path, capsys) -> None:
    src_file = tmp_path / "my_creds_to_move.json"
    src_file.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    dest = tmp_path / "config" / "credentials.json"

    ret = cli.main(["auth", "import", str(src_file), "-m", "--destination", str(dest)])
    assert ret == cli.EXIT_OK
    assert dest.exists()
    assert not src_file.exists()


def test_auth_import_file_invalid(tmp_path: Path, capsys) -> None:
    sa_file = tmp_path / "service_account.json"
    sa_file.write_text(json.dumps({"type": "service_account"}))
    dest = tmp_path / "config" / "credentials.json"

    ret = cli.main(["auth", "import", str(sa_file), "--destination", str(dest)])
    assert ret == cli.EXIT_FAILURE
    assert not dest.exists()
    assert "Service Account key" in capsys.readouterr().out


def test_auth_import_interactive_prompt_success(tmp_path: Path, capsys) -> None:
    src_file = tmp_path / "my_creds.json"
    src_file.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    dest = tmp_path / "config" / "credentials.json"

    ret = cli.main(
        ["auth", "import", "--destination", str(dest)],
        prompt_fn=lambda _: str(src_file),
    )
    assert ret == cli.EXIT_OK
    assert dest.exists()


def test_auth_import_interactive_prompt_cancel(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "config" / "credentials.json"
    ret = cli.main(
        ["auth", "import", "--destination", str(dest)],
        prompt_fn=lambda _: "",
    )
    assert ret == cli.EXIT_FAILURE
    assert "Cancelled" in capsys.readouterr().out


def test_auth_status_missing(isolated_env, capsys) -> None:
    ret = cli.main(["auth", "status"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Status: Missing" in out
    assert "unical auth import" in out


def test_auth_status_not_logged_in(isolated_env, capsys) -> None:
    creds_path = isolated_env / "credentials.json"
    creds_path.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )

    ret = cli.main(["auth", "status"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Status: Desktop app client c1" in out
    assert "Status: Not logged in" in out
    assert "unical doctor" in out


def test_auth_status_logged_in(isolated_env, capsys) -> None:
    creds_path = isolated_env / "credentials.json"
    creds_path.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    token_path = isolated_env / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "tok",
                "refresh_token": "ref",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "cid",
                "client_secret": "sec",
                "expiry": "2099-01-01T00:00:00Z",
                "scopes": [],
            }
        )
    )

    ret = cli.main(["auth", "status"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Status: Logged in (token valid until 2099-01-01 00:00 UTC)" in out


def test_auth_status_token_expired(isolated_env, capsys) -> None:
    creds_path = isolated_env / "credentials.json"
    creds_path.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    token_path = isolated_env / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "tok",
                "refresh_token": "ref",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "cid",
                "client_secret": "sec",
                "expiry": "2000-01-01T00:00:00Z",
                "scopes": [],
            }
        )
    )

    ret = cli.main(["auth", "status"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Status: Token expired (will refresh on next run)" in out


def test_auth_login_missing_credentials(isolated_env, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: False)
    ret = cli.main(["auth", "login"])
    assert ret == cli.EXIT_FAILURE
    assert "not found" in capsys.readouterr().out


def test_auth_login_success(isolated_env, monkeypatch, capsys) -> None:
    creds_path = isolated_env / "credentials.json"
    creds_path.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    fake_authenticator = MagicMock()
    monkeypatch.setattr(cli, "Authenticator", fake_authenticator)

    ret = cli.main(["auth", "login"])
    assert ret == cli.EXIT_OK
    fake_authenticator.return_value.get_credentials.assert_called_once()
    assert "Successfully authenticated" in capsys.readouterr().out


def test_auth_status_warns_about_web_clients(isolated_env, capsys) -> None:
    (isolated_env / "credentials.json").write_text(
        json.dumps({"web": {"client_id": "w1", "client_secret": "s1"}})
    )

    assert cli.main(["auth", "status"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Status: Web application client w1" in out
    assert "redirect_uri_mismatch" in out


def test_auth_login_reports_denied_login_with_hints(
    isolated_env, fake_auth, capsys
) -> None:
    (isolated_env / "credentials.json").write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    fake_auth.return_value.get_credentials.side_effect = LoginFailedError(
        "Google login was cancelled or denied (access_denied)."
    )

    assert cli.main(["auth", "login"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: Google login was cancelled" in out
    assert "unical doctor" in out


def test_main_reports_denied_login(isolated_env, fake_auth, capsys) -> None:
    fake_auth.return_value.get_credentials.side_effect = LoginFailedError(
        "Google login was cancelled or denied (access_denied)."
    )

    assert cli.main(["--no-tui"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "access_denied" in out
    assert "unical auth login" in out


def test_credentials_help_mentions_personal_accounts(tmp_path: Path) -> None:
    assert any(
        "@gmail.com" in line for line in cli.credentials_help(tmp_path / "c.json")
    )


# -- doctor -------------------------------------------------------------------


def write_token(directory: Path, **overrides) -> None:
    token = {
        "token": "tok",
        "refresh_token": "ref",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid",
        "client_secret": "sec",
        "expiry": "2099-01-01T00:00:00Z",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
    }
    token.update(overrides)
    (directory / "token.json").write_text(json.dumps(token))


@pytest.fixture
def doctor_env(isolated_env, monkeypatch):
    """A complete setup: Desktop client, valid token and both calendars."""
    (isolated_env / "credentials.json").write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )
    write_token(isolated_env)
    monkeypatch.setenv("SOURCE_CALENDAR_NAME", "Uni")
    monkeypatch.setenv("TARGET_CALENDAR_NAME", "Colored")
    refreshes: list[object] = []
    monkeypatch.setattr(
        doctor.Credentials, "refresh", lambda self, request: refreshes.append(self)
    )
    gateway = FakeCalendarGateway({"Uni": [], "Colored": []})
    install_gateway(monkeypatch, gateway)
    return gateway


def test_doctor_passes_on_a_complete_setup(doctor_env, monkeypatch, capsys) -> None:
    login = MagicMock()
    monkeypatch.setattr(cli.Authenticator, "get_credentials", login)

    assert cli.main(["doctor"]) == cli.EXIT_OK

    out = capsys.readouterr().out
    assert "PASS  Credentials: Desktop app client c1" in out
    assert "PASS  Login token: Logged in" in out
    assert "PASS  Token refresh" in out
    assert "PASS  Calendar API: 2 calendars visible" in out
    assert "PASS  Source calendar: 'Uni'" in out
    assert "PASS  Target calendar: 'Colored' is writable" in out
    assert "0 failed" in out
    login.assert_not_called()


def test_doctor_fails_without_credentials_or_token(isolated_env, capsys) -> None:
    assert cli.main(["doctor"]) == cli.EXIT_FAILURE

    out = capsys.readouterr().out
    assert "WARN  Config directory" in out
    assert "FAIL  Credentials: Missing" in out
    assert "@gmail.com" in out
    assert "FAIL  Login token: Not logged in" in out
    assert "SKIP  Calendar API" in out


def test_doctor_warns_about_web_clients(doctor_env, isolated_env, capsys) -> None:
    (isolated_env / "credentials.json").write_text(
        json.dumps({"web": {"client_id": "w1", "client_secret": "s1"}})
    )

    assert cli.main(["doctor"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "WARN  Credentials: Web application client w1" in out
    assert "redirect_uri_mismatch" in out


def test_doctor_rejects_service_account_keys(doctor_env, isolated_env, capsys):
    (isolated_env / "credentials.json").write_text(
        json.dumps({"type": "service_account"})
    )

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    assert "FAIL  Credentials: Invalid" in capsys.readouterr().out


def test_doctor_fails_when_the_token_lacks_the_calendar_scope(
    doctor_env, isolated_env, capsys
) -> None:
    write_token(isolated_env, scopes=["openid"])

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "FAIL  Login token: Missing the Calendar scope" in out
    assert "SKIP  Calendar API" in out


def test_doctor_reports_a_revoked_login(
    doctor_env, isolated_env, monkeypatch, capsys
) -> None:
    write_token(isolated_env, expiry="2000-01-01T00:00:00Z")

    def revoked(self, request):
        raise RefreshError("invalid_grant")

    monkeypatch.setattr(doctor.Credentials, "refresh", revoked)

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "PASS  Login token: Token expired" in out
    assert "FAIL  Token refresh: The saved login expired or was revoked" in out
    assert "unical auth login" in out
    assert "SKIP  Calendar API" in out


def test_doctor_reports_an_expired_token_without_refresh_token(
    doctor_env, isolated_env, capsys
) -> None:
    write_token(isolated_env, expiry="2000-01-01T00:00:00Z", refresh_token=None)

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    assert "cannot be refreshed" in capsys.readouterr().out


def test_doctor_hints_at_enabling_the_calendar_api(
    doctor_env, monkeypatch, capsys
) -> None:
    def disabled():
        raise RuntimeError(
            "Calendar API has not been used in project 1 before or it is disabled"
        )

    monkeypatch.setattr(doctor_env, "list_calendars", disabled)

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "FAIL  Calendar API" in out
    assert doctor.CALENDAR_API_URL in out


def test_doctor_fails_on_a_read_only_target(doctor_env, capsys) -> None:
    doctor_env.read_only.add("Colored")

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    assert "FAIL  Target calendar: 'Colored' is read-only" in capsys.readouterr().out


def test_doctor_calendar_lookups(doctor_env, capsys) -> None:
    del doctor_env.calendars["id::Colored"]
    del doctor_env.calendars["id::Uni"]

    assert cli.main(["doctor"]) == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "FAIL  Source calendar: 'Uni' not found" in out
    assert "WARN  Target calendar: 'Colored' not found" in out


def test_doctor_skips_the_source_calendar_for_ical(
    doctor_env, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SOURCE_ICAL_URL", "https://example.com/feed.ics?token=x")
    del doctor_env.calendars["id::Uni"]

    assert cli.main(["doctor"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "PASS  Source calendar: iCal feed" in out
    assert "token=x" not in out


def test_main_first_run_triggers_wizard_when_tui(isolated_env, monkeypatch) -> None:
    pytest.importorskip("textual")
    from unical.tui.app import UnicalApp

    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: True)
    monkeypatch.setattr(cli, "tui_available", lambda: True)

    valid_creds = isolated_env / "credentials.json"
    valid_creds.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )

    monkeypatch.setattr(
        "unical.tui.wizard.run_credentials_wizard",
        lambda destination=None: valid_creds,
    )
    apps: list[UnicalApp] = []
    monkeypatch.setattr(UnicalApp, "run", lambda self: apps.append(self))

    fake_auth_inst = MagicMock()
    fake_auth_inst.return_value.get_credentials.side_effect = [
        CredentialsFileNotFoundError(isolated_env / "credentials.json"),
        MagicMock(),
    ]
    monkeypatch.setattr(cli, "Authenticator", fake_auth_inst)
    monkeypatch.setattr(
        cli.GoogleCalendarClient,
        "from_credentials",
        classmethod(lambda cls, c: FakeCalendarGateway()),
    )

    ret = cli.main([])
    assert ret == cli.EXIT_OK
    assert len(apps) == 1


def test_main_first_run_triggers_cli_onboarding_when_not_tui(
    isolated_env, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: True)
    monkeypatch.setattr(cli, "tui_available", lambda: False)

    src_file = isolated_env / "downloaded.json"
    src_file.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )

    fake_auth_inst = MagicMock()
    fake_auth_inst.return_value.get_credentials.side_effect = [
        CredentialsFileNotFoundError(isolated_env / "credentials.json"),
        MagicMock(),
    ]
    monkeypatch.setattr(cli, "Authenticator", fake_auth_inst)
    install_gateway(monkeypatch, FakeCalendarGateway({"Calendar": SOURCE}))

    ret = cli.main([], prompt_fn=lambda _: str(src_file))
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Credentials saved to" in out


def test_main_reports_auth_error_after_cli_onboarding(
    isolated_env, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "_is_interactive_shell", lambda: True)
    monkeypatch.setattr(cli, "tui_available", lambda: False)

    src_file = isolated_env / "downloaded.json"
    src_file.write_text(
        json.dumps({"installed": {"client_id": "c1", "client_secret": "s1"}})
    )

    fake_auth_inst = MagicMock()
    fake_auth_inst.return_value.get_credentials.side_effect = [
        CredentialsFileNotFoundError(isolated_env / "credentials.json"),
        RefreshError("Token revoked"),
    ]
    monkeypatch.setattr(cli, "Authenticator", fake_auth_inst)

    ret = cli.main([], prompt_fn=lambda _: str(src_file))
    assert ret == cli.EXIT_FAILURE
    out = capsys.readouterr().out
    assert "Authentication failed: Token revoked" in out
    assert "unical auth login" in out


def test_parse_args_update_check_flags() -> None:
    args_no_check = cli.parse_args(["--no-update-check"])
    assert args_no_check.check_update is False
    assert args_no_check.check_update_only is False

    args_check_only = cli.parse_args(["--check-update"])
    assert args_check_only.check_update is True
    assert args_check_only.check_update_only is True


def test_main_version_no_check(capsys: pytest.CaptureFixture[str]) -> None:
    ret = cli.main(["version", "--no-check"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert f"unical {cli.__version__}" in out
    assert "Checking for updates..." not in out


def test_main_version_with_check(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from unical.version_check import VersionCheckResult

    monkeypatch.setattr(
        "unical.cli.main.check_for_updates",
        lambda **kw: VersionCheckResult("1.0.1", "1.0.2", True),
    )
    monkeypatch.setattr("unical.cli.main.should_check_for_updates", lambda: True)

    ret = cli.main(["version"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    plain = re.sub(r"\[[0-9;]*m", "", out)
    assert f"unical {cli.__version__}" in plain
    assert "Checking for updates..." in plain
    assert "A new version of unical is available: 1.0.1" in plain
    assert "1.0.2" in plain


def test_main_check_update_flag(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from unical.version_check import VersionCheckResult

    monkeypatch.setattr(
        "unical.cli.main.check_for_updates",
        lambda **kw: VersionCheckResult("1.0.1", "1.0.1", False),
    )
    monkeypatch.setattr("unical.cli.main.should_check_for_updates", lambda: True)

    ret = cli.main(["--check-update"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert f"unical {cli.__version__}" in out
    assert "You are running the latest version" in out


def test_main_auth_status_includes_version_and_update(
    isolated_env: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from unical.version_check import write_version_cache

    cache_file = isolated_env / "version_check.json"
    write_version_cache(cache_file, "9.9.9", checked_at=time.time())
    monkeypatch.setattr(
        "unical.cli.main.default_version_cache_path", lambda: cache_file
    )

    ret = cli.main(["auth", "status"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    assert f"Version:                 {cli.__version__}" in out
    assert "Update status:           Update available: 9.9.9" in out


def test_main_displays_update_notice_after_sync(
    isolated_env: Path,
    fake_auth: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from unical.version_check import VersionCheckResult

    install_gateway(monkeypatch, FakeCalendarGateway({"Calendar": SOURCE}))

    class FakeChecker:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def get_result(self, timeout=0.3):
            return VersionCheckResult("1.0.1", "1.0.2", True)

    monkeypatch.setattr("unical.cli.main.AsyncUpdateChecker", FakeChecker)

    ret = cli.main(["--no-tui"])
    assert ret == cli.EXIT_OK
    out = capsys.readouterr().out
    plain = re.sub(r"\[[0-9;]*m", "", out)
    assert "A new version of unical is available: 1.0.1" in plain
    assert "1.0.2" in plain


def test_parse_args_window_and_course() -> None:
    args = cli.parse_args(
        [
            "--from",
            "2026-03-01",
            "--to",
            "2026-09-15",
            "--course",
            "Algorithms",
        ]
    )
    assert args.options.window_from == date(2026, 3, 1)
    assert args.options.window_to == date(2026, 9, 15)
    assert not args.options.all_time
    assert args.options.course == "Algorithms"


def test_parse_args_all_time() -> None:
    args = cli.parse_args(["--all-time"])
    assert args.options.all_time
    assert args.options.window_from is None
    assert args.options.window_to is None


def test_parse_args_all_time_conflict_fails(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.parse_args(["--all-time", "--from", "2026-03-01"])
    assert exc_info.value.code == 2
    assert (
        "--all-time cannot be combined with --from or --to" in capsys.readouterr().err
    )


def test_parse_args_inverted_window_fails(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.parse_args(["--from", "2026-09-15", "--to", "2026-03-01"])
    assert exc_info.value.code == 2
    assert "--from date cannot be after --to date" in capsys.readouterr().err


def test_doctor_config_dir_states(tmp_path: Path, monkeypatch) -> None:
    assert doctor.check_config_dir(tmp_path).status is doctor.Status.PASS
    monkeypatch.setattr(doctor.os, "access", lambda path, mode: False)
    check = doctor.check_config_dir(tmp_path)
    assert check.status is doctor.Status.FAIL
    assert "not writable" in check.detail


def test_doctor_unreadable_token(tmp_path: Path) -> None:
    (tmp_path / "token.json").write_text("{}")
    check, creds = doctor.load_token(tmp_path / "token.json")
    assert check.status is doctor.Status.FAIL
    assert "Unreadable" in check.detail
    assert creds is None

    (tmp_path / "dir_token").mkdir()
    check, creds = doctor.load_token(tmp_path / "dir_token")
    assert check.status is doctor.Status.FAIL
    assert creds is None


def test_doctor_refresh_states() -> None:
    no_refresh = MagicMock(refresh_token=None)
    assert doctor.check_refresh(no_refresh).status is doctor.Status.WARN

    offline = MagicMock(refresh_token="r")
    offline.refresh.side_effect = TransportError("offline")
    check = doctor.check_refresh(offline, request_factory=object)
    assert check.status is doctor.Status.FAIL
    assert "Could not reach Google" in check.detail


def test_doctor_hints_at_logging_in_again_for_missing_scopes() -> None:
    gateway = MagicMock()
    gateway.list_calendars.side_effect = RuntimeError("insufficientPermissions")
    [check] = doctor.check_calendars(gateway, CalendarSettings(), ical_source=False)
    assert check.status is doctor.Status.FAIL
    assert check.hint == doctor.LOGIN_AGAIN
