"""isaaclab.sim.SimulationContext mirror — singleton lifecycle wrapper.

The canonical entry point for every Isaac Lab example: a `with`-context
manager that owns the simulation clock, step counter, and physics + render
callback registries. Pattern:

    cfg = SimulationCfg(physics_dt=1/120, rendering_dt=1/30)
    with SimulationContext(cfg) as sim:
        # Build scene, instantiate envs, register callbacks.
        sim.add_physics_callback("logger", lambda dt: print("tick"))
        sim.reset()
        while sim.is_playing():
            sim.step()              # auto-fires physics + (every N) render
            if sim.get_step_count() >= 1000:
                sim.stop()

`SimulationContext.instance()` returns the currently-active context (or
None outside a `with` block) so downstream code (envs, sensors, viewers)
can find it without having to thread the reference through every layer.

Step pipeline (per `step(render=True)` call):

    1. Validate not-stopped & is-playing (raise if stopped, warn-skip if paused)
    2. step_count += 1; current_time += physics_dt
    3. Fire every registered physics callback with `physics_dt`
    4. If render scheduled (step_count % render_decimation == 0):
       fire every registered render callback with `rendering_dt`

Render decimation = `round(rendering_dt / physics_dt)` clamped to ≥1.
Default cfg (120 Hz physics, 30 Hz rendering) → render every 4 steps.

Pure stdlib. No external sim binding — the context is descriptive, the
actual physics + render are subscriber callbacks the host registers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


# ────────────────────────────────────────────────────────────────────────────
# Cfg + error
# ────────────────────────────────────────────────────────────────────────────


class SimulationCfgError(ValueError):
    """Raised when a SimulationCfg fails validation."""


@dataclass
class SimulationCfg:
    """Mirror of `isaaclab.sim.SimulationCfg` (subset).

    Cross-field invariant: `physics_dt > 0`, `rendering_dt > 0`,
    `rendering_dt >= physics_dt`. Violations raise `SimulationCfgError`
    when passed to `SimulationContext`.
    """
    physics_dt: float = 1.0 / 120.0
    rendering_dt: float = 1.0 / 30.0
    gravity: tuple = (0.0, 0.0, -9.81)
    # Informational fields — the nv_compat context doesn't dispatch to a
    # specific device, but downstream code (envs, sensors) reads them to
    # mirror upstream behaviour ("am I on GPU?" gating).
    device: str = "cpu"
    use_gpu_pipeline: bool = False
    enable_scene_query: bool = False
    # When True, step() does NOT auto-fire render callbacks even at the
    # decimation tick (useful for headless training where only physics
    # matters). Independent of the per-call `render` arg to step().
    disable_rendering: bool = False


# ────────────────────────────────────────────────────────────────────────────
# SimulationContext
# ────────────────────────────────────────────────────────────────────────────


class SimulationContext:
    """Singleton simulation lifecycle wrapper. See module docstring."""

    _instance: Optional["SimulationContext"] = None

    def __init__(self, cfg: Optional[SimulationCfg] = None):
        cfg = cfg if cfg is not None else SimulationCfg()
        # Cfg validation.
        if cfg.physics_dt <= 0.0:
            raise SimulationCfgError(
                f"physics_dt must be positive; got {cfg.physics_dt}"
            )
        if cfg.rendering_dt <= 0.0:
            raise SimulationCfgError(
                f"rendering_dt must be positive; got {cfg.rendering_dt}"
            )
        if cfg.rendering_dt + 1e-12 < cfg.physics_dt:
            raise SimulationCfgError(
                f"rendering_dt ({cfg.rendering_dt}) must be ≥ physics_dt "
                f"({cfg.physics_dt})"
            )
        self.cfg = cfg
        # Render decimation: number of physics steps between render ticks.
        ratio = cfg.rendering_dt / cfg.physics_dt
        self._render_decimation: int = max(1, int(round(ratio)))

        # Step / time state.
        self._step_count: int = 0
        self._current_time: float = 0.0
        self._is_playing: bool = False
        self._is_stopped: bool = False

        # Callback registries.
        self._physics_callbacks: Dict[str, Callable[[float], None]] = {}
        self._render_callbacks: Dict[str, Callable[[float], None]] = {}

        # Camera-view stub (matches Isaac Lab's `set_camera_view` API).
        self._camera_eye: tuple = (1.0, 1.0, 1.0)
        self._camera_target: tuple = (0.0, 0.0, 0.0)

    # ────────────────────────────────────────────────────────────────────
    # Context-manager protocol + singleton lookup
    # ────────────────────────────────────────────────────────────────────

    def __enter__(self) -> "SimulationContext":
        if type(self)._instance is not None:
            raise RuntimeError(
                "another SimulationContext is already active; only one "
                "context may be in scope at a time"
            )
        type(self)._instance = self
        self._is_playing = True
        self._is_stopped = False
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Cleanup callbacks regardless of exception type.
        self._physics_callbacks.clear()
        self._render_callbacks.clear()
        self._is_playing = False
        if type(self)._instance is self:
            type(self)._instance = None

    @classmethod
    def instance(cls) -> Optional["SimulationContext"]:
        """Returns the currently-active SimulationContext, or None if no
        context is in scope."""
        return cls._instance

    # ────────────────────────────────────────────────────────────────────
    # Public Isaac Lab API
    # ────────────────────────────────────────────────────────────────────

    def step(self, render: bool = True) -> None:
        """Advance one physics step. Fires physics callbacks unconditionally;
        fires render callbacks at the render-decimation tick when both
        `render=True` AND `cfg.disable_rendering=False`.

        Raises RuntimeError if the sim is stopped. No-op when paused.
        """
        if self._is_stopped:
            raise RuntimeError("simulation is stopped; reset before stepping")
        if not self._is_playing:
            return  # paused — silent no-op
        self._step_count += 1
        self._current_time += self.cfg.physics_dt
        # Fire physics callbacks (iter snapshot to allow callbacks to
        # add/remove other callbacks safely mid-iter).
        for cb in list(self._physics_callbacks.values()):
            cb(self.cfg.physics_dt)
        if (
            render
            and not self.cfg.disable_rendering
            and self._step_count % self._render_decimation == 0
        ):
            for cb in list(self._render_callbacks.values()):
                cb(self.cfg.rendering_dt)

    def reset(self) -> None:
        """Reset step counter + sim time. Does NOT clear callbacks or
        change the singleton pointer. Re-arms playing state."""
        self._step_count = 0
        self._current_time = 0.0
        self._is_playing = True
        self._is_stopped = False

    def pause(self) -> None:
        """Pause stepping. step() becomes a no-op until resume()."""
        self._is_playing = False

    def resume(self) -> None:
        """Resume stepping after pause(). No-op when stopped (call reset() first)."""
        if not self._is_stopped:
            self._is_playing = True

    def stop(self) -> None:
        """Hard-stop the sim. step() raises until reset() is called."""
        self._is_playing = False
        self._is_stopped = True

    # ── state accessors ──────────────────────────────────────────────────

    def is_playing(self) -> bool:
        return self._is_playing and not self._is_stopped

    def is_stopped(self) -> bool:
        return self._is_stopped

    def get_step_count(self) -> int:
        return self._step_count

    def get_current_time(self) -> float:
        return self._current_time

    def get_physics_dt(self) -> float:
        return self.cfg.physics_dt

    def get_rendering_dt(self) -> float:
        return self.cfg.rendering_dt

    def render_decimation(self) -> int:
        """Number of physics steps per render tick. Cached at ctor."""
        return self._render_decimation

    # ── callback registration ────────────────────────────────────────────

    def add_physics_callback(self, name: str,
                             callback: Callable[[float], None]) -> None:
        """Register a per-physics-step callback. `callback(dt)` is invoked
        with the physics dt on every step(). Names are unique — re-using a
        name replaces the prior callback."""
        self._physics_callbacks[name] = callback

    def remove_physics_callback(self, name: str) -> bool:
        """Returns True if a callback with that name was present + removed."""
        return self._physics_callbacks.pop(name, None) is not None

    def add_render_callback(self, name: str,
                            callback: Callable[[float], None]) -> None:
        """Register a per-render-tick callback. Fires every
        `render_decimation()` physics steps (e.g. every 4 steps at the
        default 120 Hz physics / 30 Hz rendering)."""
        self._render_callbacks[name] = callback

    def remove_render_callback(self, name: str) -> bool:
        return self._render_callbacks.pop(name, None) is not None

    def physics_callback_names(self) -> list:
        return list(self._physics_callbacks.keys())

    def render_callback_names(self) -> list:
        return list(self._render_callbacks.keys())

    # ── camera-view stub ─────────────────────────────────────────────────

    def set_camera_view(self, eye: tuple, target: tuple) -> None:
        """Stub matching `isaaclab.sim.SimulationContext.set_camera_view`.

        Stores the camera pose for downstream viewport code to read; in
        the nv_compat surface the actual viewport is provided by a separate
        renderer (omni.kit.viewport.utility in a future iter).
        """
        self._camera_eye = tuple(eye)
        self._camera_target = tuple(target)

    def get_camera_view(self) -> tuple:
        """Returns (eye, target) tuple — the most recently set camera pose."""
        return (self._camera_eye, self._camera_target)
