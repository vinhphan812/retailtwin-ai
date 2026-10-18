"""Tests for the composition root."""

import pytest

from retailtwin_api.composition import build_composition
from retailtwin_api.settings import Settings


def test_build_composition_dev():
    """Dev environment should build successfully."""
    settings = Settings(app_env="development", live_twin_backend="memory")
    composition = build_composition(settings)

    assert composition is not None
    assert composition.settings is settings
    assert composition.event_pipe is not None


def test_build_composition_requires_firestore_in_production():
    """Production should require Firestore backend."""
    from retailtwin_api.llm.factory import ConfigurationError

    settings = Settings(app_env="production", live_twin_backend="memory")

    with pytest.raises(ConfigurationError, match="production requires LIVE_TWIN_BACKEND=firestore"):
        build_composition(settings)
