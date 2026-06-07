"""AppLauncher + SimulationApp + AppLauncherArgs.

Wraps the standard Isaac Lab CLI args + a mock simulation-app handle.
In upstream Isaac Lab the launcher boots Omniverse Kit (heavy native
process) and the returned `simulation_app` is the actual Kit handle.
In nv_compat the launcher does no heavy lifting — it parses args,
records them, and returns a SimulationApp shim with the standard
.update() / .close() / .is_running() methods that scripts call.

Side-effect: when `args.task` is set and a corresponding task is
registered (iter 46 task_registry), AppLauncher records it on .task_id
for downstream callers to look up via the registry.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ────────────────────────────────────────────────────────────────────────────
# AppLauncherArgs — typed view of standard CLI args
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class AppLauncherArgs:
    """Typed dataclass mirror of the standard Isaac Lab CLI args.

    Construct from argparse Namespace via `AppLauncherArgs(**vars(args_cli))`.
    Extra fields in args_cli (e.g. task-specific --my_arg) are stored under
    `extras` to preserve them.
    """
    # Common Isaac Lab CLI args.
    task: str = ""
    num_envs: int = 1
    seed: Optional[int] = None
    device: str = "cuda:0"
    headless: bool = False
    video: bool = False
    video_length: int = 200
    video_interval: int = 2000
    enable_cameras: bool = False
    livestream: int = -1                # -1 = disabled
    experience: str = ""                # path to Kit experience file
    kit_args: List[str] = field(default_factory=list)
    # use_fabric is the Isaac Sim GPU-pipeline flag (mirrored on env cfgs)
    use_fabric: bool = True
    # Extras: anything else from the parser (task-specific args).
    extras: dict = field(default_factory=dict)

    @classmethod
    def from_namespace(cls, ns: Any) -> "AppLauncherArgs":
        """Construct from an argparse Namespace, partitioning standard
        fields vs extras."""
        d = dict(vars(ns)) if hasattr(ns, "__dict__") else dict(ns)
        standard_keys = {
            "task", "num_envs", "seed", "device", "headless", "video",
            "video_length", "video_interval", "enable_cameras",
            "livestream", "experience", "kit_args", "use_fabric",
        }
        std = {k: v for k, v in d.items() if k in standard_keys}
        extras = {k: v for k, v in d.items() if k not in standard_keys}
        return cls(**std, extras=extras)


# ────────────────────────────────────────────────────────────────────────────
# SimulationApp — mock handle
# ────────────────────────────────────────────────────────────────────────────


class SimulationApp:
    """Mock Omniverse Kit SimulationApp handle.

    In upstream Isaac Lab this is the real Kit process handle returned by
    `omni.isaac.kit.SimulationApp`. nv_compat is a non-rendering substrate
    so we provide a lightweight stub with the API parity scripts expect:

      - is_running() → bool
      - update()      — per-step hook (host wires real render here)
      - close()       — sentinel that marks the app as exited
      - context["headless" / "device" / …] — read-only cfg map

    Once close() is called, is_running() returns False forever (matches
    upstream behavior).
    """

    def __init__(self, context: dict):
        self._context = dict(context)
        self._is_running: bool = True

    def is_running(self) -> bool:
        return self._is_running

    def update(self) -> None:
        """Per-step update hook. No-op in nv_compat."""
        pass

    def close(self) -> None:
        self._is_running = False

    @property
    def context(self) -> dict:
        return dict(self._context)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ────────────────────────────────────────────────────────────────────────────
# AppLauncher
# ────────────────────────────────────────────────────────────────────────────


class AppLauncher:
    """CLI entry point + simulation-app handle.

    Standard usage:

        parser = argparse.ArgumentParser()
        AppLauncher.add_app_launcher_args(parser)
        args_cli = parser.parse_args()

        launcher = AppLauncher(args_cli)
        sim_app = launcher.app
        # ... run sim ...
        sim_app.close()

    Properties:
        - app           → SimulationApp instance
        - args          → AppLauncherArgs dataclass (typed view)
        - task_id       → str (args.task)
        - num_envs / device / seed / headless / video — convenience accessors
    """

    @staticmethod
    def add_app_launcher_args(parser: argparse.ArgumentParser) -> None:
        """Register the standard Isaac Lab CLI args on `parser`.

        Idempotent — calling twice on the same parser raises argparse's
        ArgumentError (parser's own duplicate detection).
        """
        parser.add_argument(
            "--num_envs", type=int, default=1,
            help="Number of parallel environments (default: 1)",
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Random seed (default: unseeded)",
        )
        parser.add_argument(
            "--device", type=str, default="cuda:0",
            help='Compute device: "cuda:0" / "cpu" / "cuda:1" / ...',
        )
        parser.add_argument(
            "--headless", action="store_true",
            help="Run without rendering (training mode)",
        )
        parser.add_argument(
            "--video", action="store_true",
            help="Record video of the sim",
        )
        parser.add_argument(
            "--video_length", type=int, default=200,
            help="Number of steps per recorded video (default: 200)",
        )
        parser.add_argument(
            "--video_interval", type=int, default=2000,
            help="Steps between video recordings (default: 2000)",
        )
        parser.add_argument(
            "--enable_cameras", action="store_true",
            help="Enable camera sensors (requires non-headless or video)",
        )
        parser.add_argument(
            "--livestream", type=int, default=-1,
            help="Livestream mode (0/1/2, -1 = disabled)",
        )
        parser.add_argument(
            "--experience", type=str, default="",
            help="Path to Kit experience (.kit) file (advanced)",
        )
        parser.add_argument(
            "--kit_args", type=str, default="",
            help="Extra Kit args, space-separated",
        )
        parser.add_argument(
            "--use_fabric", action="store_true", default=True,
            help="Use GPU fabric pipeline (Isaac Sim default: True)",
        )
        parser.add_argument(
            "--no_use_fabric", dest="use_fabric", action="store_false",
            help="Disable GPU fabric (CPU pipeline)",
        )

    def __init__(self, args_cli: Any):
        """Initialize from an argparse Namespace OR an AppLauncherArgs dataclass.

        Auto-detects between the two; constructs the SimulationApp shim
        with a context dict derived from the args.
        """
        if isinstance(args_cli, AppLauncherArgs):
            self.args: AppLauncherArgs = args_cli
        elif hasattr(args_cli, "__dict__") or isinstance(args_cli, dict):
            self.args = AppLauncherArgs.from_namespace(args_cli)
        else:
            raise TypeError(
                f"AppLauncher expects argparse.Namespace or AppLauncherArgs; "
                f"got {type(args_cli).__name__}"
            )
        # Parse kit_args (space-separated → list).
        if isinstance(self.args.kit_args, str) and self.args.kit_args:
            self.args.kit_args = self.args.kit_args.split()
        # Build SimulationApp context dict.
        ctx = {
            "headless": self.args.headless,
            "device": self.args.device,
            "seed": self.args.seed,
            "enable_cameras": self.args.enable_cameras,
            "livestream": self.args.livestream,
            "video": self.args.video,
            "use_fabric": self.args.use_fabric,
        }
        if self.args.experience:
            ctx["experience"] = self.args.experience
        if self.args.kit_args:
            ctx["kit_args"] = list(self.args.kit_args)
        self._app = SimulationApp(ctx)
        # Cache task_id (when present in extras or as top-level).
        self.task_id: str = self.args.task or self.args.extras.get("task", "")

    # ── public accessors (mirror upstream pattern) ──────────────────────

    @property
    def app(self) -> SimulationApp:
        """The wrapped simulation-app handle. Scripts call `app.update()` per
        step + `app.close()` at exit."""
        return self._app

    @property
    def num_envs(self) -> int:
        return self.args.num_envs

    @property
    def seed(self) -> Optional[int]:
        return self.args.seed

    @property
    def device(self) -> str:
        return self.args.device

    @property
    def headless(self) -> bool:
        return self.args.headless

    @property
    def video(self) -> bool:
        return self.args.video

    @property
    def use_fabric(self) -> bool:
        return self.args.use_fabric

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._app.close()
