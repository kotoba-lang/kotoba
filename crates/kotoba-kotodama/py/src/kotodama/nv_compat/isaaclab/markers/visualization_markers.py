"""VisualizationMarkers implementation.

Records per-instance marker state (translation + orientation + index) so a
downstream renderer subscriber can read the live state without coupling to
this module's specific data layout.

Buffer model: each visualize() call REPLACES the buffer (matches Isaac Lab's
"set every active marker every step" idiom — partial updates aren't a
first-class operation). Pass empty lists / None to clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Sequence


# ────────────────────────────────────────────────────────────────────────────
# MarkerKind + MarkerCfg
# ────────────────────────────────────────────────────────────────────────────


class MarkerKind(Enum):
    """Supported primitive shapes. Mirrors `isaaclab.sim.spawners` shape set."""
    SPHERE = auto()
    CUBOID = auto()
    CONE = auto()
    CYLINDER = auto()
    COORDINATE_FRAME = auto()
    ARROW_X = auto()
    ARROW_Y = auto()
    ARROW_Z = auto()


@dataclass
class MarkerCfg:
    """One named marker prim config.

    Per-instance state (translation / orientation / index) lives on the
    `VisualizationMarkers` runtime — this struct only holds the
    static geometry config.

    Per-kind interpretation of geometry fields:
      SPHERE        — `radius` (default 0.05). `scale` overrides.
      CUBOID        — `size` 3-tuple (X, Y, Z extents). `scale` overrides.
      CONE          — `radius` (base) + `height`. `scale` overrides.
      CYLINDER      — `radius` + `height`. `scale` overrides.
      COORDINATE_FRAME — `axis_length` for the three RGB axes.
      ARROW_*       — `shaft_radius` + `shaft_length` + `head_radius` +
                       `head_length`.
    """
    kind: MarkerKind = MarkerKind.SPHERE
    color: tuple = (1.0, 1.0, 1.0)
    # Generic per-instance scale (multiplied with geometry fields below).
    scale: tuple = (1.0, 1.0, 1.0)
    # Per-kind geometry fields (only the relevant ones are read per kind).
    radius: float = 0.05
    height: float = 0.1
    size: tuple = (0.05, 0.05, 0.05)
    axis_length: float = 0.1
    shaft_radius: float = 0.01
    shaft_length: float = 0.05
    head_radius: float = 0.03
    head_length: float = 0.04


# ────────────────────────────────────────────────────────────────────────────
# VisualizationMarkersCfg + VisualizationMarkers
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class VisualizationMarkersCfg:
    """Mirror of `isaaclab.markers.VisualizationMarkersCfg`.

    `markers` maps a NAME to its MarkerCfg. Each marker name becomes an
    index in marker_indices passed to `visualize()` — name order is the
    insertion order of the dict.

    `max_count` caps how many marker instances can be buffered in one
    `visualize()` call (default 4096); larger calls raise ValueError.
    """
    prim_path: str = ""
    markers: Dict[str, MarkerCfg] = field(default_factory=dict)
    max_count: int = 4096


@dataclass
class _MarkerInstance:
    """One in-buffer marker placement (read by renderer subscribers)."""
    name: str
    kind: MarkerKind
    color: tuple
    position: tuple
    orientation: tuple        # (x, y, z, w) quaternion
    scale: tuple
    marker_index: int
    extras: Dict[str, Any] = field(default_factory=dict)


class VisualizationMarkers:
    """Per-instance marker state recorder.

    `visualize(translations, orientations, marker_indices, scales=None,
               extras=None)` REPLACES the buffer; subsequent reads via
    `get_state()` see only the most recent call.

    `marker_indices[i]` selects which named marker cfg to use for instance
    i (defaults to 0 = first defined marker when None). Per-instance scale
    overrides the marker-cfg `scale` when supplied.
    """

    def __init__(self, cfg: VisualizationMarkersCfg):
        if not cfg.markers:
            raise ValueError("VisualizationMarkersCfg.markers must be non-empty")
        self.cfg = cfg
        # Preserve insertion order so int indices map to names predictably.
        self._marker_names: List[str] = list(cfg.markers.keys())
        self._marker_cfgs: List[MarkerCfg] = list(cfg.markers.values())
        self._buffer: List[_MarkerInstance] = []
        # Optional callback so a renderer can subscribe to "new buffer set".
        self._on_buffer_set: Optional[Any] = None

    # ── public Isaac Lab API ─────────────────────────────────────────────

    def visualize(
        self,
        translations: Sequence[tuple],
        orientations: Optional[Sequence[tuple]] = None,
        marker_indices: Optional[Sequence[int]] = None,
        scales: Optional[Sequence[tuple]] = None,
        extras: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> None:
        """Replace the marker buffer with one instance per row of input.

        - `translations[i]` — world-frame (x, y, z) for instance i
        - `orientations[i]` — (x, y, z, w) quaternion; identity if omitted
        - `marker_indices[i]` — int index into `cfg.markers` (insertion order);
                                defaults to 0 when omitted
        - `scales[i]` — per-instance scale tuple (overrides marker-cfg scale)
        - `extras[i]` — free-form per-instance dict (e.g. {"label": "L_foot"})
        """
        n = len(translations)
        if n > self.cfg.max_count:
            raise ValueError(
                f"visualize() with {n} markers exceeds max_count={self.cfg.max_count}"
            )

        if orientations is None:
            orientations = [(0.0, 0.0, 0.0, 1.0)] * n
        if marker_indices is None:
            marker_indices = [0] * n
        if scales is None:
            scales = [None] * n
        if extras is None:
            extras = [None] * n

        if not (len(orientations) == n == len(marker_indices) == len(scales) == len(extras)):
            raise ValueError(
                f"input length mismatch: translations={n}, orientations="
                f"{len(orientations)}, marker_indices={len(marker_indices)}, "
                f"scales={len(scales)}, extras={len(extras)}"
            )

        new_buffer: List[_MarkerInstance] = []
        for i in range(n):
            idx = marker_indices[i]
            if not (0 <= idx < len(self._marker_cfgs)):
                raise IndexError(
                    f"marker_indices[{i}]={idx} out of range; have "
                    f"{len(self._marker_cfgs)} marker(s)"
                )
            mcfg = self._marker_cfgs[idx]
            inst_scale = tuple(scales[i]) if scales[i] is not None else mcfg.scale
            new_buffer.append(_MarkerInstance(
                name=self._marker_names[idx],
                kind=mcfg.kind,
                color=mcfg.color,
                position=tuple(translations[i]),
                orientation=tuple(orientations[i]),
                scale=inst_scale,
                marker_index=idx,
                extras=dict(extras[i]) if extras[i] is not None else {},
            ))
        self._buffer = new_buffer
        if self._on_buffer_set is not None:
            self._on_buffer_set(new_buffer)

    def clear_visualizations(self) -> None:
        """Drop all marker instances (next get_state() returns [])."""
        self._buffer = []
        if self._on_buffer_set is not None:
            self._on_buffer_set(self._buffer)

    # ── state accessors (renderer subscribers) ───────────────────────────

    def get_state(self) -> List[Dict[str, Any]]:
        """Returns the current buffer as a list of plain dicts (safe to
        serialize / send to a separate renderer process).

        Each entry: {name, kind, color, position, orientation, scale,
                     marker_index, extras}.
        """
        return [
            {
                "name": inst.name,
                "kind": inst.kind.name,  # str for serialization
                "color": inst.color,
                "position": inst.position,
                "orientation": inst.orientation,
                "scale": inst.scale,
                "marker_index": inst.marker_index,
                "extras": dict(inst.extras),
            }
            for inst in self._buffer
        ]

    def get_marker_state(self, name: str) -> List[Dict[str, Any]]:
        """All instances currently buffered under the named marker cfg."""
        return [s for s in self.get_state() if s["name"] == name]

    def set_buffer_callback(self, callback) -> None:
        """Register a `callback(buffer_list)` fired after every visualize()
        call. Useful for piping into a viewport renderer or for tests.
        """
        self._on_buffer_set = callback

    # ── introspection ────────────────────────────────────────────────────

    @property
    def marker_names(self) -> List[str]:
        return list(self._marker_names)

    def num_markers(self) -> int:
        """Number of NAMED marker cfgs (NOT the number of buffered instances)."""
        return len(self._marker_cfgs)

    def num_instances(self) -> int:
        """Number of currently buffered marker instances."""
        return len(self._buffer)

    def get_marker_cfg(self, name: str) -> MarkerCfg:
        """Returns the MarkerCfg for the named marker."""
        if name not in self.cfg.markers:
            raise KeyError(
                f"marker '{name}' not in cfg; have: {self._marker_names}"
            )
        return self.cfg.markers[name]
