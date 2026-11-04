"""Load a hyphenated plugin directory as a package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_package(root: Path, name: str):
    root = root.resolve()
    spec = importlib.util.spec_from_file_location(
        name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {root}")
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(root)]
    module.__package__ = name
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
