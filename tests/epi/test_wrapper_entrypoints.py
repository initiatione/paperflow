import importlib.util
import sys
from pathlib import Path

import runpy


PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins" / "paper-source"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remove_sys_path(path):
    value = str(path)
    while value in sys.path:
        sys.path.remove(value)


def test_orchestrator_wrapper_imports_bundled_runtime_main():
    runtime_root = (PLUGIN_ROOT / "scripts" / "build").resolve()
    _remove_sys_path(runtime_root)

    module = _load_module(PLUGIN_ROOT / "scripts" / "orchestrator.py", "epi_orchestrator_wrapper_test")

    try:
        from epi.orchestrator import main

        assert module.runtime_root == runtime_root
        assert sys.path[0] == str(runtime_root)
        assert module.main is main
    finally:
        _remove_sys_path(runtime_root)


def test_wiki_init_wrapper_imports_bundled_runtime_main():
    runtime_root = (PLUGIN_ROOT / "scripts" / "build").resolve()
    _remove_sys_path(runtime_root)

    module = _load_module(PLUGIN_ROOT / "scripts" / "init_paper_wiki.py", "epi_wiki_init_wrapper_test")

    try:
        from epi.wiki_init import main

        assert module.runtime_root == runtime_root
        assert sys.path[0] == str(runtime_root)
        assert module.main is main
    finally:
        _remove_sys_path(runtime_root)


def test_mineru_wrapper_runs_bundled_runtime_script(monkeypatch):
    calls = []

    def fake_run_path(path, run_name=None):
        calls.append((Path(path), run_name))
        return {}

    monkeypatch.setattr(runpy, "run_path", fake_run_path)

    module = _load_module(
        PLUGIN_ROOT / "skills" / "mineru-paper-parser" / "scripts" / "mineru_batch_to_md.py",
        "epi_mineru_wrapper_test",
    )

    expected = PLUGIN_ROOT / "build" / "mineru-paper-parser" / "mineru_batch_to_md.py"
    assert module.runtime_script == expected
    assert calls == [(expected, "__main__")]
