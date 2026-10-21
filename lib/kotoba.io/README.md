# kotoba-lang/io

[![CI](https://github.com/kotoba-lang/io/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/io/actions/workflows/ci.yml)

**Layer 3 (I/O) of the kotoba foundational stdlib** — the streaming abstraction
(`IReader` / `IWriter`) the other libs and actors re-roll, in one place. A pure
byte-buffer and `copy` make draining a reader into a writer a pure reduction.
Zero third-party runtime deps; every namespace is `.cljc` (JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why protocols

A capability-confined cell does not get a socket or a file descriptor — the
host grants a reader/writer handle. `io` defines the protocols and the pure
buffer/copy glue; the host (or `fs`/`http`'s protocol impls) supplies the
endpoints.

## Current surface

`kotoba.lang.io`:

- `IReader` protocol: `read!` → next chunk or nil (EOF)
- `IWriter` protocol: `write!` → append a chunk
- `byte-buffer` — pure growable byte buffer (`put`, `to-bytes`, `len`)
- `reader-buffer` / `buffer-writer` — adapt a byte-buffer as reader/writer
- `copy` — drain a reader into a writer (pure reduction)
- `reader-seq` — lazy seq from a reader

`kotoba.lang.io.file` (re-exported by `kotoba.io`) — the portable subset of
`clojure.java.io`: `file`, `as-file`, `as-relative-path`, `make-parents`,
`delete-file`. On the JVM each is clojure.java.io's own var (a `java.io.File`);
on Node (kbb) a file is its path string, normalised exactly as `java.io.File`
normalises it, so `(str (file ...))` is the same on both hosts (the test
literals were measured on JVM clojure.java.io).

`kotoba.lang.io.stream` (re-exported by `kotoba.io`) — `resource`, `reader`,
`writer`, `input-stream`, `output-stream` and `copy` with clojure.java.io's
contract: the JVM's own vars on the JVM, the kbb engine's own implementation
of them on kbb (the stream objects its `with-open` / `line-seq` / `slurp`
accept; `resource` is its classpath lookup, a js/URL). `kotoba.io/copy`
drains an IReader into an IWriter exactly as before when the input is a
`kotoba.io.reader/Reader`, and is clojure.java.io/copy otherwise. Parity
golden measured against raw clojure.java.io on JDK 21
(test/kotoba/lang/io/stream_test.cljk). Not portable: a file value as copy's
INPUT (on Node it is the path string, which copy reads as content -- use
`(copy (input-stream f) out)`), and `as-url` (absent).

The `java.io.File` methods, as functions of a file value (same namespaces):
`exists?` `file?` `directory?` `hidden?` `absolute?` `file-name` `path`
`parent` `parent-file` `absolute-path` `absolute-file` `canonical-path`
`canonical-file` `mkdir` `mkdirs` `delete` `create-new-file` `rename-to`
`length` `last-modified` `set-last-modified` `list-names` `list-files`
`can-read?` `can-write?` `can-execute?` and `file-seq`. On the JVM each IS
the method; on Node each is `java.io.UnixFileSystem` transcribed, checked
against a golden measured with raw `java.io.File`
(`test/kotoba/lang/io/file_ops_test.cljk`). Methods with no portable answer
(`toPath` `toURI` `toURL` `deleteOnExit` `compareTo` `get*Space`
`set*able` `setReadOnly`) are absent.

Ambient `java.nio.file.Files` (same namespaces), paths in and out as file
values, never `java.nio.file.Path`: `temp-dir` (`createTempDirectory`),
`temp-file` (`createTempFile`, nil suffix = `.tmp`), `read-all-bytes` (a host
byte array: `byte[]` / `Int8Array`), `write-bytes` and `write-string` (UTF-8;
options `:append` `:create` `:truncate-existing` `:write`, none = the JDK
default), `delete-if-exists`. On the JVM each IS the `Files` method; on Node
the same syscalls, name shape and exception messages (ex-info naming the JDK
class), checked against a golden measured with raw `Files`
(`test/kotoba/lang/io/files_test.cljk`).

## Install

```clojure
io.github.kotoba-lang/io {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.io :as io])

(let [buf (io/byte-buffer)]
  (io/write! (io/buffer-writer buf) (byte-array (range 5)))
  (alength (io/to-bytes buf)))            ;=> 5
(let [src (io/reader-buffer (doto (io/byte-buffer) (io/put (byte-array (range 5)))))
      dst (io/byte-buffer)]
  (io/copy src (io/buffer-writer dst))
  (io/len dst))                           ;=> 5
```

## Verify

```sh
kbb -M:test
```
