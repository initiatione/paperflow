import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_epi_runtime_config(monkeypatch, tmp_path):
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(tmp_path / "missing-epi-runtime.json"))
