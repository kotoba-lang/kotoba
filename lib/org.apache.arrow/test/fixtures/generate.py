"""Regenerate the test fixtures using the REFERENCE implementation.

Python, and not nbb, for the same reason `org-apache-parquet` gives: the only
trustworthy oracle for an Arrow IPC decoder is a file written by Arrow's own
writer, and that writer is reachable from this machine through pyarrow. A
fixture this repo generated itself would test the decoder against its own
misunderstanding of the spec.

    python3 -m venv .venv && .venv/bin/pip install pyarrow
    .venv/bin/python test/fixtures/generate.py

## The table is deliberately the same one org-apache-parquet uses

Same four columns, same nine rows, same batch boundaries. That is what makes
`cross_format_test` possible: two reference writers, two independent decoders
in this workspace, one set of values. A disagreement is then a decoder bug in
one of them rather than a difference of opinion about the data.
"""
import pyarrow as pa, pathlib

here = pathlib.Path(__file__).parent

# Identical to org-apache-parquet's fixture table, on purpose -- see above.
table = pa.table({
    "price":  pa.array([10, 20, 30, 110, 120, 130, 210, 220, 230], pa.int64()),
    "region": pa.array(["east","east","west","west","east","east","east","west","west"]),
    "note":   pa.array([None,"clearance",None,None,None,"sale",None,None,None]),
    # Beyond 2^53. A decoder that accumulates a 64-bit little-endian integer
    # with Math/pow returns this rounded, on BOTH runtimes, and says nothing.
    "big":    pa.array([2**62 + 1] * 9, pa.int64()),
})


def write_ipc(path, tbl, chunk=3, **kw):
    with pa.ipc.new_file(path, tbl.schema, **kw) as w:
        w.write_table(tbl, max_chunksize=chunk)


# plain.arrow -- three record batches, uncompressed, no dictionary. The subset
# this reader decodes.
write_ipc(here / "plain.arrow", table)

# compressed.arrow -- OUTSIDE the supported subset, and it has to stay that
# way. Arrow's body compression is per-buffer and does not touch the metadata,
# so `count`, `count-non-null` and all-null pruning must remain answerable
# from a file whose buffers this reader cannot decompress. That property is
# the Arrow analogue of "statistics work on files this reader cannot decode",
# and this fixture is its only witness.
write_ipc(here / "compressed.arrow", table,
          options=pa.ipc.IpcWriteOptions(compression="zstd"))

# lz4.arrow -- the witness that replaced compressed.arrow when ZSTD became
# decodable. The property needs a fixture whose buffers this reader CANNOT
# undo, and org-apache-parquet keeps delta.parquet for exactly the same
# reason: when snappy landed, the file that had been proving "statistics are
# readable from what we cannot decode" stopped proving it.
#
# LZ4_FRAME, because there is no portable .cljc LZ4 decoder in this workspace
# and therefore no risk of this fixture quietly becoming readable too.
write_ipc(here / "lz4.arrow", table,
          options=pa.ipc.IpcWriteOptions(compression="lz4"))

# types.arrow -- one batch, the physical layouts a flat reader has to tell
# apart: a bit-packed boolean, a float64, a null-free string, and a column
# that is entirely null (which is the ONE thing Arrow metadata can prune on,
# since null_count == length is a proof and min/max are not recorded at all).
types = pa.table({
    "flag":   pa.array([True, False, None, True], pa.bool_()),
    "ratio":  pa.array([1.5, 2.25, None, -0.5], pa.float64()),
    "label":  pa.array(["a", "bb", "ccc", "dddd"]),
    "absent": pa.array([None, None, None, None], pa.int64()),
    # Negatives, which are the two's-complement path. A decoder that reads the
    # high word as unsigned returns a number near 2^64 for every one of these
    # and throws nothing, so nothing downstream can tell.
    "delta":  pa.array([-1, -2**40, 7, None], pa.int64()),
    # float32, whose four-byte layout is a different reader from float64.
    # These three values are exactly representable, so the comparison is
    # against the written value rather than against a rounding.
    "small":  pa.array([1.5, -2.25, None, 0.5], pa.float32()),
    # int32 and a 16-bit width, so the fixed-width strides are all exercised.
    "count32": pa.array([1, -2, 3, None], pa.int32()),
    "tiny":   pa.array([-1, 2, None, 127], pa.int8()),
})
write_ipc(here / "types.arrow", types, chunk=4)

# ground-truth.edn -- what the REFERENCE implementation says these files
# contain. The decoder is asserted against this rather than against numbers
# transcribed by hand into a test, so regenerating a fixture cannot silently
# drift from the assertions about it: the expectations are regenerated in the
# same breath, by the writer, from the file it just wrote.
#
# EDN and not JSON so the test needs no parser: this repo depends on columnar
# and nothing else, and `clojure.edn` is in the standard library on both
# runtimes.


def edn(x, indent=0):
    pad = "  " * indent
    if x is None:
        return "nil"
    if x is True:
        return "true"
    if x is False:
        return "false"
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(x, float):
        return repr(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, list):
        return "[" + " ".join(edn(v) for v in x) + "]"
    if isinstance(x, dict):
        items = "\n".join(f'{pad}  "{k}" {edn(v, indent + 1)}'
                          for k, v in sorted(x.items()))
        return "{\n" + items + "\n" + pad + "}"
    raise TypeError(type(x))


truth = {}
for name, tbl in [("plain.arrow", table), ("types.arrow", types),
                  ("compressed.arrow", table), ("lz4.arrow", table)]:
    with pa.ipc.open_file(here / name) as r:
        truth[name] = {
            "columns": [f.name for f in r.schema],
            "types": [str(f.type) for f in r.schema],
            "batches": r.num_record_batches,
            "rows": [r.get_batch(i).num_rows for i in range(r.num_record_batches)],
            "values": {f.name: tbl.column(f.name).to_pylist() for f in r.schema},
            "nulls": {f.name: tbl.column(f.name).null_count for f in r.schema},
        }
(here / "ground-truth.edn").write_text(
    ";; GENERATED by generate.py from the pyarrow reference writer. Do not edit.\n"
    + edn(truth) + "\n")

for p in sorted(here.glob("*.arrow")):
    print(p.name, p.stat().st_size, "bytes")
print("pyarrow", pa.__version__)
