# drive

The existing CLJC model remains the open-schema semantic oracle. The
capability-free Kotoba profile in `src/drive/bounded.kotoba` represents a
single-rooted tree of at most eight keyword-identified folders and files.
`src/drive/bounded_validate.kotoba` rejects missing parents, files used as
parents, self-links, longer cycles, non-root parentless items, unknown kinds,
and over-limit trees. Updates are persistent and both Web and typed Wasm run
the same conformance graph.

Titles, media types, content/object references, and arbitrary attribute maps
are intentionally not reinterpreted by the bounded profile; consumers needing
those values continue to use the CLJC oracle or an explicit host boundary.

## Content-addressed references

`drive` lets the caller choose an object reference — "a content hash, a uuid,
a path" — and two of those choices behave differently from the third. When
the reference is derived from the bytes, two items holding one PDF hold one
reference, and the library's two safety rules both had to learn that.

`write-item` refused a reference already in use, because filing new content
under an existing one replaces an earlier version's bytes while the history
saying otherwise sits in `:drive/versions`. It now allows it **when the bytes
are the same bytes** — compared against what is stored rather than taken on
the caller's word, since a caller trusted to say "this is content-addressed"
is trusted with exactly what the guard exists to not trust. Different content
under a reference in use is refused as before.

`forget-item` deleted every reference the item held. It now takes
`:keep-ref?`, a predicate over references that must not be deleted, and
reports `:kept`. Nothing here can work that out: this function is given one
item, and the other holder may be in a different workspace entirely — only
the application holding all of them can answer. Without it a Drive that
deduplicated by content would delete a colleague's file when you emptied your
trash, and the failure would surface much later as a download that used to
work.

## Folders

`create-folder` and a `:drive/parent-id` were here from the start, and
`effective-role` walked up the parents, so sharing a folder shared what was
in it. What was missing was everything that reads the tree back:

```clojure
(ws/path ws "memo")            ; root → … → the item, a breadcrumb
(ws/children ws "work" "alice"); what is directly inside, readable, untrashed
(ws/descendants ws "work")     ; every id below, any depth
(ws/move ws "memo" "root")     ; and the refusals that make it safe
```

**Trash is derived, not cascaded, and that is the whole design.** Trashing a
folder by writing the flag onto every descendant means restoring it has to
know which ones it wrote — a file already in the trash before its folder went
there would come back out, restored by a fact about its parent. Recording
which were cascaded is a second piece of state to keep in step with the
first.

`trashed?` asks instead: is this item, or anything above it, in the trash.
Trashing a folder hides everything under it because the answer changes for
all of them at once. Restoring reveals exactly what was visible before,
because nothing else was ever touched. A file explicitly trashed inside a
trashed folder stays trashed when the folder comes back, which is right and
is only possible because the two flags are independent.

`move` refuses to put a folder inside itself or its own descendant. A drag
lands where it lands, so an interface will ask; the result would be a subtree
detached from the root — invisible to a listing that walks down, unreachable
by a breadcrumb that walks up, and marked wrong nowhere. The root refuses to
be moved or trashed for the same kind of reason: trashing it would hide the
entire Drive with no listing left to find it from.

Moving a file into a shared folder shares it, and moving it out unshares it.
That falls out of inheritance rather than being implemented, and it is tested
because it is a permission change nobody performed.

## Where the bytes are

`drive.object` is that host boundary, and it is in this library rather than in
each consumer for one reason: the rules only work if there is one of them. A
permission boundary filled privately by three applications gives three answers
to *may this principal read this file*.

```clojure
(require '[drive.object :as object] '[drive.store.memory :as mem])

(let [store (mem/store)
      {:keys [workspace]} (object/write-item ws store "plan" "alice" bytes
                                             {:object-ref "obj-1"})]
  (object/read-item workspace store "plan" "bob"))
;; {:ok? false :reason :not-permitted}
```

An `IObjectStore` is four operations over opaque references and knows nothing
about principals, roles, share links, trash or quota. Everything in
`drive.object` exists so that it is only reached after the answer is yes.

**Bytes are a vector of unsigned ints, in both directions.** The protocol did
not say so at first, and within hours there were two implementations that
disagreed — `drive.store.memory` passes vectors and a Filecoin-backed store in
another repository passes `byte[]`. Both are reasonable; the protocol not
saying was not. Unstated, the mismatch surfaces in whoever called `read-item`
rather than at the seam. `store-of` normalises both ways, and a backend that
wants arrays says so with `:bytes-out`.

Four rules that a straightforward implementation gets wrong:

- **Trashed items are not readable.** `can-read?` says nothing about trash —
  `visible-items` filters it separately — so composing `can-read?` with a
  store hands out deleted content.
- **Quota is checked before the bytes move.** `add-version` throws when the
  total would exceed, which is correct and too late: the upload has happened
  and the bandwidth is spent.
- **A new version needs a new object reference.** Reusing one silently
  replaces an earlier version's bytes while the history saying otherwise stays
  in `:drive/versions`.
- **A version records who wrote it, and the caller does not get to say who.**
  `:drive.version/author` is the principal `write-item` just checked against
  the ACL. An author passed in `opts` would be a history the caller can
  write; and the moment an item can be shared, a history that cannot say
  which of two writers made a version is a history of nothing.
- **There has to be a way to forget *some* of the history.** `add-version`
  adds and nothing subtracts; trashing frees nothing and `forget-item` frees
  everything, so without `prune-versions` the only way to reclaim a
  heavily-edited document's past is to delete the document. `keep-count`
  below 1 is refused — the newest version is the document, and a prune that
  could take it is a delete under another name.
- **Forgetting returns the quota.** A workspace counting bytes nobody can
  reach fills up for no reason anyone can see.

A write checks permission and quota first, then stores, then records the
version. A store failure leaves the workspace untouched — the model never
claims bytes that are not there. The other order strands objects nothing
references.

### Attaching a backend

`drive.store.memory` is portable and forgets everything. `drive.store.fs` is a
directory on a JVM, and refuses any reference that could name a file outside
it. Anything else attaches through `object/store-of`, which takes four
functions so that neither library has to depend on the other:

```clojure
(object/store-of {:get-object    #(storj/get-object client bucket %)
                  :put-object    #(storj/put-object client bucket %1 %2)
                  :delete-object #(storj/delete-object client bucket %)})
```

`kotoba-lang/io-storj` already exposes those verbs. Whoever builds the store
depends on both, and that is the application.

[![CI](https://github.com/kotoba-lang/drive/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/drive/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/drive.

`drive.workspace` adds tenant hierarchy, owner/editor/commenter/viewer ACLs,
immutable object versions, trash/restore and byte-quota enforcement. Blob I/O
remains a host capability; versions store opaque object references.

Pages editor: https://kotoba-lang.github.io/drive/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Test

```bash
kbb -X:test
```
