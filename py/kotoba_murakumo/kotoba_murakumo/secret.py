"""Secret — env-backed key lookup.

R0: reads from process env. R1: encrypted Vault entries gated on caller DID
(kotoba-signal + kotoba-auth CACAO chain).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Secret:
    values: dict[str, str]

    @classmethod
    def from_name(cls, name: str, *, env_keys: list[str] | None = None) -> "Secret":
        """Modal semantics: a 'named secret' is a bundle of env entries.

        R0: ``env_keys`` lists the env vars to pull. If omitted, only the
        env var named ``name`` is loaded.
        """
        keys = env_keys or [name]
        return cls(values={k: os.environ.get(k, "") for k in keys})

    @classmethod
    def from_dict(cls, mapping: dict[str, str]) -> "Secret":
        return cls(values=dict(mapping))

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)
