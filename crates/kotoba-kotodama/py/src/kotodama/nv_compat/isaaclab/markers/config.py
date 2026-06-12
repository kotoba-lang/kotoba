"""Pre-built marker cfg constants — matches Isaac Lab's `markers.config` set.

These constants are the canonical shorthand for the common marker shapes.
Each is a `VisualizationMarkersCfg` with one named marker; tasks that
need multiple shapes compose them via `VisualizationMarkersCfg(markers={
    "target": SPHERE_MARKER_CFG.markers["sphere"],
    "current": CUBOID_MARKER_CFG.markers["cuboid"],
})`.

Naming follows Isaac Lab convention:
  - SPHERE_MARKER_CFG       — white sphere, r=0.05
  - RED_SPHERE_MARKER_CFG   — red, otherwise as above
  - GREEN_SPHERE_MARKER_CFG — green
  - CUBOID_MARKER_CFG       — white cuboid, 5×5×5 cm
  - CYLINDER_MARKER_CFG     — white cylinder, r=0.05, h=0.1
  - COORDINATE_FRAME_MARKER_CFG — RGB axis triad, len=0.1
  - ARROW_X / Y / Z_MARKER_CFG — colored arrows along body axes
  - RED_ARROW_X_MARKER_CFG / BLUE_ARROW_X_MARKER_CFG — colored variants
"""

from __future__ import annotations

from .visualization_markers import MarkerCfg, MarkerKind, VisualizationMarkersCfg


def _single(prim_path: str, name: str, cfg: MarkerCfg) -> VisualizationMarkersCfg:
    return VisualizationMarkersCfg(prim_path=prim_path, markers={name: cfg})


SPHERE_MARKER_CFG = _single(
    "/Visuals/Sphere", "sphere",
    MarkerCfg(kind=MarkerKind.SPHERE, color=(1.0, 1.0, 1.0), radius=0.05),
)

RED_SPHERE_MARKER_CFG = _single(
    "/Visuals/RedSphere", "sphere",
    MarkerCfg(kind=MarkerKind.SPHERE, color=(1.0, 0.0, 0.0), radius=0.05),
)

GREEN_SPHERE_MARKER_CFG = _single(
    "/Visuals/GreenSphere", "sphere",
    MarkerCfg(kind=MarkerKind.SPHERE, color=(0.0, 1.0, 0.0), radius=0.05),
)

CUBOID_MARKER_CFG = _single(
    "/Visuals/Cuboid", "cuboid",
    MarkerCfg(kind=MarkerKind.CUBOID, color=(1.0, 1.0, 1.0), size=(0.05, 0.05, 0.05)),
)

CYLINDER_MARKER_CFG = _single(
    "/Visuals/Cylinder", "cylinder",
    MarkerCfg(kind=MarkerKind.CYLINDER, color=(1.0, 1.0, 1.0),
              radius=0.05, height=0.1),
)

COORDINATE_FRAME_MARKER_CFG = _single(
    "/Visuals/CoordinateFrame", "frame",
    MarkerCfg(kind=MarkerKind.COORDINATE_FRAME, color=(1.0, 1.0, 1.0),
              axis_length=0.1),
)

ARROW_X_MARKER_CFG = _single(
    "/Visuals/ArrowX", "arrow_x",
    MarkerCfg(kind=MarkerKind.ARROW_X, color=(1.0, 1.0, 1.0)),
)

ARROW_Y_MARKER_CFG = _single(
    "/Visuals/ArrowY", "arrow_y",
    MarkerCfg(kind=MarkerKind.ARROW_Y, color=(1.0, 1.0, 1.0)),
)

ARROW_Z_MARKER_CFG = _single(
    "/Visuals/ArrowZ", "arrow_z",
    MarkerCfg(kind=MarkerKind.ARROW_Z, color=(1.0, 1.0, 1.0)),
)

RED_ARROW_X_MARKER_CFG = _single(
    "/Visuals/RedArrowX", "arrow_x",
    MarkerCfg(kind=MarkerKind.ARROW_X, color=(1.0, 0.0, 0.0)),
)

BLUE_ARROW_X_MARKER_CFG = _single(
    "/Visuals/BlueArrowX", "arrow_x",
    MarkerCfg(kind=MarkerKind.ARROW_X, color=(0.0, 0.0, 1.0)),
)
