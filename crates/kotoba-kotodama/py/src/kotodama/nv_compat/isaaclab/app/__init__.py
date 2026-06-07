"""isaaclab.app — CLI entry point + simulation app handle.

Mirror of `isaaclab.app` (Isaac Lab 1.x). The canonical entry point that
every Isaac Lab script uses:

    import argparse
    from kotodama.nv_compat.isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser()
    AppLauncher.add_app_launcher_args(parser)
    parser.add_argument("--task", type=str, default="Isaac-Cartpole-Direct-v0")
    args_cli = parser.parse_args()

    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app
    # ... rest of script reads args_cli.task / num_envs / seed / device / ...

    # Cleanup
    simulation_app.close()

Surface:
  - AppLauncher                 — class + add_app_launcher_args(parser)
                                   + .app property + .close()
  - SimulationApp               — handle returned by .app (mock in
                                   nv_compat; upstream wraps Omniverse Kit)
  - AppLauncherArgs (dataclass) — typed view of the standard CLI args
                                   (use AppLauncherArgs(**vars(args_cli))
                                   for typed access)
"""

from .app_launcher import AppLauncher, AppLauncherArgs, SimulationApp

__all__ = ["AppLauncher", "AppLauncherArgs", "SimulationApp"]
