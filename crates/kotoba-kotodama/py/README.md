# kotodama

Python runtime SDK for mitama reactive agents (Mode A per [ADR-0049](../../../90-docs/adr/0049-python-udf-shared-pool-runtime.md)).

Counterpart to `@etzhayyim/kotoba-kotodama-host-sdk` (TS, used by CF Worker Mode B / interactive actors).

## Topology

- Runs as a **shared stateless UDF pool** on Vultr VKE (`mitama-udf-pool`, ADR-0048 cluster `a61d513b-...`).
- Each pod hosts a single Python process that registers every Mode A actor's `@udf` handlers in one NSID-keyed table and binds arrow-flight on `:8815`.
- Horizontal scale = replicas (HPA 2-10, see `50-infra/vultr/mitama-udf-pool/`).
- Handlers are stateless per call. State lives in RisingWave via `kotodama.db`.

## Contract layer

**WIT bindgen is retired** (ADR-0049 §M1). AT Lexicon JSON at `00-contracts/lexicons/**/*.json` is the surviving contract. Python types are generated into `kotodama.generated.*` via `etzhayyim lexicon-gen py` (to be implemented).

## Quick start

```bash
cd 20-actors/kotoba-kotodama/py
pip install -e '.[dev]'
python -m kotodama.server    # binds :8815 arrow-flight, :9090 prometheus
```

## Writing a handler

```python
from kotodama import udf

@udf(
    nsid="com.etzhayyim.apps.yabai.classify",
    io_threads=100,
    agent_tool="Classify an email for BEC/phishing signals",
)
async def classify(subject: str, body: str) -> int:
    # Access the shared asyncpg pool via kotodama.context.Context when
    # invoked through the server. For direct unit tests, import db.get_pool().
    return compute_score(subject, body)
```

Add the module to `kotodama/handlers/__init__.py` so it is imported at boot.

## Files

| Module | Role |
|---|---|
| `kotodama.registry` | `@udf` decorator + NSID handler table |
| `kotodama.server` | arrow-flight UdfServer bootstrap + signal handling + metrics |
| `kotodama.context` | per-invocation `Context` (db / pds / auth / logger) |
| `kotodama.db` | asyncpg pool to RisingWave (Kysely-mirror writes) |
| `kotodama.pds` | atproto XRPC client (sdk.pds.dispatch equivalent) |
| `kotodama.saver` | LangGraph `KyselyMirrorSaver` (no SELECT FOR UPDATE) |
| `kotodama.handlers.*` | per-actor handler modules; Phase B pilot: bpmn + playwright |

## See also

- [ADR-0049 Python UDF shared pool runtime](../../../90-docs/adr/0049-python-udf-shared-pool-runtime.md)
- [ADR-0044 RisingWave UDF language strategy](../../../90-docs/adr/0044-risingwave-udf-language-strategy.md)
- [ADR-0047 per-actor Worker collapse to PDS](../../../90-docs/adr/0047-per-actor-worker-collapse-to-pds.md)
- [ADR-0048 RisingWave Vultr + B2 primary](../../../90-docs/adr/0048-risingwave-vultr-b2-primary.md)
