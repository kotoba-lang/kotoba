"""
arrow-udf UdfServer bootstrap for the mitama shared pool.

Called once per pod startup. Reads the handler registry (populated by
`@udf` decorators in `kotodama.handlers.*`) and binds gRPC/arrow-flight
on `:8815`, Prometheus metrics on `:9090`.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from typing import Any

try:
    from arrow_udf import UdfServer
except ImportError:  # pragma: no cover
    UdfServer = None  # type: ignore[assignment,misc]

try:
    from prometheus_client import Counter, Gauge, start_http_server
except ImportError:  # pragma: no cover
    Counter = Gauge = None  # type: ignore[assignment,misc]
    start_http_server = None  # type: ignore[assignment]

from kotodama.registry import registered

log = logging.getLogger(__name__)

UDF_HOST = os.environ.get("UDF_HOST", "0.0.0.0")
UDF_PORT = int(os.environ.get("UDF_PORT", "8815"))
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9090"))


def serve(
    host: str = UDF_HOST,
    port: int = UDF_PORT,
    metrics_port: int = METRICS_PORT,
    preload: list[str] | None = None,
) -> None:
    """
    Bind the arrow-flight UDF server and block.

    `preload` is a list of module paths to import before serving so their
    `@udf` decorators register handlers. In production, the list is
    generated from `kotodama.handlers.__init__.py` which eagerly imports
    every actor module.
    """
    if UdfServer is None:
        raise RuntimeError(
            "arrow-udf not installed — `pip install arrow-udf` or use the "
            "production container image."
        )

    # Allow the caller to inject preloads (tests) but default to the full
    # handler package.
    if preload is None:
        import kotodama.handlers  # noqa: F401 — side-effect: register handlers
    else:
        import importlib

        for mod in preload:
            importlib.import_module(mod)

    entries = registered()
    if not entries:
        log.warning("no @udf handlers registered; serving empty pool")

    # arrow_udf.UdfServer prepends "grpc://" itself; pass bare host:port.
    # arrow_udf.UdfServer prepends "grpc://" itself; pass bare host:port.
    server = UdfServer(location=f"{host}:{port}")
    # arrow_udf.UdfServer.add_function takes a single decorated callable
    # whose `_name` attribute was set by the @udf decorator in
    # kotodama.registry (name=nsid). The NSID becomes the remote_udf name.
    for _nsid, entry in entries.items():
        server.add_function(entry.fn)

    # Prometheus scrape endpoint.
    if start_http_server and Gauge:
        start_http_server(metrics_port)
        g = Gauge("kotodama_handlers_registered", "Count of registered NSIDs")
        g.set(len(entries))
        log.info("metrics endpoint on :%d", metrics_port)

    # Signal handling — SIGTERM from kubelet on pod eviction.
    stopped = threading.Event()

    def _shutdown(signum: int, _frame: Any) -> None:
        log.info("received signal %d, shutting down", signum)
        stopped.set()
        try:
            server.stop()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info(
        "kotodama serving arrow-flight on %s:%d with %d handlers",
        host,
        port,
        len(entries),
    )
    server.serve()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    serve()
