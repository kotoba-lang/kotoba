#!/usr/bin/env python3
"""iceberg_append.py -- append a batch to a Cloudflare R2 Data Catalog table.

`commoncrawl.live-iceberg` (nbb) owns the orchestration; this owns the
Iceberg commit and nothing else. The boundary is NDJSON on disk. This
script knows nothing about seeds, governors or EDN.

Vendored verbatim from `cloud-itonami/otent`'s `scripts/iceberg_append.py`
(itself following the split `com-junkawasaki/org-gleif-projections`
established first in this workspace) rather than re-derived, so the two
callers of Cloudflare's Iceberg REST catalog share one tested contract
instead of two independently-drifting reimplementations. If you change the
behavior here, check whether `otent`'s copy needs the same fix.

Why Python: nbb has no Iceberg writer. This is the thin layer that exists
only for the part nbb cannot do.

## Append, not create-only

A GLEIF-projection-style sibling refuses to write to an existing table,
which is right for a projection rebuilt whole. This is a time series:
every tick appends to a table that must already exist after the first
one. So:

  --create   create the table if absent (first run)
  (default)  require it to exist and append

A run that would have created a table without --create FAILS. Otherwise a
typo'd --table silently starts a second, parallel history that looks fine
until someone queries the one with the older rows in it.

## Schema drift is refused, not null-filled

The schema is taken from the first batch and every later batch must match
it exactly. A change that adds a column mid-stream stops the run; it does
not get null-filled into the existing shape, because that writes a column
of nulls that reads as "these rows had no value" rather than "this run
could not represent them".

exit: 0 ok / 1 refused (missing table, schema drift, empty input) /
      2 could not answer (no credential, table unreadable)
"""

import argparse
import io
import os
import sys


def catalog(account: str, bucket: str):
    tok = os.environ.get("CF_CATALOG_TOKEN", "").strip()
    if not tok:
        print("CF_CATALOG_TOKEN is empty -- this run cannot answer whether the "
              "append succeeded, which is not the same as it having failed",
              file=sys.stderr)
        sys.exit(2)
    from pyiceberg.catalog.rest import RestCatalog

    return RestCatalog(
        name="r2",
        uri=f"https://catalog.cloudflarestorage.com/{account}/{bucket}",
        warehouse=f"{account}_{bucket}",
        token=tok,
    )


def _to_arrow(lines):
    """NDJSON line bytes -> an all-large_string Arrow table, columns sorted.

    Sorted so the schema is a function of the column SET, not of the order
    the JSON happened to serialise in. Without it, two batches with the same
    columns in a different order read as schema drift.
    """
    import pyarrow as pa
    import pyarrow.json as paj

    t = paj.read_json(io.BytesIO(b"".join(lines)))
    names = sorted(t.schema.names)
    t = t.select(names)
    return t.cast(pa.schema([(n, pa.large_string()) for n in names]))


def arrow_batches(path: str, batch_rows: int):
    """Stream the NDJSON in batches. The file's size does not set memory."""
    buf = []
    with open(path, "rb") as fh:
        for line in fh:
            if line.strip():
                buf.append(line)
                if len(buf) >= batch_rows:
                    yield _to_arrow(buf)
                    buf = []
    if buf:
        yield _to_arrow(buf)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--ndjson")
    p.add_argument("--batch-rows", type=int, default=50000)
    p.add_argument("--create", action="store_true",
                   help="create the table if it does not exist (first run only)")
    p.add_argument("--count", action="store_true",
                   help="print the table's row count and exit")
    a = p.parse_args()

    from pyiceberg.exceptions import NoSuchTableError

    cat = catalog(a.account, a.bucket)
    ident = (a.namespace, a.table)

    if a.count:
        # A separate call from the write, deliberately: "committed" and
        # "present" are two claims and must be measured twice.
        try:
            t = cat.load_table(ident)
        except NoSuchTableError:
            # 3, not 2. Exit 2 above means the catalog could not be ASKED --
            # no token, no reachable endpoint -- and this means it was asked
            # and answered: the table is not there.
            print(f"no such table: {a.namespace}.{a.table}", file=sys.stderr)
            return 3
        print(t.scan().to_arrow().num_rows)
        return 0

    if not a.ndjson:
        print("--ndjson is required unless --count", file=sys.stderr)
        return 2

    table = None
    schema = None
    total = 0

    for i, batch in enumerate(arrow_batches(a.ndjson, a.batch_rows)):
        if table is None:
            schema = batch.schema
            try:
                table = cat.load_table(ident)
            except NoSuchTableError:
                if not a.create:
                    print(
                        f"{a.namespace}.{a.table} does not exist. Pass --create "
                        "if this is the first run. Refusing to create it "
                        "implicitly: a mistyped --table would start a second "
                        "history that looks healthy and holds half the rows.",
                        file=sys.stderr,
                    )
                    return 1
                cat.create_namespace_if_not_exists((a.namespace,))
                table = cat.create_table(ident, schema=schema)
                print(f"created {a.namespace}.{a.table}", file=sys.stderr)
            else:
                existing = sorted(table.schema().column_names)
                incoming = sorted(schema.names)
                if existing != incoming:
                    print(
                        f"schema drift: table has {existing}, batch has {incoming}. "
                        "Refusing to append -- null-filling the difference would "
                        "record 'no value' where the truth is 'not representable'.",
                        file=sys.stderr,
                    )
                    return 1
        elif schema is not None and batch.schema != schema:
            print(f"schema drift at batch {i}: {batch.schema.names} != {schema.names}",
                  file=sys.stderr)
            return 1

        table.append(batch)
        total += batch.num_rows
        print(f"  batch {i}: +{batch.num_rows} (total {total})", file=sys.stderr)

    if table is None:
        # Zero rows creates a snapshot that says "a tick happened and had
        # nothing new", which is indistinguishable from a tick that failed.
        print("refusing to commit an empty batch (0 rows in NDJSON)", file=sys.stderr)
        return 1

    print(f"appended {total} rows to {a.namespace}.{a.table}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
