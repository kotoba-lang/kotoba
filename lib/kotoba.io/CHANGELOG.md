# Changelog

All notable changes to kotoba-lang/io are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased] - 2026-09-25

### Added

- `kotoba.lang.io.stream` / `kotoba.io`: `resource` `reader` `writer`
  `input-stream` `output-stream` -- clojure.java.io's; JVM delegates, the kbb
  engine uses its own clojure.java.io implementation (classpath lookup,
  JDK-checked streams). Parity golden measured with JDK 21 raw
  clojure.java.io (test/kotoba/lang/io/stream_test.cljk).

### Changed

- `kotoba.io/copy` is now `kotoba.lang.io.stream/copy`: an input that
  implements `kotoba.io.reader/Reader` is drained into the IWriter exactly as
  before (kotoba.io.copy/copy); any other input is clojure.java.io/copy
  (strings, byte arrays, files, streams, readers, writers). A kotoba file
  value as the OUTPUT names the file on both hosts.

## 2026-09-24

### Added

- `kotoba.lang.io.file` / `kotoba.io`: ambient java.nio.file.Files --
  `temp-dir` `temp-file` `read-all-bytes` `write-bytes` `write-string`
  `delete-if-exists`. File values in and out (no Path); open options as
  keywords (`:append` `:create` `:truncate-existing` `:write`). JVM: the Files
  method; Node: transcribed, parity golden measured with JDK 21 raw Files.
- `kotoba.lang.io.file` (re-exported by `kotoba.io`): `file`, `as-file`,
  `as-relative-path`, `make-parents`, `delete-file` -- the portable subset of
  clojure.java.io. JVM delegates; Node answers with java.io.File's
  normalisation as path strings. Parity literals measured on the JVM.
- `kotoba.lang.io.file` / `kotoba.io`: the java.io.File methods as functions
  of a file value -- `exists?` `file?` `directory?` `hidden?` `absolute?`
  `file-name` `path` `parent` `parent-file` `absolute-path` `absolute-file`
  `canonical-path` `canonical-file` `mkdir` `mkdirs` `delete`
  `create-new-file` `rename-to` `length` `last-modified` `set-last-modified`
  `list-names` `list-files` `can-read?` `can-write?` `can-execute?`, and
  `file-seq`. JVM: the method itself. Node: java.io.UnixFileSystem
  transcribed (realpath(3), readdir order via opendir, JDK canonicalize).
  test/kotoba/lang/io/file_ops_test.cljk: a JVM-measured golden (raw
  java.io.File) that kotoba.io must reproduce on every host.

### Changed

- `make-parents` on Node is now `(mkdirs parent)` -- java.io.File#mkdirs
  transcribed (canonical parent) instead of `mkdir -p`.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.io — IReader/IWriter protocols + pure byte-buffer + copy.

### Added

- Initial library surface, tests, and CI.
