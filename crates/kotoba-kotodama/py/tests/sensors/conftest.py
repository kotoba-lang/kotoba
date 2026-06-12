"""Conftest for sensors tests — isolated module loader.

The top-level kotodama package's ``__init__`` imports a langchain /
pydantic chain (via ``langgraph_checkpoint_rw``) that may break under
mismatched ``pydantic-core`` / ``pydantic`` versions in the operator's
environment. The W1 sensor modules themselves only depend on stdlib +
their own ``..base`` Protocol/dataclass module, so we can load them in
isolation via ``importlib`` and validate them without dragging the
broken chain into the test process.

This conftest exposes two fixtures:

- ``load_sensor`` — load a sensor module by dotted path
  (``corp.lei_sensor``, ``gov.uk_hansard_sensor``, etc.) bypassing the
  kotodama top-level ``__init__``.
- ``pin_resolver`` — a helper to construct a StaticPinResolver +
  DatasetPin around a temp annex root.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Callable

import pytest


SENSORS_ROOT = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "kotodama"
    / "organism"
    / "sensors"
)


def _stub_parent_packages() -> None:
    """Install empty namespace packages so child module loads resolve."""
    for pkg in (
        "kotodama",
        "kotodama.organism",
        "kotodama.organism.sensors",
        "kotodama.organism.sensors.corp",
        "kotodama.organism.sensors.gov",
    ):
        if pkg in sys.modules:
            continue
        mod = types.ModuleType(pkg)
        mod.__path__ = []
        sys.modules[pkg] = mod
    # Wire __path__ so submodule loads can find their siblings.
    sys.modules["kotodama"].__path__ = [str(SENSORS_ROOT.parent.parent)]
    sys.modules["kotodama.organism"].__path__ = [str(SENSORS_ROOT.parent)]
    sys.modules["kotodama.organism.sensors"].__path__ = [str(SENSORS_ROOT)]
    sys.modules["kotodama.organism.sensors.corp"].__path__ = [
        str(SENSORS_ROOT / "corp")
    ]
    sys.modules["kotodama.organism.sensors.gov"].__path__ = [
        str(SENSORS_ROOT / "gov")
    ]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def base_module():
    """Load kotodama.organism.sensors.base in isolation."""
    _stub_parent_packages()
    return _load(
        "kotodama.organism.sensors.base",
        SENSORS_ROOT / "base.py",
    )


@pytest.fixture(scope="session")
def corp_base_module(base_module):
    """Load kotodama.organism.sensors.corp.base."""
    return _load(
        "kotodama.organism.sensors.corp.base",
        SENSORS_ROOT / "corp" / "base.py",
    )


@pytest.fixture(scope="session")
def gov_base_module(base_module):
    """Load kotodama.organism.sensors.gov.base."""
    return _load(
        "kotodama.organism.sensors.gov.base",
        SENSORS_ROOT / "gov" / "base.py",
    )


@pytest.fixture
def load_sensor(base_module, corp_base_module, gov_base_module) -> Callable:
    """Return a callable that loads a sensor module by dotted suffix.

    Example::

        lei_mod = load_sensor("corp.lei_sensor")
        sensor_cls = lei_mod.GleifLeiSensor
    """

    def _loader(dotted: str):
        # dotted is "corp.lei_sensor" / "gov.uk_hansard_sensor" etc.
        ns, leaf = dotted.split(".", 1)
        full = f"kotodama.organism.sensors.{ns}.{leaf}"
        path = SENSORS_ROOT / ns / f"{leaf}.py"
        return _load(full, path)

    return _loader


@pytest.fixture
def make_pin(base_module):
    """Build a DatasetPin + StaticPinResolver bound to a subdataset name."""

    def _build(name: str, *, revision: str = "sha256:test", license: str = "test", tier: str = "A"):
        pin = base_module.DatasetPin(
            name=name,
            revision=revision,
            cid_map_cid="bafy_test_cid",
            license=license,
            tier=tier,
            created_at="2026-05-27T00:00:00Z",
        )
        resolver = base_module.StaticPinResolver(pins={name: pin})
        return pin, resolver

    return _build
