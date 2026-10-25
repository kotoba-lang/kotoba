# Kotoba Torrent

macOS BitTorrent v1 downloader app built on the `kotoba-lang/shell` boundary.
Kotoba owns the app surface and protocol policy; AppKit owns document-open and
lifecycle; the Clojure adapter supplies explicitly bounded HTTP/TCP/filesystem
effects.

```sh
chmod +x bin/build-macos
bin/build-macos
KOTOBA_TORRENT_APP_DIR="$PWD" open target/KotobaTorrent.app
```

The bundle declares `org.bittorrent.torrent`, so Finder can open `.torrent`
documents with the app. Downloads go to `~/Downloads/KotobaTorrent` and remain
as `.part` until every SHA-1 piece hash succeeds.

Architecture, evidence, security boundaries, and session-resume notes are in
[`docs/adr/ADR-2607201300-kotoba-torrent-app.md`](docs/adr/ADR-2607201300-kotoba-torrent-app.md).
