# ADR-2607201300: Kotoba Torrent macOS application

- Status: accepted, bounded prototype
- Date: 2026-07-20
- Authority: kotoba-lang/app-kotoba-torrent

## Context

Kotoba needed a BitTorrent v1 downloader whose `.torrent` handling, protocol
validation, hashing, filesystem commits, and desktop lifecycle did not acquire
ambient authority. The first end-to-end target is macOS using
`kotoba-lang/shell`, with an officially distributed Debian netinst ISO as the
legal interoperability fixture.

## Decision

The implementation is split across explicit package and runtime boundaries:

- `kotoba-lang/bencode`: capability-free bounded bencode parser primitives.
- `kotoba-lang/hash`: capability-free SHA-1 implementation for BitTorrent v1
  interoperability; SHA-1 is not approved for signatures or passwords.
- `kotoba-lang/torrent`: `.kotoba` metainfo and peer-wire protocol kernel plus
  explicit tracker, transport, hash-verification, and atomic-commit composition.
- `kotoba-lang/app-kotoba-torrent`: shell application, macOS document handler,
  progress UI, and native capability adapter.
- `kotoba-lang/shell`: application manifest, Kotoba DOM, native lifecycle, and
  file-open boundary.

The macOS bundle imports `org.bittorrent.torrent`, recognizes the `.torrent`
extension and `application/x-bittorrent`, and receives Finder document-open
events. Downloads are confined to `~/Downloads/KotobaTorrent`.

Every piece is SHA-1 verified before it is written. The destination remains a
`.part` file while incomplete. Completion uses an atomic move to the final
filename. A failed hash never advances progress and never produces a completed
artifact.

## Security and product boundaries

- BitTorrent v1 and compact IPv4 tracker peers only.
- HTTP(S) trackers and TCP peers are supported; DHT, PEX, uTP, UDP trackers,
  magnet links, BitTorrent v2, and hybrid torrents are deferred.
- Single-file torrents are supported. Multi-file path projection is deferred.
- No upload or seeding behavior is implemented.
- Peer connections and reads have finite timeouts; failed peers are rotated.
- The application does not silently become the system default handler. macOS
  users select it once through Finder's **Open With** workflow.
- Distribution signing, notarization, and installation into `/Applications`
  are not performed in this development session.

## Evidence

The official Debian 13.6.0 amd64 netinst torrent was downloaded from Debian's
`cdimage.debian.org` service. The live interoperability run observed:

- payload size: 791,674,880 bytes;
- tracker result: 50 compact peers;
- automatic rotation after timeout/reset failures;
- one 262,144-byte piece downloaded and SHA-1 verified;
- verified piece written to
  `~/Downloads/KotobaTorrent/debian-13.6.0-amd64-netinst.iso.part`;
- run stopped deliberately after the first verified piece.

Verification at session close:

- `app-kotoba-torrent`: 2 tests, 6 assertions, 0 failures;
- `kotoba-lang/shell`: 32 tests, 291 assertions, 0 failures;
- macOS `Info.plist`: `plutil -lint` passed;
- shell `app run` planning gate passed;
- native Swift application bundle built successfully.

## Consequences

The application is sufficient for real BitTorrent v1 single-file downloads and
Finder-driven launch, while keeping protocol logic and host effects reviewable.
It is a development bundle, not a signed production release. Resume and sparse
piece-state persistence are not yet implemented; restarting currently begins
piece scheduling from piece zero.

## Resume procedure

```sh
cd /Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/app-kotoba-torrent
bin/build-macos
KOTOBA_TORRENT_APP_DIR="$PWD" target/KotobaTorrent.app/Contents/MacOS/KotobaTorrent
```

The next implementation tranche should add a verified resume ledger, multi-file
safe-path projection, choke-state resilience, and signed/notarized packaging.
