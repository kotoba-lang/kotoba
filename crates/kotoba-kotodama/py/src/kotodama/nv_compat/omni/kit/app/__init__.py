"""omni.kit.app — Application + IExt + extension lifecycle.

Mirrors `omni.kit.app` (Omniverse Kit 105+) at the public API level.
The Application instance is the singleton that owns all loaded extensions
and dispatches lifecycle events (startup / shutdown). Each extension is a
subclass of IExt registered with the Application.

Standard usage:

    from kotodama.nv_compat.omni.kit.app import get_app, IExt

    class MyExtension(IExt):
        def on_startup(self, ext_id):
            print(f"started: {ext_id}")
        def on_shutdown(self):
            print("stopping")

    app = get_app()
    app.register_extension("my.ext", MyExtension())
    app.startup_all()
    # ... do work ...
    app.shutdown_all()
"""

from .application import Application, get_app, reset_app
from .extension import ExtensionToml, IExt, parse_extension_toml

__all__ = [
    "Application", "get_app", "reset_app",
    "IExt", "ExtensionToml", "parse_extension_toml",
]
