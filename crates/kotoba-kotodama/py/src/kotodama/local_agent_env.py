"""Environment loading helpers for local agent CLIs."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


def repo_root_from_py_dir() -> Path:
    return Path(__file__).resolve().parents[5]


def default_env_file() -> Path:
    return repo_root_from_py_dir() / "ops" / "local-agent" / "agent-daemon.env"


def load_env_file(path: str | os.PathLike[str] | None = None, *, override: bool = True) -> Path | None:
    env_path = Path(path or os.environ.get("AGENT_DAEMON_ENV_FILE") or default_env_file())
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        parsed = shlex.split(value, comments=False, posix=True)
        env_value = parsed[0] if parsed else ""
        if override or key not in os.environ:
            os.environ[key] = env_value
    os.environ.setdefault("AGENT_DAEMON_ENV_FILE", str(env_path))
    return env_path


def load_keychain_secret(*, service: str, account: str) -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
