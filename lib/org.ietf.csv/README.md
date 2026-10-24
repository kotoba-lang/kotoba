# org-ietf-csv

**CSV per RFC 4180, in portable `.cljc`. Zero dependencies.**

```clojure
(require '[csv.core :as csv])

(csv/read-csv "a,\"b,c\",d")        ; => [["a" "b,c" "d"]]
(csv/read-maps "id,name\n1,alice")  ; => [{"id" "1" "name" "alice"}]
(csv/read-csv "a\tb" {:separator \tab})
```

Origin plane: RFC 4180 is an IETF document, so the repo is named for where the
spec comes from — same pattern as `org-ietf-cbor`, `org-ietf-deflate`.

## CSV looks like `split(",")` and is not

Everything hard about it is in the quoting rules, and **every one of them
produces plausible wrong rows rather than an error**:

| the rule | what the naive parser does |
|---|---|
| a quoted field may contain the separator | `a,"b,c",d` becomes four fields |
| a quoted field may contain **newlines** | one record becomes two |
| a quote inside quotes is doubled | `"say ""hi"""` keeps its doubling |
| CRLF is the spec, LF is the practice | a trailing `\r` on every row's last field |

That last one is the meanest: `"b\r"` compares unequal to `"b"`, silently,
in every join and every group-by downstream, forever.

**A record is not a line.** That is also why this can never be a scanning
reader: you cannot seek to record N without having read everything before it,
because the delimiter is only a delimiter *outside* quotes. In the kotobase
lake this registers as `:materialize`, not `:scan`, and that is a property of
CSV rather than a gap here.

## What it refuses to decide

**Types.** Every field comes back a string. `"007"` might be a zip code that
must keep its leading zero; `"1.0"` might be a version number. RFC 4180 has no
type system, and a parser's guess here is unrecoverable — the caller who knows
the schema converts.

**Whether row one is a header.** `read-csv` returns rows. `read-maps` treats
the first as a header because the caller said so. Sniffing gets it wrong on
exactly the files where every value looks like a name.

**Absent vs empty.** `a,,b` has an empty middle field; `a,b` has no third one.
`read-maps` omits the key for a short row rather than filling it with `nil` or
`""`, because flattening the two takes the distinction away from every caller.
A long row keeps its extras under their index rather than dropping them.

## Edge cases pinned by tests

- A trailing newline is **not** an empty final record; a trailing separator
  **is** an empty final field.
- A lone newline is **one** record whose single field is empty — consistent
  with `a\n` being one record. The terminator ends a record; it does not
  decide whether one was there.
- A lone `\r` is **data**. Old Mac line endings are not RFC 4180, and dropping
  the character would corrupt a field that legitimately holds one.
- `write-csv` quotes a field when, and only when, leaving it bare would change
  what it parses back as — checked by round-tripping the awkward cases.

Fields accumulate in a char vector rather than a `StringBuilder`: that class is
JVM-only, and `(str acc c)` in a loop is quadratic in the field length.

## Test

```sh
kbb -M:test
kbb --backend sci --classpath "src:test" test/run.cljk
kbb -M:cljs -m cljs.main --target node -m csv.cljs-runner
kbb -M:lint
```
