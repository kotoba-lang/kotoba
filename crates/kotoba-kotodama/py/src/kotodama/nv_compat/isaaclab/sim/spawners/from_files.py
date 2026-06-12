"""File spawners — load .usd / .usda / .urdf onto the stage.

Mirror of `isaaclab.sim.spawners.from_files.UsdFileCfg`. Accepts a file path
(or inline text via `usd_text` / `urdf_text` overrides) and records the
spawn request. In upstream Isaac Lab the spawner instantiates a USD
reference / payload on the active Stage; in nv_compat the prim record
carries the file identifier + (optionally) the inline content so a
downstream USD parser can load it later.

USDC binary parsing is a separate iter; this module only handles the
declarative spawn-record contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .spawner import SpawnedPrim, SpawnerCfgBase, get_registry


@dataclass
class UsdFileCfg(SpawnerCfgBase):
    """USD / URDF file reference.

    Either `usd_path` (filesystem path resolved at spawn time) OR
    `usd_text` (inline content) MUST be set. When both are set, `usd_text`
    wins. URDF input (`.urdf` extension on usd_path, or `urdf_text`) is
    accepted as well — the spawned prim records the format in
    `cfg.detected_format`.

    `variants` is a dict of {variant_set: variant_value} matching upstream's
    Sdf.VariantSelection. Unused in nv_compat but preserved for API parity.

    `articulation_props` / `rigid_props` / `mass_props` are forwarded
    verbatim into `cfg.extras` as `articulation_props=...`. Real USD
    backends consume these.
    """
    usd_path: str = ""
    usd_text: str = ""
    urdf_text: str = ""
    variants: dict = None
    # Populated at spawn-time by spawn_from_usd().
    detected_format: str = ""

    def __post_init__(self):
        if self.variants is None:
            self.variants = {}


def spawn_from_usd(prim_path: str, cfg: UsdFileCfg,
                   translation: tuple = (0.0, 0.0, 0.0),
                   orientation: tuple = (0.0, 0.0, 0.0, 1.0),
                   scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    """Spawn a USD / URDF file reference. Resolves `usd_path` (if set and
    no inline text) and records the spawn request."""
    if not prim_path:
        raise ValueError("prim_path is required")
    if not (cfg.usd_path or cfg.usd_text or cfg.urdf_text):
        raise ValueError(
            "UsdFileCfg requires at least one of usd_path / usd_text / urdf_text"
        )

    # Detect format from path extension or inline text.
    fmt = ""
    inline = ""
    if cfg.urdf_text:
        fmt, inline = "urdf", cfg.urdf_text
    elif cfg.usd_text:
        fmt, inline = "usda", cfg.usd_text
    elif cfg.usd_path:
        ext = os.path.splitext(cfg.usd_path)[1].lower()
        if ext == ".urdf":
            fmt = "urdf"
        elif ext in (".usda", ".usd"):
            fmt = "usda"
        elif ext == ".usdc":
            fmt = "usdc"   # binary — parser arrives in a future iter
        elif ext == ".usdz":
            fmt = "usdz"
        else:
            fmt = "unknown"

    cfg.detected_format = fmt

    prim = SpawnedPrim(
        path=prim_path, kind="usd_file", cfg=cfg,
        translation=tuple(translation), orientation=tuple(orientation),
        scale=tuple(scale),
        extras={"detected_format": fmt, "inline": inline},
    )
    get_registry().add(prim)
    return prim
