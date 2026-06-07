"""SQLMesh project config for RisingWave MV management (ADR-2605080500).

SQLMesh manages materialized view (MV) SQL definitions as version-controlled
models.  It replaces the Kysely TypeScript migration pattern for MVs, providing:

- **Lineage graph** — which MVs depend on which source tables / other MVs
- **Schema drift detection** — detect when deployed MV SQL diverges from definition
- **Migration plan** — generate DDL diff between current state and target state

Deployment note
---------------
SQLMesh does NOT directly execute ``CREATE MATERIALIZED VIEW`` on RisingWave for
streaming MVs (RW streaming MVs are not ``CREATE TABLE AS SELECT``).  Instead,
SQLMesh generates the migration SQL that is then reviewed and applied through the
RisingWave DDL channel (same flow as existing graph-schema migrations).

See ADR-2605080500 for the Kysely → SQLMesh migration path.

Usage
-----
::

    # Plan (shows what would change)
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
    sqlmesh plan --gateway risingwave

    # Generate SQL only (for review before applying)
    sqlmesh plan --gateway risingwave --no-prompts --forward-only

    # Audit defined models
    sqlmesh audit --gateway risingwave

    # Lineage graph for a specific model
    sqlmesh dag mv_actor_social_stats
"""

from __future__ import annotations

import os

from sqlmesh.core.config import (  # type: ignore[import-untyped]
    Config,
    GatewayConfig,
    ModelDefaultsConfig,
)

try:
    from sqlmesh.integrations.dbt import DbtIntegration  # noqa: F401 — optional
except ImportError:
    pass

try:
    from sqlmesh.core.config.connection import PostgresConnectionConfig
except ImportError:  # fallback import path changed between sqlmesh versions
    from sqlmesh.core.config import PostgresConnectionConfig  # type: ignore[no-redef]


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _rw_host() -> str:
    """Parse host from RW_URL or fall back to individual env vars."""
    url = _env("RW_URL")
    if url:
        # postgresql://user:pass@host:port/db
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname or "localhost"
        except Exception:
            pass
    return _env("RW_HOST", "localhost")


def _rw_port() -> int:
    url = _env("RW_URL")
    if url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.port or 4566
        except Exception:
            pass
    return int(_env("RW_PORT", "4566"))


def _rw_user() -> str:
    url = _env("RW_URL")
    if url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.username or "root"
        except Exception:
            pass
    return _env("RW_USER", "root")


def _rw_password() -> str:
    url = _env("RW_URL")
    if url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.password or ""
        except Exception:
            pass
    return _env("RW_PASSWORD", "")


def _rw_database() -> str:
    url = _env("RW_URL")
    if url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return (parsed.path or "/dev").lstrip("/") or "dev"
        except Exception:
            pass
    return _env("RW_DATABASE", "dev")


config = Config(
    gateways={
        "risingwave": GatewayConfig(
            connection=PostgresConnectionConfig(
                host=_rw_host(),
                port=_rw_port(),
                user=_rw_user(),
                password=_rw_password(),
                database=_rw_database(),
            ),
        ),
        # Local DuckDB gateway for fast lineage / audit checks without a live RW.
        "local": GatewayConfig(
            connection={
                "type": "duckdb",
                "database": ":memory:",
            },
        ),
    },
    default_gateway="risingwave",
    model_defaults=ModelDefaultsConfig(
        dialect="postgres",  # RisingWave is PostgreSQL-wire-compatible
        start="2026-01-01",  # earliest snapshot date for time-partitioned models
    ),
    # State table for SQLMesh metadata lives in the _sqlmesh schema.
    # This is separate from vertex_*/edge_*/mv_* (Kysely scope).
    state_connection=PostgresConnectionConfig(
        host=_rw_host(),
        port=_rw_port(),
        user=_rw_user(),
        password=_rw_password(),
        database=_rw_database(),
        schema_="_sqlmesh",
    ),
    format={"normalize": True},
)
