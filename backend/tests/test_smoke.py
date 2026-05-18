"""Trivial smoke tests to verify the test harness runs."""

from asuadvisr import __version__
from asuadvisr.settings import Settings


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_settings_loads_with_no_env() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.supabase_url == ""
    assert s.anthropic_api_key == ""
