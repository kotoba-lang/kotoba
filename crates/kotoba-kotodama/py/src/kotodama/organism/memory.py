import hashlib
import uuid
from typing import Iterable, Optional, Protocol

from kotodama.organism.observation import Observation


class MemoryPersistence(Protocol):
    """Protocol for the memory tier system (warm/cold).
    Ref: ADR-2605266400 (hot/warm/cold layers).
    """

    def warm_flush(self, observations: Iterable[Observation]) -> list[str]:
        """Flush a batch of observations to the warm layer, returning their CIDs."""
        ...

    def warm_lookup(self, actor_did: str, kind: Optional[str], n: int) -> list[Observation]:
        """Look up the most recent n observations from the warm layer."""
        ...

    def cold_archive(self, cids: list[str]) -> str:
        """Archive a set of warm CIDs to the cold layer (IPFS dataset)."""
        ...


class KotobaKqeMemory:
    """Stub implementation of MemoryPersistence for R1.0.
    In-memory dict/list for mocking the actual KQE binding (which comes in R1.1).
    Maintains provenance hash chain for L4 adversarial invariant (ADR-2605266700).
    """

    def __init__(self) -> None:
        # Store tuples of (cid, observation, provenance_hash)
        self._warm_store: list[tuple[str, Observation, str]] = []
        self._last_provenance_hash = "genesis"

    @property
    def current_provenance_hash(self) -> str:
        return self._last_provenance_hash

    def warm_flush(self, observations: Iterable[Observation]) -> list[str]:
        cids = []
        for obs in observations:
            # Generate a mock CID (using uuid for uniqueness in the stub)
            cid = f"bafyreq{uuid.uuid4().hex[:24]}"

            # Update provenance chain (hash of prev_hash + cid + createdAt)
            hasher = hashlib.sha256()
            hasher.update(self._last_provenance_hash.encode())
            hasher.update(cid.encode())
            hasher.update(str(obs.createdAt).encode())

            new_hash = hasher.hexdigest()
            self._last_provenance_hash = new_hash

            self._warm_store.append((cid, obs, new_hash))
            cids.append(cid)

        return cids

    def warm_lookup(self, actor_did: str, kind: Optional[str], n: int) -> list[Observation]:
        results: list[Observation] = []
        # Search backwards for most recent
        for _, obs, _ in reversed(self._warm_store):
            if obs.actorDid == actor_did and (kind is None or obs.kind == kind):
                results.append(obs)
                if len(results) == n:
                    break
        return results

    def cold_archive(self, cids: list[str]) -> str:
        return f"bafyarchive{uuid.uuid4().hex[:20]}"
