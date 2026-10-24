"""Regenerate the test fixtures using the REFERENCE implementation.

Python, and not nbb, for one reason: the only trustworthy oracle for a
Parquet decoder is a file written by Parquet's own writer, and that writer is
reachable from this machine through pyarrow. A fixture this repo generated
itself would test the decoder against its own misunderstanding.

    python3 -m venv .venv && .venv/bin/pip install pyarrow
    .venv/bin/python test/fixtures/generate.py
"""
import pyarrow as pa, pyarrow.parquet as pq, pathlib

here = pathlib.Path(__file__).parent

# Three row groups with disjoint price ranges, so chunk pruning is observable,
# and a nullable column so definition levels are exercised.
table = pa.table({
    "price":  pa.array([10, 20, 30, 110, 120, 130, 210, 220, 230], pa.int64()),
    "region": pa.array(["east","east","west","west","east","east","east","west","west"]),
    "note":   pa.array([None,"clearance",None,None,None,"sale",None,None,None]),
    # Beyond 2^53. A decoder that accumulates with Math/pow returns this
    # rounded, on BOTH runtimes, and says nothing.
    "big":    pa.array([2**62 + 1] * 9, pa.int64()),
})

# plain.parquet — the subset this reader decodes: PLAIN, uncompressed.
pq.write_table(table, here / "plain.parquet", row_group_size=3,
               compression="none", use_dictionary=False,
               write_statistics=True, version="2.6",
               data_page_version="1.0")

# dictionary-snappy.parquet — what pyarrow writes by DEFAULT, and what most
# real files therefore are. Decoded, and asserted to agree value-for-value
# with plain.parquet: two independent encodings of the same data.
pq.write_table(table, here / "dictionary-snappy.parquet", row_group_size=3,
               compression="snappy", use_dictionary=True,
               write_statistics=True, version="2.6")

# delta.parquet — deliberately OUTSIDE the supported subset, and it has to
# stay that way. Statistics must remain readable from a file this reader
# cannot decode, because the footer does not depend on how the pages were
# encoded; that property is what makes pruning and min/max/count work
# regardless. When snappy became supported, this fixture is what kept the
# property tested instead of quietly losing its only witness.
#
# DELTA_BINARY_PACKED and not gzip, though gzip was the obvious choice: gzip
# byte-equality is not a property that holds across environments. Deflate
# output is implementation-dependent, so the fixture regenerated identically
# on one machine and differed on CI's — same size, different bytes. Codec
# refusal is covered by unit tests on check-readable! instead, which need no
# fixture and can name every codec.
pq.write_table(table, here / "delta.parquet", row_group_size=3,
               compression="none", use_dictionary=False,
               column_encoding={"price": "DELTA_BINARY_PACKED",
                                "big": "DELTA_BINARY_PACKED"},
               write_statistics=True, version="2.6")

# gzip.parquet — a real gzip-compressed file, decoded through
# org-ietf-deflate. NOT part of the byte-determinism gate: deflate output is
# implementation-dependent, so "the reference writer produces exactly these
# bytes" is not a claim gzip supports across environments (measured: identical
# locally, different on CI). What IS checkable is that it decodes to the same
# values as plain.parquet, and that is what the test asserts.
pq.write_table(table, here / "gzip.parquet", row_group_size=3,
               compression="gzip", use_dictionary=True,
               write_statistics=True, version="2.6")

# zstd.parquet — what Spark, Trino and Databricks commonly write, and what
# this reader refused by name until org-ietf-zstd was wired in. Included in
# the byte-determinism gate: unlike deflate, zstd's reference encoder is
# deterministic for a fixed level, and pyarrow pins the level.
pq.write_table(table, here / "zstd.parquet", row_group_size=3,
               compression="zstd", use_dictionary=False,
               write_statistics=True, version="2.6",
               data_page_version="1.0")

for p in sorted(here.glob("*.parquet")):
    print(p.name, p.stat().st_size, "bytes")
