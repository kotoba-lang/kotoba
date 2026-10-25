"""Check that files THIS REPO wrote are valid Arrow, using the reference reader.

    kbb -M:test -m arrow.emit-for-python /tmp/arrow-out
    .venv/bin/python test/fixtures/verify_written.py /tmp/arrow-out

Why this exists as a separate step: "the writer produces valid Arrow" is a
statement about what a real Arrow implementation accepts, and it cannot be
checked from inside the repo. Round-tripping our writer through our own reader
proves only that the two share an opinion -- and the failures that matter most
are exactly the ones both halves would share. A buffer that is not 8-byte
aligned, a metadata length that does not account for its padding, a vtable
with a wrong table size: every one of those round-trips through our reader
cleanly and is rejected or misread here.

`validate(full=True)` is the point of the exercise -- it walks offsets and
buffer bounds rather than trusting the metadata.
"""
import pyarrow as pa
import pathlib
import sys

out = pathlib.Path(sys.argv[1])

EXPECTED = {
    "single-batch": {
        "price":  [10, 20, 30],
        "region": ["east", "west", "east"],
        "note":   [None, "clearance", None],
        "big":    [4611686018427387905, -4611686018427387905, 0],
        "flag":   [True, None, False],
        "ratio":  [1.5, None, -0.5],
        "small":  [1.5, -2.25, None],
        "tiny":   [-1, 2, 127],
        "c32":    [1, -2, 3],
    },
    "multi-batch": {"price": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
    "all-null":    {"absent": [None] * 4, "blank": [None] * 4},
    "no-nulls":    {"n": [1, 2, 3], "s": ["a", "bb", "ccc"]},
    "empty-batch": {"n": []},
    "unicode":     {"s": ["日本語", "", "aéb", None]},
}

TYPES = {
    "price": pa.int64(), "big": pa.int64(), "tiny": pa.int8(),
    "c32": pa.int32(), "ratio": pa.float64(), "small": pa.float32(),
    "flag": pa.bool_(), "region": pa.string(), "note": pa.string(),
}

BATCHES = {"multi-batch": 3}

failures = []
for name, expected in EXPECTED.items():
    path = out / f"{name}.arrow"
    try:
        with pa.ipc.open_file(path) as r:
            n = r.num_record_batches
            table = r.read_all()
        # Walks every offset and buffer bound rather than trusting metadata.
        table.validate(full=True)

        if name in BATCHES and n != BATCHES[name]:
            failures.append(f"{name}: {n} batches, expected {BATCHES[name]}")

        got_cols = list(table.column_names)
        if got_cols != list(expected.keys()):
            failures.append(f"{name}: columns {got_cols} != {list(expected.keys())}")

        for col, want in expected.items():
            got = table.column(col).to_pylist()
            if got != want:
                failures.append(f"{name}.{col}: {got!r} != {want!r}")
            if col in TYPES and table.schema.field(col).type != TYPES[col]:
                failures.append(
                    f"{name}.{col}: type {table.schema.field(col).type} != {TYPES[col]}")
        print(f"ok   {name}  ({n} batch(es), {table.num_rows} rows)")
    except Exception as e:
        failures.append(f"{name}: {type(e).__name__}: {e}")
        print(f"FAIL {name}: {e}")

if failures:
    print("\n" + "\n".join(failures))
    sys.exit(1)
print(f"\nall {len(EXPECTED)} written files accepted by pyarrow {pa.__version__}")
