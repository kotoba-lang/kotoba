"""omni.usd compat — minimal Stage/Layer/Prim surface for Cartpole-class scenes.

Mirrors public `omni.usd` API documented in NVIDIA Omniverse Kit Public API.
Backed by kotodama.nv_compat._kernel URDF parser (R1.1) and will be backed
by kami-usd (tinyusdz + Hydra) at R1.x for full USD support.

NOTE: at R1.1 this only handles .urdf input as a USD-like Stage; binary .usdc
and .usdz arrive when kami-usd lands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .._kernel import ArticulatedSystem, parse_urdf


@dataclass
class Prim:
    """Mirror of pxr.Usd.Prim (subset)."""
    path: str
    type_name: str
    attributes: dict


@dataclass
class Layer:
    """Mirror of pxr.Sdf.Layer (subset)."""
    identifier: str
    contents: str


class Stage:
    """Mirror of pxr.Usd.Stage. Holds an articulated system + scene metadata."""

    def __init__(self, root_layer: Layer, system: ArticulatedSystem):
        self._root_layer = root_layer
        self.system = system

    @classmethod
    def open(cls, path_or_text: str) -> "Stage":
        """omni.usd.Stage.Open() mirror. Accepts a URDF string or file path."""
        text = path_or_text
        if "\n" not in path_or_text and len(path_or_text) < 4096:
            try:
                with open(path_or_text, "r", encoding="utf-8") as f:
                    text = f.read()
            except (OSError, FileNotFoundError):
                pass  # treat as inline text
        sys = parse_urdf(text)
        layer = Layer(identifier=path_or_text, contents=text)
        return cls(layer, sys)

    def get_root_layer(self) -> Layer:
        return self._root_layer

    def get_prim_at_path(self, path: str) -> Optional[Prim]:
        # /World/cartpole/cart → look up cart link
        last = path.rstrip("/").rsplit("/", 1)[-1]
        for link in self.system.links:
            if link.name == last:
                return Prim(
                    path=path,
                    type_name="Xform",
                    attributes={
                        "mass": link.inertia.mass,
                        "ixx": link.inertia.ixx,
                        "iyy": link.inertia.iyy,
                        "izz": link.inertia.izz,
                    },
                )
        for j in self.system.joints:
            if j.name == last:
                return Prim(
                    path=path,
                    type_name="PhysicsJoint",
                    attributes={
                        "type": j.kind,
                        "parent": j.parent,
                        "child": j.child,
                        "lower": j.lower,
                        "upper": j.upper,
                        "axis": j.axis,
                    },
                )
        return None

    def traverse(self):
        """Yield all Prims in the stage."""
        for link in self.system.links:
            yield Prim(
                path=f"/World/{self.system.name}/{link.name}",
                type_name="Xform",
                attributes={"mass": link.inertia.mass},
            )
        for j in self.system.joints:
            yield Prim(
                path=f"/World/{self.system.name}/joints/{j.name}",
                type_name="PhysicsJoint",
                attributes={"type": j.kind},
            )


def get_stage_from_text(urdf_or_usd_text: str) -> Stage:
    """Convenience wrapper, not in upstream Omniverse but useful for tests."""
    return Stage(
        root_layer=Layer(identifier="<inline>", contents=urdf_or_usd_text),
        system=parse_urdf(urdf_or_usd_text),
    )
