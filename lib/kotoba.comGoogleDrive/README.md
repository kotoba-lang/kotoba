# com-google-drive

**Google Drive as a connector** — search, file metadata, permissions, and text
export. Metadata and text, not bytes.

Portable `.cljc`. One dependency, [`kotoba-lang/connector`](https://github.com/kotoba-lang/connector).

## Tools

| tool | effect | scope |
|---|---|---|
| `google_drive_search_files` | read | `drive.metadata.readonly` |
| `google_drive_get_file` | read | `drive.metadata.readonly` |
| `google_drive_list_permissions` | read | `drive.metadata.readonly` |
| `google_drive_export_document` | read | **`drive.readonly`** (content) |

Three of the four never ask for permission to read a file's contents. A
deployment that lists and audits Drive holds `drive.metadata.readonly` only;
the moment it wants to read a document, that is a visible, separate scope.

## There is no download tool, on purpose

`connector.ports/IHttp` hands back an already-parsed body — the right contract
for JSON, the wrong one for a 200 MB video. This workspace keeps bytes on the
object plane (`kotobase.storage`'s large-object profile) rather than in the
query plane, and a connector returning a base64 blob through a tool result
would put a file into a model's context window, which is neither cheap nor
reversible.

`google_drive_export_document` shows where the line is: it asks Drive to render
a Google Doc as `text/plain` (or `text/csv`, `text/markdown`), so what comes
back is text a caller can read.

## `fields` is not an optimisation

Drive's default projection is `id`, `name`, `mimeType` and nothing else. A
caller asking "when was this last touched" gets no `modifiedTime` and no error
explaining why. Every field the normalizer reads is requested by name, and
there is a test asserting the two lists agree.

## Usage

```clojure
(require '[connector.registry :as reg]
         '[connector.invoke :as invoke]
         '[google-drive.connector :as drive])

(def registry (reg/registry [drive/provider]))

(invoke/call registry "google_drive_list_permissions" {"fileId" "…"}
             {:http my-http :tokens my-tokens})
;; => {:permissions [{:type "anyone" :role "reader" :discoverable? true …}]}
;;    i.e. "did this file leave the org", without reading it
```

This namespace cannot obtain a credential; `connector.invoke` attaches it.

## Declaration

`connector.edn` is generated; the test suite fails if the committed file has
drifted.

```sh
kbb --backend sci --classpath "src:../connector/src" emit-connector-edn.cljk
```

## Tests

```sh
kbb --backend sci --classpath "src:test:../connector/src" run-tests.cljk   # 10 tests, 34 assertions
kbb -M:test
```

## Naming

`google.com` → `com-google`, subject `drive` (ADR-2608040100).
