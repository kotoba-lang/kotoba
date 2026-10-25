# filecoin-cas

cljk adapter to Filecoin Onchain Cloud (Synapse SDK + Filecoin Pay), meant to be
the cold, verifiable archive tier under murakumo's artifact CAS and
yataverse-distribution's lake CAR export. No Python, no TS sidecar: cljk runs on
nbb/kbb, which `require`s the npm SDK directly.

## Status

- Stage 1: `filecoin-cas.synapse` and a calibration round trip.
- Stage 2: CID verification, cid to pieceCid index, persistent retry queue,
  and `fetch` by CID, with unit tests and a calibration smoke test.
- Stage 3 (this state): a loopback HTTP service (`server.cljk`, `bin/`) with a
  background drainer, and murakumo's `murakumo.filecoin-tier` client. Verified
  end to end against Filecoin calibration.
- Streaming: PUT, upload and GET go through the disk, so memory no longer scales
  with object size (see "Things to know" for measurements).
- Stage 4: yataverse-distribution archives lake CARs through the service
  (`deploy/filecoin_archive.cljk` there): archive with a receipt, restore with
  sha-256 verification. Verified on calibration up to 520 MiB.
- Not yet: batching many small objects into one piece, mainnet, any scheduled
  archiving.

## Layout

- `src/filecoin_cas/synapse.cljk` is the only JS-interop boundary to Synapse
  (viem, bigint). All functions return promises; ids/amounts are strings.
- `src/filecoin_cas/cid.cljk` verifies bytes against a `baf...` CIDv1 (raw or
  dag-cbor), the same rule as murakumo.artifact-store, and installs the host
  SHA-256 (the cljs default is far slower).
- `src/filecoin_cas/index.cljk` is the pure state: queued/stored objects, the
  cid to pieceCid map, capped exponential backoff. No I/O, no clock.
- `src/filecoin_cas/state.cljk` persists it: `index.edn` (atomic write) and a
  `spool/<cid>` file per object awaiting upload.
- `src/filecoin_cas/engine.cljk` ties them together with injected transport:
  `open`, `enqueue!` (sync, verifies, spools), `drain!` (uploads due objects),
  `fetch` (spool first, else download; always re-verified against the CID).
- `src/filecoin_cas/server.cljk` is the HTTP front and the drainer (see
  Service below); `bin/filecoin-cas-server.cljk` runs it from environment.
- `scripts/roundtrip.cljk` (stage 1) and `scripts/cas_smoke.cljk` (stage 2) are
  the network acceptance checks. Unit tests: `test/`.

## Run

```sh
npm install
kbb --backend sci run-tests.cljk                    # unit tests, no network
kbb --backend sci scripts/roundtrip.cljk --fund     # first run: claim testnet FIL/USDFC
kbb --backend sci scripts/roundtrip.cljk --bytes 1048576
kbb --backend sci scripts/cas_smoke.cljk            # engine end to end, incl. a restart
# from ../murakumo: real curl client against a real sidecar
MURAKUMO_FILECOIN_E2E=memory      kbb -M:test -n murakumo.filecoin-tier-e2e-test
MURAKUMO_FILECOIN_E2E=calibration kbb -M:test -n murakumo.filecoin-tier-e2e-test
```

`roundtrip` uploads random bytes on the calibration testnet and compares
sha-256 after download. `cas_smoke` does the same through the engine with a
real CIDv1: enqueue, drain, reopen from disk, fetch by CID.

## Service

```sh
FILECOIN_CAS_KEY_FILE=~/.filecoin-cas/calibration.key \
  kbb --backend sci bin/filecoin-cas-server.cljk      # http://127.0.0.1:8788
```

| Variable | Meaning |
|---|---|
| `FILECOIN_CAS_CHAIN` | `calibration` (default) or `mainnet` |
| `FILECOIN_CAS_ALLOW_MAINNET` | must be `1` for mainnet (real funds) |
| `FILECOIN_CAS_KEY_FILE` | 0x-hex private key; refused unless mode 0600 |
| `FILECOIN_CAS_STATE_DIR` | default `~/.filecoin-cas/state-<chain>` |
| `FILECOIN_CAS_HOST` / `_PORT` | default `127.0.0.1` / `8788` |
| `FILECOIN_CAS_TOKEN_FILE` | bearer token (0600); required for a non-loopback host |
| `FILECOIN_CAS_MAX_OBJECT` | bytes, default 536870912; Synapse itself refuses a piece over 1,065,353,216 bytes |

`--memory-network` swaps Filecoin for a local directory (`<state-dir>/memnet`)
that streams files like the real transport (tests and wiring only; nothing is
durable or provable).

