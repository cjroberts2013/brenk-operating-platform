"""Shared pytest fixtures."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_work_order() -> dict:
    """A real ServiceChannel work order response, scrubbed."""
    path = FIXTURES_DIR / "workorder_detail.json"
    if not path.exists():
        pytest.skip("Sample work order fixture not present yet")
    return json.loads(path.read_text())


@pytest.fixture
def sample_notes_response() -> dict:
    """A real ServiceChannel notes response, scrubbed."""
    path = FIXTURES_DIR / "workorder_notes.json"
    if not path.exists():
        pytest.skip("Sample notes fixture not present yet")
    return json.loads(path.read_text())


@pytest.fixture
def sample_work_order_list() -> list[dict]:
    """A scrubbed work-order list response (mirrors the /v3/workorders shape)."""
    path = FIXTURES_DIR / "workorder_list.json"
    return json.loads(path.read_text())
