"""isaaclab.markers — 3D visualization marker primitives.

Mirror of `isaaclab.markers` (Isaac Lab 1.x). The canonical API for spawning
debug visualization geometry at world positions — used in every example to
show commands (arrow at target pose), contact points (sphere), coordinate
frames (RGB axis triad), state-machine status (color-coded cuboid), etc.

In upstream Isaac Lab the marker prims actually render via UsdGeom; in the
nv_compat surface the actual rendering is delegated to whatever viewport
binding the host wires up (omni.kit.viewport.utility — future iter), so
this module records per-instance marker state (translations / orientations /
indices / colors) and exposes accessors that a renderer subscribes to.

Surface:
  - MarkerKind            — enum of supported primitive types (SPHERE,
                             CUBOID, CONE, CYLINDER, COORDINATE_FRAME,
                             ARROW_X, ARROW_Y, ARROW_Z)
  - MarkerCfg             — kind + color (rgb) + scale + per-kind params
                             (radius, height)
  - VisualizationMarkersCfg — prim_path + named marker dict + max_count cap
  - VisualizationMarkers  — visualize(translations, orientations,
                             marker_indices) per-instance state recorder
  - Pre-built marker cfgs — SPHERE / CUBOID / CONE / CYLINDER /
                             COORDINATE_FRAME / RED_ARROW_X_MARKER_CFG
                             (matches Isaac Lab's `markers.config` constants)

Standard usage:

    cfg = VisualizationMarkersCfg(
        prim_path="/Visuals/cartpole_targets",
        markers={
            "target":  sim_utils.SphereCfg(radius=0.05, color=(1.0, 0.0, 0.0)),
            "current": sim_utils.SphereCfg(radius=0.05, color=(0.0, 1.0, 0.0)),
        },
    )
    markers = VisualizationMarkers(cfg)
    # On each step, push the (target, current) positions into the buffer:
    markers.visualize(
        translations=[(0.0, 0.0, 1.0), (0.1, 0.0, 0.95)],
        marker_indices=[0, 1],
    )
    # Renderer reads via markers.get_state():
    # → [{"name": "target", "pos": (0, 0, 1), "quat": (0,0,0,1), ...},
    #    {"name": "current", "pos": (0.1, 0, 0.95), "quat": (0,0,0,1), ...}]
"""

from .visualization_markers import (
    MarkerCfg,
    MarkerKind,
    VisualizationMarkers,
    VisualizationMarkersCfg,
)
from .config import (
    ARROW_X_MARKER_CFG,
    ARROW_Y_MARKER_CFG,
    ARROW_Z_MARKER_CFG,
    BLUE_ARROW_X_MARKER_CFG,
    COORDINATE_FRAME_MARKER_CFG,
    CUBOID_MARKER_CFG,
    CYLINDER_MARKER_CFG,
    GREEN_SPHERE_MARKER_CFG,
    RED_ARROW_X_MARKER_CFG,
    RED_SPHERE_MARKER_CFG,
    SPHERE_MARKER_CFG,
)

__all__ = [
    "MarkerKind", "MarkerCfg",
    "VisualizationMarkersCfg", "VisualizationMarkers",
    "SPHERE_MARKER_CFG", "RED_SPHERE_MARKER_CFG", "GREEN_SPHERE_MARKER_CFG",
    "CUBOID_MARKER_CFG", "CYLINDER_MARKER_CFG",
    "COORDINATE_FRAME_MARKER_CFG",
    "ARROW_X_MARKER_CFG", "ARROW_Y_MARKER_CFG", "ARROW_Z_MARKER_CFG",
    "RED_ARROW_X_MARKER_CFG", "BLUE_ARROW_X_MARKER_CFG",
]
