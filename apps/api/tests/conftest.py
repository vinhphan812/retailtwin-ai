import sys
import os

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from retailtwin_api.main import create_app
from retailtwin_api.settings import DEFAULT_FIXTURE, Settings

_SETTINGS_ENV = (
    "APP_ENV",
    "API_HOST",
    "API_PORT",
    "CORS_ORIGINS",
    "STORE_ID",
    "STORE_FIXTURE_PATH",
    "LOG_LEVEL",
)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for key in _SETTINGS_ENV:
        monkeypatch.delenv(key, raising=False)
    return Settings(
        _env_file=None,
        app_env="test",
        store_id="store-001",
        store_fixture_path=DEFAULT_FIXTURE,
    )


@pytest.fixture
def client(settings: Settings):
    """Standard test client with demo orchestrator set up (normal case)."""
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def client_no_demo(settings: Settings) -> TestClient:
    """Test client with demo orchestrator intentionally NOT set up.

    Creates the app normally (demo setup runs), then explicitly clears
    demo_orchestrator so demo routes return 503.
    """
    application = create_app(settings)
    # Clear the orchestrator so routes hit the "not initialised" branch
    application.state.demo_orchestrator = None
    with TestClient(application) as test_client:
        yield test_client
