"""Compatibility wrapper for the retry scheduler module."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


_REPO_ROOT = Path(__file__).resolve().parents[4]
_WORKER_SERVICE_DIR = _REPO_ROOT / "services" / "airex-worker"
_CORE_SERVICE_DIR = _REPO_ROOT / "services" / "airex-core"
_DEF_PATH = _WORKER_SERVICE_DIR / "app" / "core" / "retry_scheduler.py"


for _path in (str(_WORKER_SERVICE_DIR), str(_CORE_SERVICE_DIR)):
    if _path in sys.path:
        sys.path.remove(_path)
    sys.path.insert(0, _path)

sys.modules.pop("app", None)


def _load_retry_scheduler_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "airex_worker_compat_retry_scheduler",
        _DEF_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load retry scheduler module from {_DEF_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_retry_scheduler_module = _load_retry_scheduler_module()

__all__ = [name for name in dir(_retry_scheduler_module) if not name.startswith("_")]

globals().update({name: getattr(_retry_scheduler_module, name) for name in __all__})
