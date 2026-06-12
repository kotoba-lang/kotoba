"""isaaclab.utils.timer — perf timing helpers.

Mirror of `isaaclab.utils.timer` (Isaac Lab 1.x). Used widely for
per-step timing budgets, training-loop benchmarks, and module-level
profile aggregation.

Public surface:
  - Timer                       — context-manager / start-stop timer with
                                   total_run_time + last_lap accessors
  - TimerError                  — raised on misuse (stop-before-start, ...)
  - start_timer(name)           — module-level named registry
  - stop_timer(name) → seconds
  - get_timer_elapsed(name)
  - get_timer_total(name)
  - clear_timer(name=None)
  - list_timers() → dict[name, elapsed]
  - time_function(label=None)   — decorator factory: print elapsed on
                                   function exit; counts add to a named
                                   accumulator
  - format_seconds(s)           — pretty "1m23.456s" output

Uses time.perf_counter() (monotonic + highest available resolution).
Pure stdlib.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Dict, Optional


# ────────────────────────────────────────────────────────────────────────────
# TimerError + Timer class
# ────────────────────────────────────────────────────────────────────────────


class TimerError(Exception):
    """Raised when Timer is misused (stop without start, restart without
    stop, query elapsed before any lap, etc.)."""


class Timer:
    """Start-stop wall-clock timer with optional context-manager use.

    Standard usage:

        # Context manager:
        with Timer("forward_pass") as t:
            ...
        print(t.time_elapsed)        # last lap, seconds (float)

        # Explicit start/stop:
        t = Timer("backward_pass")
        t.start()
        ...
        t.stop()
        print(t.time_elapsed)

        # Multi-lap accumulation:
        for _ in range(100):
            t.start()
            ...
            t.stop()
        print(t.total_run_time, t.lap_count)
    """

    def __init__(self, name: str = ""):
        self.name: str = name
        self._start_time: Optional[float] = None
        self._last_lap: float = 0.0
        self._total: float = 0.0
        self._lap_count: int = 0

    # ── lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin (or restart) the timer. Raises TimerError if already running."""
        if self._start_time is not None:
            raise TimerError(
                f"Timer '{self.name}' is already running; call stop() before start()"
            )
        self._start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer; returns the duration of the just-ended lap."""
        if self._start_time is None:
            raise TimerError(
                f"Timer '{self.name}' is not running; call start() before stop()"
            )
        lap = time.perf_counter() - self._start_time
        self._last_lap = lap
        self._total += lap
        self._lap_count += 1
        self._start_time = None
        return lap

    def reset(self) -> None:
        """Reset to zero (clears total + lap count). Raises if running."""
        if self._start_time is not None:
            raise TimerError(
                f"Timer '{self.name}' cannot be reset while running; call stop() first"
            )
        self._last_lap = 0.0
        self._total = 0.0
        self._lap_count = 0

    # ── accessors ────────────────────────────────────────────────────────

    @property
    def time_elapsed(self) -> float:
        """Duration of the most recently completed lap (seconds).

        When the timer is currently running, returns elapsed since start()
        (live read). Raises TimerError if no lap has ever completed AND
        timer is not running.
        """
        if self._start_time is not None:
            return time.perf_counter() - self._start_time
        if self._lap_count == 0:
            raise TimerError(
                f"Timer '{self.name}' has no completed lap; "
                f"call start()+stop() at least once"
            )
        return self._last_lap

    @property
    def total_run_time(self) -> float:
        """Sum of all lap durations (seconds). Excludes the current lap
        if running."""
        return self._total

    @property
    def lap_count(self) -> int:
        return self._lap_count

    @property
    def is_running(self) -> bool:
        return self._start_time is not None

    # ── context-manager protocol ────────────────────────────────────────

    def __enter__(self) -> "Timer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        # Stop even on exception (matches Isaac Lab semantics — measure
        # wall time including failed paths).
        if self.is_running:
            self.stop()

    # ── pretty repr ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return (
            f"Timer(name={self.name!r}, status={status}, "
            f"laps={self._lap_count}, total={format_seconds(self._total)})"
        )


# ────────────────────────────────────────────────────────────────────────────
# Module-level named timer registry
# ────────────────────────────────────────────────────────────────────────────


_TIMERS: Dict[str, Timer] = {}


def start_timer(name: str) -> Timer:
    """Start a named timer (registry-backed). Returns the Timer instance.

    If a timer with this name exists AND is stopped, it resumes (the
    next stop() adds to total_run_time). If it's running, raises
    TimerError.
    """
    if name in _TIMERS:
        _TIMERS[name].start()
        return _TIMERS[name]
    t = Timer(name)
    t.start()
    _TIMERS[name] = t
    return t


def stop_timer(name: str) -> float:
    """Stop the named timer; returns last-lap seconds. Raises KeyError if
    no timer registered under `name`."""
    if name not in _TIMERS:
        raise KeyError(
            f"no timer named '{name}' (registered: {sorted(_TIMERS.keys())})"
        )
    return _TIMERS[name].stop()


def get_timer_elapsed(name: str) -> float:
    """Last-lap elapsed seconds for the named timer.

    Returns 0.0 when no laps have completed (more forgiving than the
    Timer.time_elapsed property — convenient for logging loops that
    print every step even before the first stop)."""
    if name not in _TIMERS:
        raise KeyError(f"no timer named '{name}'")
    t = _TIMERS[name]
    if t.lap_count == 0 and not t.is_running:
        return 0.0
    if t.is_running:
        return time.perf_counter() - t._start_time  # type: ignore[operator]
    return t._last_lap


def get_timer_total(name: str) -> float:
    """Sum of all lap durations for the named timer."""
    if name not in _TIMERS:
        raise KeyError(f"no timer named '{name}'")
    return _TIMERS[name].total_run_time


def clear_timer(name: Optional[str] = None) -> None:
    """Remove the named timer (or all timers when name is None) from the
    registry. Running timers are stopped first to avoid leaks."""
    if name is None:
        for t in _TIMERS.values():
            if t.is_running:
                t.stop()
        _TIMERS.clear()
        return
    if name in _TIMERS:
        if _TIMERS[name].is_running:
            _TIMERS[name].stop()
        del _TIMERS[name]


def list_timers() -> Dict[str, float]:
    """Returns {name: total_run_time} snapshot of every registered timer."""
    return {name: t.total_run_time for name, t in _TIMERS.items()}


def get_timer(name: str) -> Timer:
    """Return the registered Timer instance, or KeyError on miss."""
    if name not in _TIMERS:
        raise KeyError(f"no timer named '{name}'")
    return _TIMERS[name]


# ────────────────────────────────────────────────────────────────────────────
# Decorator
# ────────────────────────────────────────────────────────────────────────────


def time_function(label: Optional[str] = None,
                  print_each_call: bool = False) -> Callable:
    """Decorator: time every call to a function and accumulate into a
    named registry timer.

    Usage:

        @time_function("compute_advantages")
        def gae(rewards, values, dones): ...

        for _ in range(100):
            gae(...)

        print(get_timer_total("compute_advantages"))   # sum over 100 calls

    `label` defaults to the function's `__qualname__` when omitted.
    `print_each_call=True` prints per-call elapsed (debug; default False
    to avoid noise in training loops).
    """
    def decorator(fn: Callable) -> Callable:
        timer_name = label or getattr(fn, "__qualname__", fn.__name__)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Use a fresh Timer for this call; merge into the registry
            # accumulator on stop.
            if timer_name not in _TIMERS:
                _TIMERS[timer_name] = Timer(timer_name)
            t = _TIMERS[timer_name]
            t.start()
            try:
                return fn(*args, **kwargs)
            finally:
                lap = t.stop()
                if print_each_call:
                    print(f"[{timer_name}] {format_seconds(lap)}")

        return wrapper

    return decorator


# ────────────────────────────────────────────────────────────────────────────
# format_seconds
# ────────────────────────────────────────────────────────────────────────────


def format_seconds(seconds: float) -> str:
    """Format a duration in seconds as `"<H>h<M>m<S>.<ms>s"`.

    Examples:
      0.000234 → "234.0µs"
      0.123    → "123.0ms"
      5.678    → "5.678s"
      125.0    → "2m5.000s"
      3725.0   → "1h2m5.000s"
    """
    if seconds < 0:
        return "-" + format_seconds(-seconds)
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f}µs"   # µ
    if seconds < 1.0:
        return f"{seconds * 1e3:.1f}ms"
    if seconds < 60.0:
        return f"{seconds:.3f}s"
    if seconds < 3600.0:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}m{s:.3f}s"
    h = int(seconds // 3600)
    rem = seconds - h * 3600
    m = int(rem // 60)
    s = rem - m * 60
    return f"{h}h{m}m{s:.3f}s"
