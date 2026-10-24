# kotoba-lang/org-ieee-tar

Zero-dep portable `.cljc` **tar reader and writer** (POSIX.1 ustar, IEEE Std
1003.1), including the PAX and GNU header extensions.

Named `org-ieee-tar` — IEEE publishes POSIX, the same `org-<body>-<spec>` pattern
as `org-ieee-verilog`/`org-ieee-vhdl` and as the other archive/codec repos
(`org-ietf-deflate`, `org-pkware-zip`, `org-tukaani-xz`).

tar is an **archiver, not a codec**: it concatenates 512-byte header blocks with
padded file data and leaves compression to somebody else. `.tar.gz` is this repo
composed with `org-ietf-deflate`, `.tar.xz` with `org-tukaani-xz`:

```clojure
(require '[tar.core :as tar] '[deflate.core :as deflate])

(deflate/gzip (tar/build entries))                    ; → .tar.gz
(tar/parse (deflate/gunzip tgz-bytes))                ; ← .tar.gz
(tar/parse (xz/decompress txz-bytes))                 ; ← .tar.xz
```

## Usage

```clojure
;; read — metadata only, nothing copied out of the archive
(def listed (tar/entries archive-bytes))
(tar/names listed)                                    ; => ["a.txt" "dir/" ...]
(tar/read-entry archive-bytes (tar/entry listed "a.txt"))
;; => {:name "a.txt" :size 5 :bytes [...] :mode 420 :mtime 0 :type :file ...}

(tar/parse archive-bytes)                             ; every entry with :bytes

;; write
(tar/build [{:name "a.txt" :bytes (b/str->utf8 "hello")}
            {:name "dir/" :type :directory :mode 0755}
            {:name "dir/link" :type :symlink :linkname "../a.txt"}]
           {:record-size 10240})
```

Entries carry `:name :size :mode :mtime :uid :gid :uname :gname :type
:linkname :offset :pax`. `:type` is one of `:file :directory :symlink
:hard-link :fifo :char-device :block-device`.

Writes are **reproducible**: mtime, uid and gid default to 0, nothing reads the
clock or the environment, so the same entries always produce the same bytes.

## Header dialects

Three exist in the wild and all three are read:

| dialect | how it appears | what it solves |
|---|---|---|
| **ustar** (POSIX.1-1988) | `magic = "ustar\0"`, name split across a 155-byte prefix + 100-byte name | paths up to 255 bytes that split at a `/` |
| **PAX** (POSIX.1-2001) | an `x`/`g` entry whose *data* is `"<len> <key>=<value>\n"` records overriding the next entry | any-length names, sub-second mtimes, >8 GiB sizes, non-ASCII metadata. What macOS `tar` writes by default |
| **GNU** | `L`/`K` entries for long name/link, base-256 numeric fields | the same problems, differently |

Writing produces ustar, escalating to a PAX header only for what ustar cannot
express: a name that will not split at a `/`, a link target over 100 bytes, or a
size above 8 GiB.

Failures are `ex-info` with a `:reason` — `:bad-checksum`, `:truncated`,
`:bad-numeric-field`, `:field-overflow`.

Not implemented: extraction to a filesystem (this library moves bytes, not
files — permissions, symlink safety and path traversal are the caller's policy
decision), sparse files (GNU `S` entries), and the `V` volume-label entry.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against python3 tarfile and `tar`
kbb --backend sci run-tests.cljk       # ClojureScript: the same portable suite
kbb -M:lint
```

The JVM suite shells out to python3's `tarfile` — which writes GNU, ustar *and*
PAX on demand — in both directions, and extracts our archives with the system
`tar` (including a symlink and a `.tar.gz` made with our own gzip). Both
directions matter: *them → us* covers headers we would never write, *us → them*
proves our field offsets, octal padding and checksum are right. A self-round-trip
agrees with itself no matter where the fields sit.
