# @etzhayyim/sdk-mock

In-memory mock implementation of the `@etzhayyim/sdk` for testing kotoba reference implementations (e.g., open-banking, hanrei, open-denki) without requiring PDS, IPFS, or Base L2 infrastructure.

Provides a `MockEtzhayyim` class that simulates the core read/write APIs:
- `write<T>({ collection, record, rkey })` — persist record and return AT URI
- `read<T>({ collection, rkey? })` — fetch single record or list with pagination (cursor + limit)
- Test helpers: `dump()`, `count()`, `clear()`

Records are stored in-memory, ordered by insertion sequence (TID-like), and support cursor-based pagination. Idempotent writes on the same `collection + rkey` overwrite the previous value.

## Example

```ts
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import { createAccount, transfer } from "@etzhayyim/open-banking-kotoba";

const mock = new MockEtzhayyim({ did: "did:web:test.etzhayyim.com" });

await createAccount(mock, {
  accountId: "alice",
  ownerDid: "did:plc:alice",
  kind: "checking",
  currency: "USDC",
});

const allRecords = mock.dump("com.etzhayyim.apps.openBanking.account");
console.log(allRecords.length); // 1
```