API: `PUT /obj/<cid>` (202 queued, 200 already stored, 400/413/422 on bad
input), `GET /obj/<cid>` (re-verified bytes, 404 unknown, 502 unverifiable),
`GET /status/<cid>`, `GET /health`. The drainer runs every 15 s and shortly
after a new object arrives; before each drain it tops up the Filecoin Pay
deposit for what is queued.

murakumo enables the tier by setting `MURAKUMO_FILECOIN_CAS_URL` (and
optionally `MURAKUMO_FILECOIN_CAS_TOKEN_FILE`); unset, nothing changes. The
client is `murakumo.filecoin-tier` in the murakumo repository.

## Keys

The calibration key is a throwaway kept in `.filecoin-cas/calibration.key`
(gitignored, mode 0600) and is never printed. For mainnet, supply a key you
control; never commit it, and prefer a scoped session key over the main key.

## Things to know

- Runtime: everything here needs nbb/kbb (it requires an npm package and uses
  Node APIs). murakumo's `artifact_store.cljk` uses `java.nio`, so wiring the
  tier into it (stage 3) crosses a runtime boundary; decide whether that is a
  cljs port of the store or a process boundary before writing the adapter.
- Bytes are `Uint8Array`. Callers holding a JVM `byte[]` or a vector of ints
  must convert.
- Errors: under nbb an `ex-info` thrown inside a promise callback arrives
  wrapped as `:sci/error` with the original in `ex-cause`. Use
  `filecoin-cas.cid/error-reason` to read `:reason` (`:cid-mismatch`,
  `:spool-corrupt`, `:fetched-bytes-cid-mismatch`, `:no-copies`).
- A crash between a successful upload and saving the index re-uploads that
  object on the next drain: a duplicate piece, never lost data.
- Streaming: objects move through the disk, never through memory. A PUT is
  written to `<state-dir>/spool/.tmp-*` while it is hashed and is renamed into
  place only once the digest matches the CID; an upload streams the spool file to
  the SDK (`upload-file!`, a web stream, PieceCID computed as it passes); a GET
  downloads the stored piece from a stored copy URL into
  `<state-dir>/fetch/.tmp-*`, verifies it against the CID, and only then streams it
  to the client (so unverified bytes are never sent). Interrupted transfers'
  `.tmp-*` files are swept at startup.
- Measured on Filecoin calibration through the yataverse `archive`/`restore` CLI
  (sha-256 identical after the round trip; peak sidecar RSS covers both):

  | object | archive to `stored` | restore | peak RSS |
  |---|---|---|---|
  | 64 MiB | 352 s | 75 s | 370 MiB |
  | 256 MiB | 1148 s | 297 s | 470 MiB |
  | 520 MiB | 2340 s | 629 s | 731 MiB |

  Before streaming the same 64 and 256 MiB runs peaked at 1755 and 4212 MiB, and
  520 MiB did not finish. Time is dominated by the storage providers (upload,
  on-chain commit), not by this service. RSS still creeps up with size (about
  1.4x from 256 to 520 MiB); it is not flat, and larger objects were not measured.
- Disk, not RAM, is now the resource: budget roughly the object size in the spool
  while it waits, plus the object size per concurrent GET of an object that is no
  longer spooled.
- A PUT for a CID the tier already holds is answered 200/202 without reading the
  body: the object is identified by its CID and what is stored was verified when
  it arrived.
- One object is one piece today, which is wasteful for small objects; batching
  belongs to the archive step (stage 3/4).
- Synapse keys pieces by PieceCID (CommP), not `baf…` CIDv1. `index.edn` holds
  the cid to pieceCid map (the source CID is also stored as piece metadata so
  the index can be rebuilt); the SDK only verifies bytes against the PieceCID,
  which is why `fetch` re-verifies against the CID.
- The SDK stores 2 copies on 2 providers by default. 1 MiB required a
  ~1.24 USDFC deposit (lockup) on calibration.
- Deposit with runway. `prepare!` defaults to 30 days of slack
  (`default-runway-epochs`). Depositing only the bare lockup leaves
  `availableFunds` at 0, the account cannot settle, and the second upload to an
  existing dataset fails with `LockupNotSettledRateChangeNotAllowed`.
- A calibration upload takes minutes end to end (2 copies, on-chain commit);
  the SDK rejection path can also be slow, so give scripts a generous timeout.
- Data stored on Filecoin is publicly readable and not deletable: encrypt
  before upload anything sensitive.
- The faucet returns before its transactions are indexed; poll the balance
  rather than waiting on a receipt.

## License

Apache License 2.0 (see `LICENSE`), the same as the other kotoba-lang libraries.
