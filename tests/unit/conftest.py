"""Unit-test shared fixtures (hermetic config loading).

Unlike integration/e2e tests, unit tests must not load the real ``config/.env``
(which holds live API keys): the autouse fixture below redirects
``load_settings`` to a non-existent ``.env`` so a standalone ``pytest
tests/unit`` run stays clean.  Dedicated dotenv tests opt back in by passing an
explicit ``env_file=``.
"""

from pathlib import Path

import pytest

from src.core import settings as settings_module

# Match tests/conftest.py's PROJECT_ROOT resolution.
_PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point load_settings at a non-existent .env so unit tests stay hermetic.

    load_settings() resolves ``env_file`` against the module-level DEFAULT_ENV_FILE
    inside the function body, so monkeypatching the constant redirects every unit
    test (dedicated dotenv tests pass an explicit ``env_file=`` to opt back in).
    """
    monkeypatch.setattr(
        settings_module, "DEFAULT_ENV_FILE", _PROJECT_ROOT / "config" / "__no_such_env__.env"
    )
